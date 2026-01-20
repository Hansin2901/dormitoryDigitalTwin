"""Planner Agent - Main orchestrating agent with Langfuse tracing."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from dataclasses import dataclass, field
from typing import Any

from chat.llm import GeminiClient
from chat.prompts import PLANNER_SYSTEM_PROMPT
from chat.tools import execute_cypher, execute_sql


# Tool definitions for Gemini function calling
TOOLS = [
    {
        "name": "execute_cypher",
        "description": "Execute a Cypher query against Neo4j graph database. Use for questions about relationships, topology, which AC services which room, what sensors are in a room, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The Cypher query to execute"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "execute_sql",
        "description": "Execute a SQL query against InfluxDB time-series database. Use for questions about sensor readings over time, temperatures, occupancy patterns, averages, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The SQL query to execute"
                }
            },
            "required": ["query"]
        }
    }
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "execute_cypher": execute_cypher,
    "execute_sql": execute_sql,
}


@dataclass
class AgentStep:
    """A single step in the agent's reasoning."""
    thought: str = ""
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_result: Any | None = None


@dataclass
class AgentResponse:
    """Complete response from the planner agent."""
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: str = ""
    trace_url: str | None = None


class PlannerAgent:
    """
    Main orchestrating agent that reasons and calls tools iteratively.

    Uses an agentic loop:
    1. Think about what to do
    2. Call a tool if needed
    3. Observe the result
    4. Repeat until ready to answer

    All steps are traced in Langfuse.
    """

    def __init__(self):
        """Initialize the planner agent with LLM client."""
        self.llm = GeminiClient()
        self.max_iterations = 10

    def _execute_tool(self, tool_name: str, tool_input: dict, trace: Any = None) -> dict:
        """Execute a tool and return the result."""
        tool_span = None
        if trace:
            try:
                tool_span = trace.span(name=f"tool_{tool_name}", input=tool_input)
            except Exception:
                pass

        try:
            tool_func = TOOL_FUNCTIONS.get(tool_name)
            if not tool_func:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
            else:
                result = tool_func(**tool_input)

            if tool_span:
                try:
                    tool_span.end(output=result)
                except Exception:
                    pass

            return result

        except Exception as e:
            error_result = {"success": False, "error": str(e)}
            if tool_span:
                try:
                    tool_span.end(output=error_result, level="ERROR")
                except Exception:
                    pass
            return error_result

    def _format_tool_result(self, result: dict) -> str:
        """Format tool result for the LLM context."""
        if result.get("success"):
            data = result.get("data", [])
            row_count = result.get("row_count", 0)
            if row_count > 20:
                data_str = json.dumps(data[:20], indent=2)
                return f"Result ({row_count} rows, showing first 20):\n{data_str}"
            else:
                return f"Result ({row_count} rows):\n{json.dumps(data, indent=2)}"
        else:
            return f"Error: {result.get('error', 'Unknown error')}"

    def _looks_like_intent_without_call(self, text: str) -> bool:
        """Check if the response describes intent to call a tool without actually calling it."""
        intent_phrases = [
            "i'll use", "i will use", "i'll call", "i will call",
            "let me use", "let me call", "i need to use", "i need to call",
            "using execute_", "call execute_"
        ]
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in intent_phrases)

    def run(self, user_query: str, user_id: str | None = None) -> AgentResponse:
        """Process user query through agentic loop."""
        trace = self.llm.create_trace(
            name="agent_run",
            user_id=user_id,
            metadata={"query": user_query}
        )

        response = AgentResponse()
        messages = [{"role": "user", "content": user_query}]

        for iteration in range(self.max_iterations):
            iter_span = trace.span(
                name=f"iteration_{iteration + 1}",
                metadata={"iteration": iteration + 1}
            )

            try:
                llm_response = self.llm.generate_with_tools(
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    messages=messages,
                    tools=TOOLS,
                    parent_trace=iter_span
                )

                # Check if LLM called a tool
                if "function_call" in llm_response:
                    func_call = llm_response["function_call"]
                    tool_name = func_call["name"]
                    tool_input = func_call["arguments"]

                    # Execute tool
                    tool_result = self._execute_tool(tool_name, tool_input, trace)

                    # Record step
                    step = AgentStep(
                        thought=f"Calling {tool_name}",
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_result=tool_result
                    )
                    response.steps.append(step)

                    # Add to conversation for next iteration
                    formatted_result = self._format_tool_result(tool_result)
                    messages.append({
                        "role": "model",
                        "content": f"Calling {tool_name}"
                    })
                    messages.append({
                        "role": "function",
                        "name": tool_name,
                        "content": formatted_result
                    })

                    iter_span.end(output={"tool_called": tool_name, "success": tool_result.get("success")})

                else:
                    # Got a text response
                    content = llm_response.get("content", "")

                    # Check if model described intent without calling
                    if self._looks_like_intent_without_call(content) and iteration < self.max_iterations - 1:
                        # Nudge model to actually call the tool
                        messages.append({"role": "model", "content": content})
                        messages.append({
                            "role": "user",
                            "content": "Please actually call the tool now with a query. Don't describe what you'll do - execute the function."
                        })
                        iter_span.end(output={"nudged_to_call": True})
                        continue

                    # It's a final answer
                    response.final_answer = content
                    iter_span.end(output={"final_answer": True})
                    break

            except Exception as e:
                iter_span.end(output={"error": str(e)}, level="ERROR")
                response.final_answer = f"Error: {str(e)}"
                break

        else:
            # Max iterations reached
            if response.steps:
                response.final_answer = "I gathered some data but couldn't complete the analysis. Please see the results above."
            else:
                response.final_answer = "I wasn't able to answer your question."

        try:
            response.trace_url = trace.get_trace_url()
        except Exception:
            pass

        self.llm.flush()
        return response
