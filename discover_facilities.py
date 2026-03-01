import requests
from bs4 import BeautifulSoup
import re
import json
import sys

# Common synonyms for thorough matching
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

def scrape_website(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.extract()
        text_content = soup.get_text(separator=' ', strip=True)
        alt_texts = [img.get('alt', '') for img in soup.find_all('img') if img.get('alt')]
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_description['content'] if meta_description and meta_description.get('content') else ""
        return (text_content + " " + " ".join(alt_texts) + " " + meta_content).lower()
    except Exception: return ""

def discover_facilities_for_hotel(hotel_website, facility_list):
    content = scrape_website(hotel_website)
    if not content: return []

    matched_facilities = []
    for facility_name in facility_list:
        search_terms = list(set([facility_name] + FACILITY_SYNONYMS.get(facility_name, [])))
        for term in search_terms:
            if term and re.search(r'\b' + re.escape(term.lower()) + r'(s|es)?\b', content):
                matched_facilities.append(facility_name)
                break
    return matched_facilities

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Expecting JSON input with "website" and "facilities"
        try:
            input_data = json.loads(sys.argv[1])
            website = input_data.get("website")
            facilities = input_data.get("facilities", [])
            results = discover_facilities_for_hotel(website, facilities)
            print(json.dumps(results))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
