import os
import requests
from bs4 import BeautifulSoup
import re
import json
import logging
from notion_client import Client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache for facilities data to avoid redundant Notion API calls
_facilities_cache = None

def scrape_website_with_sources(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()

        text_content = soup.get_text(separator=' ', strip=True).lower()
        alt_texts = [img.get('alt', '').lower() for img in soup.find_all('img') if img.get('alt')]

        meta_description = ""
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        if meta_desc_tag and meta_desc_tag.get('content'):
            meta_description = meta_desc_tag['content'].lower()

        return {
            "text": text_content,
            "alt": " ".join(alt_texts),
            "meta": meta_description
        }, None
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return None, str(e)

def get_notion_facilities():
    """
    Fetches facilities and their Alt Text synonyms from Notion.
    """
    global _facilities_cache
    if _facilities_cache:
        return _facilities_cache

    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("FACILITIES_DB_ID")
    if not token or not db_id:
        logger.error("Missing NOTION_TOKEN or FACILITIES_DB_ID for synonym lookup.")
        return []

    notion = Client(auth=token)
    try:
        # Check for data_sources fallback
        db = notion.databases.retrieve(database_id=db_id)
        if hasattr(notion, 'data_sources') and 'data_sources' in db and db['data_sources']:
            endpoint = notion.data_sources
            query_kwargs = {"data_source_id": db['data_sources'][0]['id']}
        else:
            endpoint = notion.databases
            query_kwargs = {"database_id": db_id}

        results = []
        start_cursor = None
        while True:
            response = endpoint.query(start_cursor=start_cursor, **query_kwargs)
            results.extend(response['results'])
            if not response.get('has_more'): break
            start_cursor = response.get('next_cursor')

        facilities_data = []
        for page in results:
            props = page['properties']
            name = props['facilityname']['title'][0]['plain_text'] if props.get('facilityname') and props['facilityname']['title'] else ""
            synonyms = []
            if props.get('Alt Text') and props['Alt Text']['rich_text']:
                synonyms = [s.strip() for s in props['Alt Text']['rich_text'][0]['plain_text'].split(',') if s.strip()]

            facilities_data.append({"name": name, "synonyms": synonyms})

        _facilities_cache = facilities_data
        return facilities_data
    except Exception as e:
        logger.error(f"Failed to fetch synonyms from Notion: {e}")
        return []

def discover_facilities_for_hotel(website_url, facilities=None, existing_facilities=None, hotel_name=None):
    """
    Exposed logic for discovery. If 'facilities' list of strings is provided, it uses them.
    Otherwise, it fetches them from Notion.
    """
    sources, error = scrape_website_with_sources(website_url)
    if error:
        return {"error": f"Failed to scrape {website_url}: {error}"}

    # Fetch synonyms from Notion if possible
    all_facilities_data = get_notion_facilities()

    # If the user provided a subset of facilities to check, filter the data
    if facilities:
        facilities_to_check = [f for f in all_facilities_data if f['name'] in facilities]
    else:
        facilities_to_check = all_facilities_data

    existing_set = set(existing_facilities or [])
    matched_names = []
    evidence = {}

    for facility in facilities_to_check:
        name = facility['name']
        if name in existing_set:
            continue

        search_terms = list(set([name] + facility.get('synonyms', [])))

        for term in search_terms:
            if not term: continue
            pattern = r'\b' + re.escape(term.lower()) + r'(s|es)?\b'

            found_in = []
            if re.search(pattern, sources['text']): found_in.append("page text")
            if re.search(pattern, sources['alt']): found_in.append("image alt tags")
            if re.search(pattern, sources['meta']): found_in.append("meta description")

            if found_in:
                matched_names.append(name)
                evidence[name] = f"Found via term '{term}' in: {', '.join(found_in)}"
                break

    return {
        "hotel_name": hotel_name,
        "matched_facilities": matched_names,
        "evidence": evidence
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            input_json = json.loads(sys.argv[1])
            result = discover_facilities_for_hotel(
                website_url=input_json.get("website_url"),
                facilities=input_json.get("facilities"),
                existing_facilities=input_json.get("existing_facilities"),
                hotel_name=input_json.get("hotel_name")
            )
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
