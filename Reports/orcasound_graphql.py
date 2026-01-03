"""GraphQL query builder for Orcasound API."""

from typing import Any, Dict, List, Optional

# GraphQL endpoint (NOT graphiql)
GRAPHQL_ENDPOINT = "https://live.orcasound.net/graphql"

# GraphQL query for fetching detections directly (preferred, per task requirements)
DETECTIONS_QUERY = """
query detections($filter: DetectionFilterInput, $limit: Int, $offset: Int, $sort: [DetectionSortInput]) {
  detections(filter: $filter, limit: $limit, offset: $offset, sort: $sort) {
    count
    hasNextPage
    lastPage
    pageNumber
    limit
    results {
      id
      timestamp
      source
      category
      feedId
      playlistTimestamp
      playerOffset
      description
      listenerCount
      visible
      feed {
        id
        name
        slug
        nodeName
      }
    }
  }
}
"""


def build_detection_query_variables(
    offset: int = 0,
    limit: int = 1000,
    include_machine: bool = False,
    category: Optional[str] = None,
    feed_id: Optional[str] = None,
    timestamp_gte: Optional[str] = None,
    timestamp_lt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build GraphQL query variables for Detection query.

    Args:
        offset: Pagination offset
        limit: Number of records per batch
        include_machine: If False, filter to HUMAN source only
        category: Optional category filter (WHALE, VESSEL, OTHER)
        feed_id: Optional feed ID filter
        timestamp_gte: ISO timestamp for greaterThanOrEqual filter
        timestamp_lt: ISO timestamp for lessThan filter

    Returns:
        Variables dictionary for GraphQL query
    """
    variables: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "sort": [{"field": "TIMESTAMP", "order": "DESC"}],
    }

    # Build filter object
    filter_conditions: List[Dict[str, Any]] = []

    # Source filter (default to HUMAN only)
    if not include_machine:
        filter_conditions.append({"source": {"eq": "HUMAN"}})

    # Category filter
    if category:
        filter_conditions.append({"category": {"eq": category.upper()}})

    # Feed filter
    if feed_id:
        filter_conditions.append({"feedId": {"eq": feed_id}})

    # Timestamp filters
    if timestamp_gte:
        filter_conditions.append({"timestamp": {"greaterThanOrEqual": timestamp_gte}})

    if timestamp_lt:
        filter_conditions.append({"timestamp": {"lessThan": timestamp_lt}})

    # Combine with AND if multiple conditions
    if filter_conditions:
        if len(filter_conditions) == 1:
            variables["filter"] = filter_conditions[0]
        else:
            variables["filter"] = {"and": filter_conditions}

    return variables


def execute_graphql_query(
    session, endpoint: str, query: str, variables: Dict[str, Any], timeout: int = 30
) -> Dict[str, Any]:
    """
    Execute GraphQL query and handle errors.

    Args:
        session: HTTP session
        endpoint: GraphQL endpoint URL
        query: GraphQL query string
        variables: Query variables
        timeout: Request timeout

    Returns:
        Response data dictionary

    Raises:
        ValueError: If response contains errors or no data
    """
    payload = {"query": query, "variables": variables}

    response = session.post(endpoint, json=payload, timeout=timeout)
    response.raise_for_status()

    data = response.json()

    # Check for GraphQL errors
    if "errors" in data:
        error_messages = [error.get("message", str(error)) for error in data["errors"]]
        raise ValueError(f"GraphQL errors: {', '.join(error_messages)}")

    # Check for data
    if "data" not in data:
        raise ValueError("No data in GraphQL response")

    return data["data"]
