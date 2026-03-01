import os
import time
import sys
import json
import logging
from datetime import datetime
from notion_client import Client
from notion_worker_tool import discover_facilities_for_hotel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment variables
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
HOTELS_DB_ID = os.getenv("HOTELS_DB_ID")
FACILITIES_DB_ID = os.getenv("FACILITIES_DB_ID")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "ultimatefamilyhotels@gmail.com")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "ultimatefamilyhotels@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Exact property names in Notion
HOTEL_WEBSITE_PROP = "Website"
HOTEL_FACILITIES_RELATION_PROP = "🛝\xa0 Facilities & Amenities"
HOTEL_UPDATE_DATE_PROP = "Amenities last updated"
FACILITY_NAME_PROP = "facilityname"
FACILITY_ALT_TEXT_PROP = "Alt Text"

if not NOTION_TOKEN or not HOTELS_DB_ID or not FACILITIES_DB_ID:
    logger.error("Missing required environment variables: NOTION_TOKEN, HOTELS_DB_ID, or FACILITIES_DB_ID")
    sys.exit(1)

notion = Client(auth=NOTION_TOKEN)

def query_database(db_id, filter=None, page_size=100):
    """
    Handles Notion database queries with a fallback for environment-specific behaviors.
    """
    try:
        db = notion.databases.retrieve(database_id=db_id)
        # Handle specific 'data_sources' artifact if present in this environment
        if hasattr(notion, 'data_sources') and 'data_sources' in db and db['data_sources']:
            ds_id = db['data_sources'][0]['id']
            endpoint = notion.data_sources
            query_key = "data_source_id"
            target_id = ds_id
        else:
            endpoint = notion.databases
            query_key = "database_id"
            target_id = db_id

        results = []
        start_cursor = None
        while True:
            kwargs = {query_key: target_id, "page_size": page_size, "start_cursor": start_cursor}
            if filter:
                kwargs["filter"] = filter

            response = endpoint.query(**kwargs)
            results.extend(response['results'])

            if not response.get('has_more'):
                break
            start_cursor = response.get('next_cursor')
        return results
    except Exception as e:
        logger.error(f"Error querying database {db_id}: {e}")
        raise

def get_all_facilities():
    pages = query_database(FACILITIES_DB_ID)
    facilities = []
    for page in pages:
        props = page['properties']
        name = props[FACILITY_NAME_PROP]['title'][0]['plain_text'] if props[FACILITY_NAME_PROP]['title'] else ""

        synonyms = []
        if props[FACILITY_ALT_TEXT_PROP]['rich_text']:
            raw_synonyms = props[FACILITY_ALT_TEXT_PROP]['rich_text'][0]['plain_text']
            synonyms = [s.strip() for s in raw_synonyms.split(',') if s.strip()]

        facilities.append({
            "id": page['id'],
            "name": name,
            "synonyms": synonyms
        })
    return facilities

def get_all_hotels():
    pages = query_database(HOTELS_DB_ID)
    hotels = []
    for page in pages:
        props = page['properties']
        website = props[HOTEL_WEBSITE_PROP]['url']

        hotel_name = "Unnamed Hotel"
        for prop_data in props.values():
            if prop_data['type'] == 'title' and prop_data['title']:
                hotel_name = prop_data['title'][0]['plain_text']
                break

        existing_facility_ids = [rel['id'] for rel in props[HOTEL_FACILITIES_RELATION_PROP]['relation']]

        hotels.append({
            "id": page['id'],
            "name": hotel_name,
            "website": website,
            "existing_facility_ids": existing_facility_ids
        })
    return hotels

def send_email_report(successes, failures):
    if not EMAIL_PASSWORD:
        logger.warning("EMAIL_PASSWORD not set. Skipping report email.")
        return

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = "Hotel Facilities Sync Report"

    body = "The Hotel Facilities Sync process has completed.\n\nSUCCESSFULLY PROCESSED:\n"
    for hotel, count in successes:
        body += f"- {hotel}: {count} total facilities\n"

    body += "\nFAILED / SKIPPED:\n"
    for hotel, reason in failures:
        body += f"- {hotel}: {reason}\n"

    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info("Email report sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send email report: {e}")

def main():
    logger.info("Starting production hotel facilities sync...")

    successes = []
    failures = []

    try:
        facilities_data = get_all_facilities()
        logger.info(f"Fetched {len(facilities_data)} facilities from Notion.")

        facility_name_to_id = {f['name']: f['id'] for f in facilities_data}
        facility_id_to_name = {f['id']: f['name'] for f in facilities_data}

        hotels = get_all_hotels()
        logger.info(f"Fetched {len(hotels)} hotels from Notion.")
    except Exception as e:
        logger.critical(f"Failed to initialize sync: {e}")
        sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")

    for hotel in hotels:
        if not hotel['website']:
            failures.append((hotel['name'], "No website URL in Notion"))
            continue

        existing_names = [facility_id_to_name.get(fid) for fid in hotel['existing_facility_ids'] if fid in facility_id_to_name]

        discovery_result = discover_facilities_for_hotel(
            website_url=hotel['website'],
            facilities_data=facilities_data,
            existing_facilities=existing_names,
            hotel_name=hotel['name']
        )

        if "error" in discovery_result:
            failures.append((hotel['name'], discovery_result['error']))
            continue

        matched_names = discovery_result['matched_facilities']
        matched_ids = set(hotel['existing_facility_ids'])
        newly_matched_count = 0

        for name in matched_names:
            fid = facility_name_to_id.get(name)
            if fid and fid not in matched_ids:
                matched_ids.add(fid)
                newly_matched_count += 1

        if newly_matched_count > 0:
            try:
                notion.pages.update(
                    page_id=hotel['id'],
                    properties={
                        HOTEL_FACILITIES_RELATION_PROP: {"relation": [{"id": fid} for fid in matched_ids]},
                        HOTEL_UPDATE_DATE_PROP: {"date": {"start": today}}
                    }
                )
                successes.append((hotel['name'], len(matched_ids)))
                logger.info(f"Updated {hotel['name']} with {newly_matched_count} new facilities.")
            except Exception as e:
                failures.append((hotel['name'], f"Notion update error: {e}"))
        else:
            successes.append((hotel['name'], len(matched_ids)))

        time.sleep(0.5)

    send_email_report(successes, failures)

if __name__ == "__main__":
    main()
