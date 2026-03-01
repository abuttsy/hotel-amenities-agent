import requests
from bs4 import BeautifulSoup
import re
import json

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

def scrape_website_with_sources(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=20, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.extract()

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
        return None, str(e)

def discover_facilities_for_hotel(website_url, facilities, existing_facilities=None, hotel_name=None):
    """
    Exposed worker tool for Notion Agent.
    :param website_url: The hotel's website URL.
    :param facilities: List of canonical facility names to search for.
    :param existing_facilities: List of facility names already linked (to avoid redundant matching).
    :param hotel_name: Name of the hotel for logging.
    :return: Dict with matched_facilities and evidence.
    """
    sources, error = scrape_website_with_sources(website_url)
    if error:
        return {"error": f"Failed to scrape {website_url}: {error}"}

    existing_set = set(existing_facilities or [])
    matched_names = []
    evidence = {}

    for name in facilities:
        if name in existing_set:
            continue

        # Get synonyms for the facility
        # Note: In the tool version, 'facilities' is just a list of names.
        # We use our local FACILITY_SYNONYMS map.
        synonyms = FACILITY_SYNONYMS.get(name, [])
        search_terms = list(set([name] + synonyms))

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
                facilities=input_json.get("facilities", []),
                existing_facilities=input_json.get("existing_facilities", []),
                hotel_name=input_json.get("hotel_name")
            )
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
