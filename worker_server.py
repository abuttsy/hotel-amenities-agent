import os
import sys
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import json
from notion_worker_tool import discover_facilities_for_hotel

# Validate required environment variables on startup
if not os.getenv("NOTION_TOKEN"):
    print("FATAL: NOTION_TOKEN environment variable is missing.")
    sys.exit(1)
if not os.getenv("FACILITIES_DB_ID"):
    print("FATAL: FACILITIES_DB_ID environment variable is missing.")
    sys.exit(1)

app = FastAPI(title="Hotel Facilities Discovery Worker")

# Discovery manifest matching the provided contract
DISCOVERY_MANIFEST = {
    "tools": [
        {
            "name": "discover_facilities_for_hotel",
            "description": "Scrapes a hotel website to discover which facilities from a provided list are offered. Checks page text, meta descriptions, and image alt tags.",
            "input_schema": {
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

class ToolInput(BaseModel):
    website_url: str
    facilities: List[str]
    existing_facilities: Optional[List[str]] = []
    hotel_name: Optional[str] = None

@app.get("/.well-known/notion-tools.json")
async def discovery():
    return DISCOVERY_MANIFEST

@app.post("/tools/discover_facilities_for_hotel")
async def run_tool(input_data: ToolInput):
    result = discover_facilities_for_hotel(
        website_url=input_data.website_url,
        facilities=input_data.facilities,
        existing_facilities=input_data.existing_facilities,
        hotel_name=input_data.hotel_name
    )
    return result

if __name__ == "__main__":
    import uvicorn
    # Railway/Render provide the PORT environment variable
    port = int(os.getenv("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
