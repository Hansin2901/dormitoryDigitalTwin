"""Gemini LLM client wrapper with function calling and optional Langfuse tracing."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from typing import Any

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.generativeai.types import content_types
from dotenv import load_dotenv

load_dotenv()

# Try to import Langfuse v3
LANGFUSE_AVAILABLE = False
langfuse_client = None

try:
    from langfuse import get_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if public_key and secret_key:
        # Set env vars for Langfuse
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        host = os.getenv("LANGFUSE_HOST")
        if host:
            os.environ["LANGFUSE_HOST"] = host

        langfuse_client = get_client()
        LANGFUSE_AVAILABLE = True
        print("Langfuse tracing enabled")
except Exception as e:
    print(f"Langfuse not available: {e}")


class GeminiClient:
    """Wrapper for Google Gemini API with function calling and optional Langfuse tracing."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        """
        Initialize the Gemini client with optional Langfuse tracing.

        Args:
            model: Gemini model to use
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)
        self.langfuse = langfuse_client

    def _convert_tools_to_gemini_format(self, tools: list[dict]) -> list[Tool]:
        """Convert our tool definitions to Gemini's format."""
        function_declarations = []
        for tool in tools:
            func_decl = FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"]
            )
            function_declarations.append(func_decl)

        return [Tool(function_declarations=function_declarations)]

    def _build_contents(self, messages: list[dict]) -> list[dict]:
        """Build Gemini content format from messages."""
        contents = []

        for msg in messages:
            role = msg["role"]
            if role == "user":
                contents.append({"role": "user", "parts": [msg["content"]]})
            elif role == "model" or role == "assistant":
                contents.append({"role": "model", "parts": [msg["content"]]})
            elif role == "function":
                contents.append({
                    "role": "function",
                    "parts": [{
                        "function_response": {
                            "name": msg["name"],
                            "response": {"result": msg["content"]}
                        }
                    }]
                })

        return contents

    def generate_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        parent_trace: Any = None
    ) -> dict:
        """
        Generate a response with function calling.

        Returns:
            dict with either:
            - 'content': text response (final answer)
            - 'function_call': {"name": "...", "arguments": {...}}
        """
        try:
            gemini_tools = self._convert_tools_to_gemini_format(tools)

            model_with_tools = genai.GenerativeModel(
                self.model_name,
                system_instruction=system_prompt,
                tools=gemini_tools
            )

            contents = self._build_contents(messages)

            tool_config = content_types.to_tool_config({
                "function_calling_config": {"mode": "AUTO"}
            })

            response = model_with_tools.generate_content(
                contents,
                tool_config=tool_config
            )

            candidate = response.candidates[0]
            part = candidate.content.parts[0]

            if hasattr(part, 'function_call') and part.function_call.name:
                func_call = part.function_call
                result = {
                    "function_call": {
                        "name": func_call.name,
                        "arguments": dict(func_call.args) if func_call.args else {}
                    }
                }
            elif hasattr(part, 'text') and part.text:
                result = {"content": part.text}
            else:
                try:
                    result = {"content": response.text}
                except Exception:
                    result = {"content": "I was unable to generate a response."}

            return result

        except Exception as e:
            raise

    def create_trace(self, name: str, user_id: str | None = None, metadata: dict | None = None):
        """
        Create a new trace for an agent run using Langfuse v3 API.

        Returns:
            TraceContext object for managing the trace
        """
        return TraceContext(self.langfuse, name, user_id, metadata)

    def flush(self):
        """Flush pending Langfuse events."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                self.langfuse.flush()
            except Exception:
                pass


class TraceContext:
    """Context manager for Langfuse traces using v3 API."""

    def __init__(self, langfuse, name: str, user_id: str | None = None, metadata: dict | None = None):
        self.langfuse = langfuse
        self.name = name
        self.user_id = user_id
        self.metadata = metadata or {}
        self._observation = None
        self._trace_url = None

    def span(self, name: str = "", metadata: dict | None = None):
        """Create a span within this trace."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                obs = self.langfuse.start_as_current_observation(
                    as_type="span",
                    name=name,
                    metadata=metadata or {}
                )
                return SpanContext(obs)
            except Exception as e:
                print(f"Failed to create span: {e}")
        return DummySpan()

    def get_trace_url(self):
        """Get the URL to view this trace in Langfuse."""
        return self._trace_url


class SpanContext:
    """Context manager for Langfuse spans."""

    def __init__(self, observation):
        self.observation = observation

    def __enter__(self):
        if self.observation:
            self.observation.__enter__()
        return self

    def __exit__(self, *args):
        if self.observation:
            self.observation.__exit__(*args)

    def end(self, output: Any = None, **kwargs):
        """End the span with output."""
        if self.observation:
            try:
                self.observation.update(output=output)
            except Exception:
                pass


class DummySpan:
    """Dummy span when Langfuse is not available."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def end(self, **kwargs):
        pass
