"""InfluxDB query execution tool."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db import InfluxClient
from chat.validators import validate_sql_query, QueryValidationError


def execute_sql(query: str) -> dict:
    """
    Execute a SQL query against InfluxDB.

    Args:
        query: SQL query string

    Returns:
        dict with keys:
        - 'success': bool
        - 'data': list of records (if success)
        - 'error': error message (if failure)
    """
    try:
        # Validate query is read-only
        validate_sql_query(query)

        # Execute query
        with InfluxClient() as client:
            result = client.query(query)

            # Convert to list of dicts for JSON serialization
            df = result.to_pandas()

            # Handle timestamp columns
            for col in df.columns:
                if df[col].dtype == 'datetime64[ns]' or 'time' in col.lower():
                    df[col] = df[col].astype(str)

            records = df.to_dict(orient='records')

        return {
            "success": True,
            "data": records,
            "row_count": len(records)
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
