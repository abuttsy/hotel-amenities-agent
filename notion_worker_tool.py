import requests
from bs4 import BeautifulSoup
import re
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def scrape_website_with_sources(url):
    """
    Scrapes the given URL for visible text, image alt tags, and meta description.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
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

def discover_facilities_for_hotel(website_url, facilities_data, existing_facilities=None, hotel_name=None):
    """
    Core logic to discover facilities for a given hotel website.

    :param website_url: The URL of the hotel website to scrape.
    :param facilities_data: List of dicts, each with 'name' and 'synonyms' (from Alt Text property).
    :param existing_facilities: List of facility names already linked.
    :param hotel_name: Optional name for logging purposes.
    :return: Dict with matched_facilities, evidence, and hotel_name.
    """
    logger.info(f"Discovering facilities for {hotel_name or 'unnamed hotel'} at {website_url}")

    sources, error = scrape_website_with_sources(website_url)
    if error:
        return {"error": f"Failed to scrape {website_url}: {error}"}

    existing_set = set(existing_facilities or [])
    matched_names = []
    evidence = {}

    for facility in facilities_data:
        name = facility['name']
        if name in existing_set:
            continue

        # Compile all search terms (canonical name + synonyms from Alt Text)
        synonyms = facility.get('synonyms', [])
        search_terms = list(set([name] + synonyms))

        for term in search_terms:
            if not term: continue
            # Match with word boundaries and optional pluralization
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
            # For the standalone tool, we expect 'facilities_data' to be provided
            result = discover_facilities_for_hotel(
                website_url=input_json.get("website_url"),
                facilities_data=input_json.get("facilities_data", []),
                existing_facilities=input_json.get("existing_facilities", []),
                hotel_name=input_json.get("hotel_name")
            )
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
