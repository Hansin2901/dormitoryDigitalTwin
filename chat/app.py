"""Streamlit chat interface for Dormitory Digital Twin.

Run with: uv run streamlit run chat/app.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from chat.agents import PlannerAgent, AgentResponse, AgentStep


def display_step(step: AgentStep, index: int):
    """Display a single agent reasoning step."""
    if step.tool_name == "execute_cypher":
        tool_label = "Neo4j (Cypher)"
        lang = "cypher"
    elif step.tool_name == "execute_sql":
        tool_label = "InfluxDB (SQL)"
        lang = "sql"
    else:
        tool_label = step.tool_name or "Thinking"
        lang = "text"

    with st.expander(f"Step {index + 1}: {tool_label}", expanded=False):
        if step.thought:
            st.markdown(f"**Thought:** {step.thought}")

        if step.tool_name and step.tool_input:
            st.markdown(f"**Query:**")
            st.code(step.tool_input.get("query", str(step.tool_input)), language=lang)

            if step.tool_result:
                st.markdown("**Result:**")
                if step.tool_result.get("success"):
                    data = step.tool_result.get("data", [])
                    if data:
                        # Convert complex objects to strings for display
                        df = pd.DataFrame(data)
                        for col in df.columns:
                            df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (dict, list)) else x)
                        st.dataframe(df, width="stretch")
                    else:
                        st.info("No results returned")
                else:
                    st.error(step.tool_result.get("error", "Unknown error"))


def display_agent_response(response: AgentResponse):
    """Display the agent's reasoning steps and final answer."""
    # Show reasoning steps in expandable sections
    if response.steps:
        st.markdown("##### Reasoning Steps")
        for i, step in enumerate(response.steps):
            display_step(step, i)
        st.divider()

    # Show final answer
    st.markdown(response.final_answer)

    # Show link to Langfuse trace
    if response.trace_url:
        st.caption(f"[View full trace in Langfuse]({response.trace_url})")


def init_agent():
    """Initialize the agent, handling missing API keys gracefully."""
    try:
        return PlannerAgent()
    except ValueError as e:
        return None


def main():
    st.set_page_config(
        page_title="Dormitory Digital Twin",
        page_icon="🏢",
        layout="wide"
    )

    st.title("Dormitory Digital Twin")
    st.caption("Ask questions about the building, sensors, and equipment")

    # Sidebar with example queries and info
    with st.sidebar:
        st.markdown("### Example Questions")

        st.markdown("**Graph queries** (Neo4j)")
        if st.button("Which AC unit services room 103?", key="ex1"):
            st.session_state.pending_query = "Which AC unit services room 103?"
        if st.button("What sensors are installed in room 101?", key="ex2"):
            st.session_state.pending_query = "What sensors are installed in room 101?"
        if st.button("What rooms are serviced by which Air Conditioning Units?", key="ex3"):
            st.session_state.pending_query = "What rooms are serviced by which Air Conditioning Units?"

        st.markdown("**Time-series queries** (InfluxDB)")
        if st.button("What's the latest temperature in room 105?", key="ex4"):
            st.session_state.pending_query = "What's the latest temperature in room 105?"
        if st.button("What are the typical occupancy patterns for the dorms?", key="ex5"):
            st.session_state.pending_query = "What are the typical occupancy patterns for the dorms?"
        if st.button("Which room has the highest temperature recently?", key="ex6"):
            st.session_state.pending_query = "Which room has the highest temperature in the most recent readings?"

        st.markdown("**Hybrid queries**")
        if st.button("Which occupied rooms are over 25°C?", key="ex7"):
            st.session_state.pending_query = "Which occupied rooms have temperatures above 25°C?"
        if st.button("Show all rooms with their latest temperatures", key="ex8"):
            st.session_state.pending_query = "Show me all rooms with their latest temperatures"
        if st.button("What times of day are we observing hot temperatures?", key="ex9"):
            st.session_state.pending_query = "What times of day are we observing hot temperatures? In which dorm rooms? Are these rooms related to an Air Conditioning Unit?"

        st.markdown("**Graceful failure tests**")
        if st.button("What's the temperature in room 999?", key="ex10"):
            st.session_state.pending_query = "What's the temperature in room 999?"
        if st.button("Delete all temperature readings", key="ex11"):
            st.session_state.pending_query = "Delete all temperature readings"

        st.divider()
        st.markdown("### About")
        st.markdown("""
        This assistant can query:
        - **Neo4j** for building topology (rooms, AC units, sensors, relationships)
        - **InfluxDB** for sensor time-series data (temperature, occupancy)

        All queries are traced in Langfuse for observability.
        """)

    # Initialize agent in session state
    if "agent" not in st.session_state:
        st.session_state.agent = init_agent()

    # Check if agent initialized successfully
    if st.session_state.agent is None:
        st.error("⚠️ Missing API keys. Please set GEMINI_API_KEY in your .env file.")
        st.code("""
# Add to your .env file:
GEMINI_API_KEY=your_gemini_api_key

# Optional for Langfuse tracing:
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
        """)
        return

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "response" in message:
                display_agent_response(message["response"])
            else:
                st.write(message["content"])

    # Handle pending query from sidebar buttons
    pending_query = st.session_state.pop("pending_query", None)

    # Chat input
    prompt = st.chat_input("Ask about the building...")

    # Use pending query if set, otherwise use chat input
    query = pending_query or prompt

    if query:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": query})

        with st.chat_message("user"):
            st.write(query)

        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.agent.run(query)
                display_agent_response(response)

                # Add to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response.final_answer,
                    "response": response
                })


if __name__ == "__main__":
    main()
