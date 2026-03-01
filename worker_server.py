from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import json
from notion_worker_tool import discover_facilities_for_hotel

app = FastAPI(title="Hotel Facilities Discovery Worker")

# Discovery manifest
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
                    "facilities_data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "synonyms": {"type": "array", "items": {"type": "string"}}
                            }
                        },
                        "description": "List of facility objects containing the canonical name and synonyms."
                    },
                    "existing_facilities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of facility names already linked to the hotel."
                    },
                    "hotel_name": {
                        "type": "string",
                        "description": "Optional: Name of the hotel for debugging and evidence tracking."
                    }
                },
                "required": ["website_url", "facilities_data"]
            }
        }
    ]
}

class FacilityInput(BaseModel):
    name: str
    synonyms: List[str]

class ToolInput(BaseModel):
    website_url: str
    facilities_data: List[FacilityInput]
    existing_facilities: Optional[List[str]] = []
    hotel_name: Optional[str] = None

@app.get("/.well-known/notion-tools.json")
async def discovery():
    return DISCOVERY_MANIFEST

@app.post("/tools/discover_facilities_for_hotel")
async def run_tool(input_data: ToolInput):
    # Convert Pydantic models to dicts for the core logic
    facilities_data_dict = [f.dict() for f in input_data.facilities_data]

    result = discover_facilities_for_hotel(
        website_url=input_data.website_url,
        facilities_data=facilities_data_dict,
        existing_facilities=input_data.existing_facilities,
        hotel_name=input_data.hotel_name
    )

    if "error" in result:
        # We still return 200 but include the error in the body as per tool convention
        return result

    return result

if __name__ == "__main__":
    import uvicorn
    # Defaulting to 0.0.0.0:3000 as requested for live preview/worker access
    uvicorn.run(app, host="0.0.0.0", port=3000)
