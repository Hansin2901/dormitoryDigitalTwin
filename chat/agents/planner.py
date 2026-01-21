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
        "description": "Execute a Cypher query against Neo4j graph database. Use for questions about relationships, topology, for example which AC services, which room, what sensors are in a room, etc. Should also be used to look up sensor IDs before querying time-series data.",
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
        "description": "Execute a SQL query against InfluxDB time-series database. Use for questions about sensor readings over time, temperatures, occupancy patterns, averages, etc. Note if you need the senssor ID you will have to query the graph database with using the room numbers to obtain the sensor IDs in them.",
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
        """Execute a tool and return the result (legacy method without tracing)."""
        try:
            tool_func = TOOL_FUNCTIONS.get(tool_name)
            if not tool_func:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
            return tool_func(**tool_input)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_tool_with_span(self, tool_name: str, tool_input: dict, trace: Any = None) -> dict:
        """Execute a tool with Langfuse tool observation tracing."""
        if trace:
            try:
                with trace.tool_span(
                    name=f"tool_{tool_name}",
                    input_data=tool_input,
                    metadata={"tool": tool_name}
                ) as tool_obs:
                    try:
                        tool_func = TOOL_FUNCTIONS.get(tool_name)
                        if not tool_func:
                            result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                        else:
                            result = tool_func(**tool_input)

                        tool_obs.update(output=result)
                        return result

                    except Exception as e:
                        error_result = {"success": False, "error": str(e)}
                        tool_obs.update(output=error_result)
                        return error_result
            except Exception:
                # Fall back to untraced execution if span fails
                pass

        return self._execute_tool(tool_name, tool_input)

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
            metadata={},
            input_data={"query": user_query}
        )

        response = AgentResponse()
        messages = [{"role": "user", "content": user_query}]

        # Use trace as context manager for proper v3 API usage
        with trace:
            for iteration in range(self.max_iterations):
                print(f"[Agent] Starting iteration {iteration + 1}")

                # Use span as context manager with input data
                with trace.span(
                    name=f"iteration_{iteration + 1}",
                    input_data={"messages": messages.copy()},
                    metadata={"iteration": iteration + 1}
                ) as iter_span:
                    try:
                        print(f"[Agent] Calling LLM with {len(messages)} messages")

                        # Build messages array with system prompt for tracing
                        trace_messages = [
                            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                            *[{"role": m["role"], "content": m.get("content", str(m))} for m in messages]
                        ]

                        # Wrap LLM call in generation observation
                        with trace.generation(
                            name="llm_call",
                            model=self.llm.model_name,
                            input_data=trace_messages,
                            metadata={"tools": TOOLS}
                        ) as gen:
                            llm_response = self.llm.generate_with_tools(
                                system_prompt=PLANNER_SYSTEM_PROMPT,
                                messages=messages,
                                tools=TOOLS,
                                parent_trace=iter_span
                            )
                            gen.update(output=llm_response)

                        print(f"[Agent] LLM response keys: {llm_response.keys()}")

                        # Check if LLM called a tool
                        if "function_call" in llm_response:
                            func_call = llm_response["function_call"]
                            tool_name = func_call["name"]
                            tool_input = func_call["arguments"]

                            # Execute tool within its own span
                            tool_result = self._execute_tool_with_span(tool_name, tool_input, trace)

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

                            iter_span.update(output={
                                "action": "tool_call",
                                "tool_name": tool_name,
                                "tool_input": tool_input,
                                "tool_result": tool_result
                            })

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
                                iter_span.update(output={
                                    "action": "nudge",
                                    "llm_response": content
                                })
                                continue

                            # It's a final answer
                            response.final_answer = content
                            iter_span.update(output={
                                "action": "final_answer",
                                "answer": content
                            })
                            break

                    except Exception as e:
                        print(f"[Agent] Error in iteration {iteration + 1}: {e}")
                        import traceback
                        traceback.print_exc()
                        iter_span.update(output={"error": str(e)})
                        response.final_answer = f"Error: {str(e)}"
                        break

            else:
                # Max iterations reached
                if response.steps:
                    response.final_answer = "I gathered some data but couldn't complete the analysis. Please see the results above."
                else:
                    response.final_answer = "I wasn't able to answer your question."

            # Set the final output on the root trace
            trace.set_output({
                "final_answer": response.final_answer,
                "steps_count": len(response.steps),
                "tools_used": [s.tool_name for s in response.steps if s.tool_name]
            })

            # Get trace URL while still inside the context
            try:
                response.trace_url = trace.get_trace_url()
            except Exception:
                pass

        self.llm.flush()
        return response
