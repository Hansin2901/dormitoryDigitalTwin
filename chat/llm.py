"""Gemini LLM client wrapper with function calling and optional Langfuse tracing."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from contextlib import contextmanager
from typing import Any, Generator

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.generativeai.types import content_types
from dotenv import load_dotenv

load_dotenv()

# Initialize Langfuse v3 client
LANGFUSE_AVAILABLE = False
langfuse_client = None

try:
    from langfuse import get_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if public_key and secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        # Support both LANGFUSE_HOST (legacy) and LANGFUSE_BASE_URL (official)
        host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
        if host:
            os.environ["LANGFUSE_HOST"] = host
            os.environ["LANGFUSE_BASE_URL"] = host

        langfuse_client = get_client()

        # Verify authentication
        try:
            if langfuse_client.auth_check():
                LANGFUSE_AVAILABLE = True
                print("Langfuse tracing enabled")
            else:
                print("Langfuse authentication failed - tracing disabled")
        except Exception as auth_err:
            print(f"Langfuse authentication error: {auth_err}")
except Exception as e:
    print(f"Langfuse not available: {e}")


class GeminiClient:
    """Wrapper for Google Gemini API with function calling and optional Langfuse tracing."""

    def __init__(self, model: str = "gemini-3-flash-preview"):
        """Initialize the Gemini client."""
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
        """Generate a response with function calling."""
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

            # Check for empty response
            if not response.candidates:
                print(f"[LLM] Warning: No candidates in response")
                # Check if there's a prompt feedback (safety block, etc.)
                if hasattr(response, 'prompt_feedback'):
                    print(f"[LLM] Prompt feedback: {response.prompt_feedback}")
                return {"content": "I was unable to generate a response. The model returned no candidates."}

            candidate = response.candidates[0]

            # Check for finish reason that might indicate an issue
            if hasattr(candidate, 'finish_reason'):
                print(f"[LLM] Finish reason: {candidate.finish_reason}")

            # Check for empty content
            if not hasattr(candidate, 'content') or not candidate.content:
                print(f"[LLM] Warning: No content in candidate")
                return {"content": "I was unable to generate a response. The model returned empty content."}

            # Check for empty parts
            if not candidate.content.parts:
                print(f"[LLM] Warning: No parts in content")
                return {"content": "I was unable to generate a response. The model returned no parts."}

            part = candidate.content.parts[0]

            if hasattr(part, 'function_call') and part.function_call.name:
                func_call = part.function_call
                print(f"[LLM] Function call: {func_call.name}")
                return {
                    "function_call": {
                        "name": func_call.name,
                        "arguments": dict(func_call.args) if func_call.args else {}
                    }
                }
            elif hasattr(part, 'text') and part.text:
                print(f"[LLM] Text response: {part.text[:100]}...")
                return {"content": part.text}
            else:
                try:
                    return {"content": response.text}
                except Exception:
                    return {"content": "I was unable to generate a response."}

        except Exception as e:
            print(f"[LLM] Error in generate_with_tools: {e}")
            import traceback
            traceback.print_exc()
            raise

    def create_trace(self, name: str, user_id: str | None = None, metadata: dict | None = None, input_data: Any = None):
        """Create a trace context for an agent run."""
        return TraceContext(self.langfuse, name, user_id, metadata, input_data)

    def flush(self):
        """Flush pending Langfuse events."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                self.langfuse.flush()
            except Exception:
                pass


class TraceContext:
    """
    Wrapper for Langfuse trace using v3 API.

    In Langfuse v3, tracing uses OpenTelemetry-style context managers.
    The proper pattern is:
        with client.start_as_current_span(name="root") as root:
            with client.start_as_current_span(name="child") as child:
                # work here
    """

    def __init__(self, langfuse, name: str, user_id: str | None = None, metadata: dict | None = None, input_data: Any = None):
        self.langfuse = langfuse
        self.name = name
        self.user_id = user_id
        self.metadata = metadata or {}
        self.input_data = input_data
        self._trace_id = None
        self._root_span = None
        self._root_ctx = None

    def __enter__(self):
        """Start the root span when entering context."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                self._root_ctx = self.langfuse.start_as_current_span(
                    name=self.name,
                    input=self.input_data,
                    metadata=self.metadata
                )
                self._root_span = self._root_ctx.__enter__()
                if self.user_id:
                    self._root_span.update(user_id=self.user_id)
            except Exception as e:
                print(f"Failed to start trace: {e}")
        return self

    def __exit__(self, *args):
        """End the root span when exiting context."""
        if self._root_ctx:
            try:
                self._root_ctx.__exit__(*args)
            except Exception:
                pass

    def set_output(self, output: Any):
        """Set output on the root span."""
        if self._root_span:
            try:
                self._root_span.update(output=output)
            except Exception:
                pass

    @contextmanager
    def span(self, name: str = "", input_data: Any = None, metadata: dict | None = None) -> Generator["SpanWrapper", None, None]:
        """Create a child span within the trace using context manager."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                with self.langfuse.start_as_current_span(
                    name=name,
                    input=input_data,
                    metadata=metadata or {}
                ) as span_ctx:
                    yield SpanWrapper(span_ctx)
                return
            except Exception as e:
                print(f"Failed to create span: {e}")
        yield DummySpan()

    @contextmanager
    def generation(
        self,
        name: str = "llm-call",
        model: str = "",
        input_data: Any = None,
        model_parameters: dict | None = None,
        metadata: dict | None = None
    ) -> Generator["GenerationWrapper", None, None]:
        """Create a generation observation for LLM calls."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                with self.langfuse.start_as_current_generation(
                    name=name,
                    model=model,
                    input=input_data,
                    model_parameters=model_parameters or {},
                    metadata=metadata or {}
                ) as gen_ctx:
                    yield GenerationWrapper(gen_ctx)
                return
            except Exception as e:
                print(f"Failed to create generation: {e}")
        yield DummySpan()

    @contextmanager
    def tool_span(
        self,
        name: str = "",
        input_data: Any = None,
        metadata: dict | None = None
    ) -> Generator["SpanWrapper", None, None]:
        """Create a tool observation for tool executions."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                with self.langfuse.start_as_current_observation(
                    as_type="tool",
                    name=name,
                    input=input_data,
                    metadata=metadata or {}
                ) as tool_ctx:
                    yield SpanWrapper(tool_ctx)
                return
            except Exception as e:
                print(f"Failed to create tool span: {e}")
        yield DummySpan()

    def get_trace_url(self):
        """Get URL to view trace in Langfuse."""
        if self.langfuse and LANGFUSE_AVAILABLE:
            try:
                trace_id = self.langfuse.get_current_trace_id()
                if trace_id:
                    self._trace_id = trace_id
                    host = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
                    return f"{host}/trace/{trace_id}"
            except Exception:
                pass
        return None


class SpanWrapper:
    """Wrapper for Langfuse span to provide a consistent interface."""

    def __init__(self, span):
        self._span = span

    def update(self, output: Any = None, **kwargs):
        """Update span with output or other attributes."""
        if self._span:
            try:
                self._span.update(output=output, **kwargs)
            except Exception:
                pass

    def end(self, output: Any = None, **kwargs):
        """End is a no-op in v3 API - spans end when context exits."""
        # Update with final output if provided
        if output is not None:
            self.update(output=output, **kwargs)


class GenerationWrapper:
    """Wrapper for Langfuse generation observation to provide a consistent interface."""

    def __init__(self, generation):
        self._generation = generation

    def update(self, output: Any = None, usage: dict | None = None, **kwargs):
        """Update generation with output, usage stats, or other attributes."""
        if self._generation:
            try:
                update_kwargs = {}
                if output is not None:
                    update_kwargs["output"] = output
                if usage is not None:
                    update_kwargs["usage"] = usage
                update_kwargs.update(kwargs)
                self._generation.update(**update_kwargs)
            except Exception:
                pass

    def end(self, output: Any = None, usage: dict | None = None, **kwargs):
        """End is a no-op in v3 API - generations end when context exits."""
        if output is not None or usage is not None:
            self.update(output=output, usage=usage, **kwargs)


class DummySpan:
    """Dummy span when Langfuse is not available."""

    def update(self, **kwargs):
        pass

    def end(self, **kwargs):
        pass
