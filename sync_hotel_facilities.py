import os
import requests
from bs4 import BeautifulSoup
from notion_client import Client
import time
import re
import json
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

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
FACILITY_ALT_TEXT_PROP = "Alt Text"

# Extended synonyms for thorough matching
FACILITY_SYNONYMS = {
    "Apartment Option": ["Apartments", "Suites", "Family Rooms", "Kitchenette"],
    "Direct Beach Access": ["on the beach", "beachfront", "oceanfront", "steps to the beach", "seafront"],
    "Hot Tub": ["Whirlpool", "Jacuzzi", "Hot Tub", "Hydromassage"],
    "Spa": ["Wellness", "Relaxation", "Spa Center", "Health Club"],
    "Outdoor Playground": ["Playground", "Outdoor Play", "Play Area", "Kids' Playground"],
    "Cooking Class": ["Culinary", "Cooking Workshop", "Gastronomy"],
    "Cold Tub": ["Cold Plunge", "Ice Fountain", "Cold Water Pool"],
    "Adults-only Pool": ["Adult Pool", "Quiet Pool", "18+ Pool"],
    "Ice Cream Shop": ["Gelateria", "Ice Cream Parlor", "Gelato"],
    "Game Room": ["Gaming", "Video Games", "Arcade", "Entertainment Room", "Billiards", "Pool Table"],
    "Lake": ["Lakeside", "On the lake"],
    "Steam Room": ["Steam Bath", "Turkish Bath", "Steam Sauna"],
    "Art Studio for Children": ["Art Class", "Craft Room", "Painting", "Creative Workshop"],
    "Serviced Beach": ["Beach Club", "Beach Service", "Sun loungers"],
    "Villa Option": ["Chalet", "House", "Villas", "Bungalows", "Private Residence", "Cottage"],
    "Snow Room": ["Snow Cabin", "Ice Room"],
    "Sled Rental": ["Toboggans", "Sledging", "Sleigh"],
    "Water Park": ["Aquapark", "Slides", "Water Slides"],
    "Tennis Court": ["Tennis", "Racquet Sports"],
    "Indoor Pool": ["Swimming Hall", "Indoor Swimming", "Covered Pool"],
    "Golf Course": ["Golfing", "18-hole", "9-hole", "Fairway"],
    "Live Entertainment Program": ["Live Shows", "Evening Entertainment", "Performances"],
    "Spa Treatments": ["Massages", "Facials", "Therapies", "Treatments", "Body Scrub", "Massage"],
    "Mini Golf": ["Crazy Golf", "Putting Green"],
    "Outdoor Pool": ["Open-air Pool", "Main Pool", "Infinity Pool"],
    "Bicycle Rental": ["Bikes", "Mountain Bike", "E-Bike", "Cycling", "Bicycles"],
    "Pool for Children": ["Baby Pool", "Kids Pool", "Children's Pool", "Splash Pool", "Paddling Pool"],
    "Go Kart Track": ["Bobby Car Track", "Race Car Track", "Push Car Track"],
    "Sauna": ["Finnish Sauna", "Bio Sauna", "Infrared Sauna"],
    "Theater": ["Stage", "Amphitheater", "Cinema"],
    "Fitness Center": ["Gym", "Workout", "Fitness Room", "Exercise", "Health Suite"],
    "Pet Friendly": ["Pets allowed", "Dogs allowed", "Pet-friendly"],
    "Infrared Treatment": ["Infrared Cabin", "Infrared Rays"],
    "Garden": ["Park", "Gardens", "Landscaped"],
    "Spa for Children": ["Family Spa", "Kids' Spa"],
    "Petting Zoo": ["Farm Animals", "Animal Interaction"],
    "Indoor Play Area": ["Indoor Playground", "Soft Play", "Playroom"],
    "Private Beach": ["Exclusive Beach", "Own Beach"],
    "Swimming Pond": ["Bathing Lake", "Natural Pool"],
    "Play Mud Room": ["Indoor Sandpit", "Sandbox", "Sand Play"],
    "Football Pitch": ["Soccer Field", "Football Field"],
    "Wood Workshop": ["Carpentry", "Woodwork"],
    "Excursion Offering": ["Tours", "Guided Trips", "Sightseeing"],
    "Private Pools": ["Plunge Pool", "Your own pool", "Room with pool"],
    "Padel Court": ["Padel Tennis"],
    "Beauty Salon": ["Hair Stylist", "Makeup", "Hairdresser", "Nail Salon"],
    "Campfire": ["Fire Pit", "Bonfire"],
    "Mascot": ["Character", "Hotel Mascot"],
    "Magic School": ["Magic Class", "Magician"],
    "Trampoline": ["Bouncing", "Trampolining"],
    "Wine Cellar": ["Wine Tasting", "Wine Lounge", "Vinotheque", "Sommelier"],
    "Farm": ["Farming", "Livestock"],
    "Riding Stables": ["Horse Riding", "Equestrian", "Pony"],
    "Hammam": ["Turkish Bath", "Oriental Spa"],
    "Water Playground": ["Splash Pad", "Water Play Area"],
    "Climbing Wall": ["Rock Climbing", "Bouldering"],
    "Cinema": ["Movie Theater", "Film Screenings"],
    "Ski In / Ski Out": ["Ski-to-door", "Slope-side"],
    "Bouncy Castle": ["Bounce House", "Airwalk", "Inflatable"],
    "Apple Orchard": ["Fruit trees"],
    "Kids Club": ["Children's Club", "Mini Club", "Kids' World", "Junior Club"],
    "Teen Club": ["Teens Club", "Young Adults", "Teenagers"],
    "Baby Club": ["Nursery", "Creche", "Infant Care", "Baby Care"],
    "Lazy River": ["River Pool"],
    "Hot Springs": ["Thermal Bath", "Mineral Springs"],
    "Pickleball Court": ["Pickleball"],
    "Fishing Pond": ["Fishing Lake", "Angling"]
}

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
            alt_text_list = []
            if page['properties'][FACILITY_ALT_TEXT_PROP]['rich_text']:
                alt_text_raw = page['properties'][FACILITY_ALT_TEXT_PROP]['rich_text'][0]['plain_text']
                alt_text_list = [t.strip() for t in alt_text_raw.split(',') if t.strip()]
            extra_terms = FACILITY_SYNONYMS.get(name, [])
            facilities.append({"id": page['id'], "name": name, "search_terms": list(set([name] + alt_text_list + extra_terms))})
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
            hotels.append({"id": page['id'], "name": hotel_name, "website": website, "existing_facility_ids": existing_facility_ids})
        if not response.get('has_more'): break
        start_cursor = response.get('next_cursor')
    return hotels

def scrape_website(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.extract()
        text_content = soup.get_text(separator=' ', strip=True)
        alt_texts = [img.get('alt', '') for img in soup.find_all('img') if img.get('alt')]
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_description['content'] if meta_description and meta_description.get('content') else ""
        return (text_content + " " + " ".join(alt_texts) + " " + meta_content).lower(), None
    except Exception as e: return "", str(e)

def send_email_report(successes, failures):
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
    print("Starting comprehensive hotel facilities sync...")
    successes = []; failures = []
    try:
        facilities = get_all_facilities(); hotels = get_all_hotels()
    except Exception as e: print(f"Error fetching data from Notion: {e}"); sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")

    for hotel in hotels:
        if not hotel['website']:
            failures.append((hotel['name'], "No website URL in Notion")); continue
        print(f"Processing {hotel['name']}...")
        content, error = scrape_website(hotel['website'])
        if error:
            failures.append((hotel['name'], f"Scraping error: {error}")); continue

        matched_ids = set(hotel['existing_facility_ids'])
        newly_matched_count = 0
        for facility in facilities:
            if facility['id'] in matched_ids: continue
            matched = False
            for term in facility['search_terms']:
                if term and re.search(r'\b' + re.escape(term.lower()) + r'(s|es)?\b', content):
                    matched = True; break
            if matched: matched_ids.add(facility['id']); newly_matched_count += 1

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
                print(f"Updated {hotel['name']} with {newly_matched_count} new facilities.")
            except Exception as e: failures.append((hotel['name'], f"Notion update error: {e}"))
        else:
            successes.append((hotel['name'], len(matched_ids)))
        time.sleep(0.5)

    send_email_report(successes, failures)

if __name__ == "__main__": main()
