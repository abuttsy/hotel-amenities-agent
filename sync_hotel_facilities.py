import os
import time
import sys
import json
from datetime import datetime
from notion_client import Client
from notion_worker_tool import discover_facilities_for_hotel

# Configuration from environment variables
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "ntn_F7497976754aQjBYJ7uYvrt2bOsEgRcJvJHM580GYkc7an")
HOTELS_DB_ID = os.getenv("HOTELS_DB_ID", "4c1a76c312d3402d9d83a255c3ae95aa")
FACILITIES_DB_ID = os.getenv("FACILITIES_DB_ID", "11f1beea0bb2802cbdfaf74c29c4ef15")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "ultimatefamilyhotels@gmail.com")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "ultimatefamilyhotels@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "qnjz ftif inex ipng")

# Exact property names in Notion
HOTEL_WEBSITE_PROP = "Website"
HOTEL_FACILITIES_RELATION_PROP = "🛝\xa0 Facilities & Amenities"
HOTEL_UPDATE_DATE_PROP = "Amenities last updated"
FACILITY_NAME_PROP = "facilityname"

notion = Client(auth=NOTION_TOKEN)

def get_query_source(db_id):
    db = notion.databases.retrieve(database_id=db_id)
    if hasattr(notion, 'data_sources') and 'data_sources' in db and db['data_sources']:
        return notion.data_sources, db['data_sources'][0]['id']
    return notion.databases, db_id

def get_all_facilities():
    facilities = []
    endpoint, target_id = get_query_source(FACILITIES_DB_ID)
    start_cursor = None
    while True:
        query_kwargs = {"page_size": 100, "start_cursor": start_cursor}
        if endpoint == notion.databases: query_kwargs["database_id"] = target_id
        else: query_kwargs["data_source_id"] = target_id
        response = endpoint.query(**query_kwargs)
        for page in response['results']:
            name = page['properties'][FACILITY_NAME_PROP]['title'][0]['plain_text'] if page['properties'][FACILITY_NAME_PROP]['title'] else ""
            facilities.append({"id": page['id'], "name": name})
        if not response.get('has_more'): break
        start_cursor = response.get('next_cursor')
    return facilities

def get_all_hotels():
    hotels = []
    endpoint, target_id = get_query_source(HOTELS_DB_ID)
    start_cursor = None
    while True:
        query_kwargs = {"page_size": 100, "start_cursor": start_cursor}
        if endpoint == notion.databases: query_kwargs["database_id"] = target_id
        else: query_kwargs["data_source_id"] = target_id
        response = endpoint.query(**query_kwargs)
        for page in response['results']:
            website = page['properties'][HOTEL_WEBSITE_PROP]['url']
            hotel_name = "Unnamed Hotel"
            for prop_name, prop_data in page['properties'].items():
                if prop_data['type'] == 'title' and prop_data['title']:
                    hotel_name = prop_data['title'][0]['plain_text']; break
            existing_facility_ids = [rel['id'] for rel in page['properties'][HOTEL_FACILITIES_RELATION_PROP]['relation']]
            hotels.append({
                "id": page['id'],
                "name": hotel_name,
                "website": website,
                "existing_facility_ids": existing_facility_ids
            })
        if not response.get('has_more'): break
        start_cursor = response.get('next_cursor')
    return hotels

def send_email_report(successes, failures):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    if not EMAIL_PASSWORD: return
    msg = MIMEMultipart(); msg['From'] = EMAIL_SENDER; msg['To'] = EMAIL_RECEIVER; msg['Subject'] = "Hotel Facilities Sync Report"
    body = "The Hotel Facilities Sync process has completed.\n\nSUCCESSFULLY PROCESSED:\n"
    for hotel, count in successes: body += f"- {hotel}: {count} total facilities\n"
    body += "\nFAILED / SKIPPED:\n"
    for hotel, reason in failures: body += f"- {hotel}: {reason}\n"
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(EMAIL_SENDER, EMAIL_PASSWORD); server.send_message(msg); server.quit()
        print("Email report sent successfully.")
    except Exception as e: print(f"Failed to send email report: {e}")

def main():
    if not NOTION_TOKEN: sys.exit(1)
    print("Starting sync using enhanced worker tool logic...")
    successes = []; failures = []
    try:
        facilities_data = get_all_facilities()
        facility_names = [f['name'] for f in facilities_data]
        facility_name_to_id = {f['name']: f['id'] for f in facilities_data}
        facility_id_to_name = {f['id']: f['name'] for f in facilities_data}

        hotels = get_all_hotels()
    except Exception as e: print(f"Error fetching data from Notion: {e}"); sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")

    for hotel in hotels:
        if not hotel['website']:
            failures.append((hotel['name'], "No website URL in Notion")); continue

        print(f"Processing {hotel['name']}...")
        existing_names = [facility_id_to_name.get(fid) for fid in hotel['existing_facility_ids'] if fid in facility_id_to_name]

        discovery_result = discover_facilities_for_hotel(
            website_url=hotel['website'],
            facilities=facility_names,
            existing_facilities=existing_names,
            hotel_name=hotel['name']
        )

        if "error" in discovery_result:
            failures.append((hotel['name'], f"Discovery error: {discovery_result['error']}")); continue

        matched_names = discovery_result['matched_facilities']
        matched_ids = set(hotel['existing_facility_ids'])
        newly_matched_count = 0

        for name in matched_names:
            fid = facility_name_to_id.get(name)
            if fid and fid not in matched_ids:
                matched_ids.add(fid); newly_matched_count += 1
                # print(f"  + Found {name}: {discovery_result['evidence'].get(name)}")

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
                print(f"Updated {hotel['name']} with {newly_matched_count} new facilities. Total: {len(matched_ids)}")
            except Exception as e: failures.append((hotel['name'], f"Notion update error: {e}"))
        else:
            successes.append((hotel['name'], len(matched_ids)))

        time.sleep(0.5)

    send_email_report(successes, failures)

if __name__ == "__main__": main()
