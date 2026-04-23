"""
FFL MCP Server — exposes FFL lookup tools via the Model Context Protocol.

Run with:
    python -m ffl.mcp_server.server          (stdio transport, for Claude Desktop)
    python -m ffl.mcp_server.server --sse    (SSE transport, for remote clients)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from mcp.server.fastmcp import FastMCP

from ffl.database import AsyncSessionLocal
from ffl.services.lookup import (
    get_license_types,
    lookup_by_address,
    lookup_by_zip,
    lookup_changes,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="ffl-data-service",
    instructions=(
        "Provides lookup tools for US Federal Firearms Licensees (FFLs). "
        "Use these tools to verify FFL holders at addresses, find nearby dealers, "
        "and monitor license changes or upcoming expirations."
    ),
)


@mcp.tool()
async def lookup_by_address_tool(
    street: str,
    city: str,
    state: str,
    zip_code: str | None = None,
) -> str:
    """
    Find active FFL licensees at a given US street address.

    Returns a JSON list of matching licensees. Each result includes the FFL number,
    license type (what activities are permitted), business name, and address details.
    If no exact match is found and a ZIP code is provided, returns licensees in that ZIP.

    Args:
        street: Street address (e.g. "123 Main St")
        city: City name
        state: 2-letter state abbreviation (e.g. "TX")
        zip_code: Optional 5-digit ZIP code for fallback search
    """
    async with AsyncSessionLocal() as session:
        results = await lookup_by_address(
            session, street=street, city=city, state=state, zip_code=zip_code
        )
    return json.dumps({"count": len(results), "results": results}, default=str)


@mcp.tool()
async def lookup_by_zip_tool(
    zip_code: str,
    radius_miles: float = 0.0,
) -> str:
    """
    Find all active FFL licensees in or near a given US ZIP code.

    With radius_miles=0 (default), returns only licensees whose physical address
    is in the given ZIP code. With radius_miles>0, returns all licensees within
    that radius of the ZIP centroid, ordered by distance (max 500 results).

    Args:
        zip_code: 5-digit US ZIP code
        radius_miles: Search radius in miles (0 = exact ZIP match only, max 500)
    """
    async with AsyncSessionLocal() as session:
        results = await lookup_by_zip(session, zip_code=zip_code, radius_miles=radius_miles)
    return json.dumps(
        {"zip_code": zip_code, "radius_miles": radius_miles, "count": len(results), "results": results},
        default=str,
    )


@mcp.tool()
async def check_changes_and_expirations(
    since_date: str | None = None,
    expiring_within_days: int = 90,
) -> str:
    """
    Return recent FFL license changes and upcoming expirations.

    Useful for monitoring when dealers gain/lose their license or when licenses
    are about to expire (helpful for compliance and due diligence workflows).

    Args:
        since_date: ISO date string (e.g. "2025-01-01"). Defaults to 30 days ago.
        expiring_within_days: Include licenses expiring within this many days (default 90).
    """
    parsed_date: date | None = None
    if since_date:
        try:
            parsed_date = date.fromisoformat(since_date)
        except ValueError:
            return json.dumps({"error": f"Invalid date format: {since_date!r}. Use ISO format YYYY-MM-DD."})

    async with AsyncSessionLocal() as session:
        result = await lookup_changes(
            session, since_date=parsed_date, expiring_within_days=expiring_within_days
        )
    return json.dumps(result, default=str)


@mcp.resource("ffl://license-types")
async def license_types_resource() -> str:
    """
    Reference data for all FFL license type codes (01–11).

    Returns a JSON list describing each license type: its code, name, description,
    and the specific activities it permits (e.g. sell, manufacture, import).
    Also indicates which types require a Special Occupational Tax (SOT) designation
    to handle NFA-regulated items (suppressors, short-barreled rifles, etc.).
    """
    async with AsyncSessionLocal() as session:
        types = await get_license_types(session)
    return json.dumps(types, default=str)


def run() -> None:
    import sys
    use_sse = "--sse" in sys.argv
    if use_sse:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
