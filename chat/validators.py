"""Read-only query validators for Neo4j Cypher and InfluxDB SQL."""

import re


class QueryValidationError(Exception):
    """Raised when a query fails validation."""
    pass


# Cypher keywords that indicate write operations
CYPHER_WRITE_KEYWORDS = [
    r'\bCREATE\b',
    r'\bMERGE\b',
    r'\bDELETE\b',
    r'\bDETACH\s+DELETE\b',
    r'\bREMOVE\b',
    r'\bSET\b',
    r'\bFOREACH\b',
    r'\bCALL\s*\{',  # CALL with subquery can modify
]

# SQL keywords that indicate write operations
SQL_WRITE_KEYWORDS = [
    r'\bINSERT\b',
    r'\bUPDATE\b',
    r'\bDELETE\b',
    r'\bDROP\b',
    r'\bALTER\b',
    r'\bTRUNCATE\b',
    r'\bCREATE\b',
    r'\bGRANT\b',
    r'\bREVOKE\b',
]


def validate_cypher_query(query: str) -> str:
    """
    Validate a Cypher query is read-only.

    Args:
        query: Cypher query string

    Returns:
        The query if valid

    Raises:
        QueryValidationError: If the query contains write operations
    """
    if not query or not query.strip():
        raise QueryValidationError("Query cannot be empty")

    query_upper = query.upper()

    for pattern in CYPHER_WRITE_KEYWORDS:
        if re.search(pattern, query_upper):
            keyword = re.search(pattern, query_upper).group()
            raise QueryValidationError(
                f"Write operation '{keyword}' is not allowed. Only read queries (MATCH/RETURN) are permitted."
            )

    # Ensure query has MATCH or RETURN (basic sanity check)
    if not re.search(r'\bMATCH\b|\bRETURN\b', query_upper):
        raise QueryValidationError(
            "Query must contain MATCH or RETURN clause."
        )

    return query


def validate_sql_query(query: str) -> str:
    """
    Validate a SQL query is read-only.

    Args:
        query: SQL query string

    Returns:
        The query if valid

    Raises:
        QueryValidationError: If the query contains write operations
    """
    if not query or not query.strip():
        raise QueryValidationError("Query cannot be empty")

    query_upper = query.upper()

    for pattern in SQL_WRITE_KEYWORDS:
        if re.search(pattern, query_upper):
            keyword = re.search(pattern, query_upper).group()
            raise QueryValidationError(
                f"Write operation '{keyword}' is not allowed. Only SELECT queries are permitted."
            )

    # Ensure query starts with SELECT (basic sanity check)
    query_stripped = query_upper.strip()
    if not query_stripped.startswith('SELECT'):
        raise QueryValidationError(
            "Query must be a SELECT statement."
        )

    return query
