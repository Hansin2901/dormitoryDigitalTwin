"""Neo4j query execution tool."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db import Neo4jClient
from chat.validators import validate_cypher_query, QueryValidationError


def execute_cypher(query: str) -> dict:
    """
    Execute a Cypher query against Neo4j.

    Args:
        query: Cypher query string

    Returns:
        dict with keys:
        - 'success': bool
        - 'data': list of records (if success)
        - 'error': error message (if failure)
    """
    try:
        # Validate query is read-only
        validate_cypher_query(query)

        # Execute query
        with Neo4jClient() as client:
            results = client.run_query(query)

        return {
            "success": True,
            "data": results,
            "row_count": len(results)
        }

    except QueryValidationError as e:
        return {
            "success": False,
            "error": f"Validation error: {str(e)}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Query execution error: {str(e)}"
        }
