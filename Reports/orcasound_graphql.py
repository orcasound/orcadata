"""GraphQL query builder for Orcasound API."""

from typing import Any, Dict, Optional

# GraphQL query for fetching candidates with detections
CANDIDATES_QUERY = """
query candidates($filter: CandidateFilterInput, $limit: Int, $offset: Int, $sort: [CandidateSortInput]) {
  candidates(filter: $filter, limit: $limit, offset: $offset, sort: $sort) {
    count
    hasNextPage
    results {
      id
      minTime
      maxTime
      category
      detectionCount
      visible
      feed {
        id
        slug
        name
        nodeName
      }
      detections {
        id
        category
        description
        listenerCount
        playlistTimestamp
        playerOffset
        timestamp
        visible
        sourceIp
        source
        feedId
      }
    }
  }
}
"""


def build_query_variables(
    offset: int = 0,
    limit: int = 1000,
    category: Optional[str] = None,
    feed_slug: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build GraphQL query variables.

    Args:
        offset: Pagination offset
        limit: Number of records per batch
        category: Optional category filter (WHALE, VESSEL, OTHER)
        feed_slug: Optional feed slug filter

    Returns:
        Variables dictionary for GraphQL query
    """
    variables: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "sort": [{"field": "MIN_TIME", "order": "DESC"}],
    }

    # Build filter object
    filter_obj: Dict[str, Any] = {}

    if category:
        filter_obj["category"] = {"eq": category.upper()}

    if feed_slug:
        filter_obj["feed"] = {"slug": {"eq": feed_slug}}

    if filter_obj:
        variables["filter"] = filter_obj

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
