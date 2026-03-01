import os
import sys
import json
import logging
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from notion_worker_tool import discover_facilities_for_hotel, get_notion_facilities

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Validate required environment variables on startup
if not os.getenv("NOTION_TOKEN"):
    logger.error("FATAL: NOTION_TOKEN environment variable is missing.")
    sys.exit(1)
if not os.getenv("FACILITIES_DB_ID"):
    logger.error("FATAL: FACILITIES_DB_ID environment variable is missing.")
    sys.exit(1)

# Initialize FastMCP
mcp = FastMCP("Hotel Facilities Discovery")

@mcp.tool()
async def discover_facilities(website_url: str, facilities: List[str], existing_facilities: Optional[List[str]] = None, hotel_name: Optional[str] = None) -> str:
    """
    Scrapes a hotel website to discover which facilities from a provided list are offered.
    Checks page text, meta descriptions, and image alt tags.
    """
    result = discover_facilities_for_hotel(
        website_url=website_url,
        facilities=facilities,
        existing_facilities=existing_facilities,
        hotel_name=hotel_name
    )
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        # 1. Create the discovery JSON (The 'Map' for Notion)
        # This tells Notion exactly what 'discover_facilities' does
        notion_config = {
            "tools": [
                {
                    "name": "discover_facilities",
                    "description": "Scrapes a hotel website to discover which facilities from a provided list are offered. Checks page text, meta descriptions, and image alt tags.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "website_url": {
                                "type": "string",
                                "description": "The URL of the hotel website to scrape."
                            },
                            "facilities": {
                                "type": "array",
                                "items": { "type": "string" },
                                "description": "List of canonical facility names to search for."
                            },
                            "existing_facilities": {
                                "type": "array",
                                "items": { "type": "string" },
                                "description": "Optional: List of facility names already linked to the hotel."
                            },
                            "hotel_name": {
                                "type": "string",
                                "description": "Optional: Name of the hotel for debugging and evidence."
                            }
                        },
                        "required": ["website_url", "facilities"]
                    }
                }
            ]
        }

        # 2. Add a special route so Notion can find this map
        @mcp.external_route("/.well-known/notion-tools.json", methods=["GET"])
        async def discovery_endpoint(request):
            return JSONResponse(notion_config)

        # 3. Run the server on the port Railway expects
        port = int(os.getenv("PORT", 8080))
        logger.info(f"Starting MCP Server on port {port}...")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
