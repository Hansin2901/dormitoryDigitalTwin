"""System prompts for the chat agents."""

from .planner import PLANNER_SYSTEM_PROMPT
from .neo4j import NEO4J_SYSTEM_PROMPT, NEO4J_EXAMPLES
from .influx import INFLUX_SYSTEM_PROMPT, INFLUX_EXAMPLES

__all__ = [
    "PLANNER_SYSTEM_PROMPT",
    "NEO4J_SYSTEM_PROMPT",
    "NEO4J_EXAMPLES",
    "INFLUX_SYSTEM_PROMPT",
    "INFLUX_EXAMPLES",
]
