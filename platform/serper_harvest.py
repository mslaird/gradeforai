#!/usr/bin/env python3
"""
Serper.dev Google Maps Harvester -- Bulk business URL collection.

Uses Serper.dev's Google Maps API to harvest business URLs at scale.
Much faster and more reliable than DDG scraping.

Serper Maps returns ~20 local results per query.
30 verticals x 200 cities = 6,000 queries = ~120,000 business URLs.
Cost: ~$6 at $1/1K searches.

Usage:
    python serper_harvest.py --api-key YOUR_KEY
    python serper_harvest.py --api-key YOUR_KEY --workers 5 --cities 200
    python serper_harvest.py --api-key YOUR_KEY --dry-run  # count queries without running

Pipeline: serper_harvest.py -> target CSVs -> parallel_scorer.py -> scores.db
"""

import argparse
import csv
import json
import os
import sys
import signal
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

# --- Configuration ---

TARGETS_DIR = os.path.expanduser("/opt/agent-readiness/data/targets")
STATE_FILE = os.path.expanduser("/opt/agent-readiness/data/serper_harvest_state.json")
SERPER_ENDPOINT = "https://google.serper.dev/maps"

VERTICALS = [
    "plumber", "hvac", "electrician", "roofing", "dentist",
    "lawyer", "auto repair", "pest control", "landscaping", "cleaning service",
    "painting", "fencing", "flooring", "garage door", "locksmith",
    "moving company", "pool service", "pressure washing", "tree service", "window cleaning",
    "veterinarian", "chiropractor", "salon", "handyman", "accountant",
    "insurance agent", "personal trainer", "photographer", "appliance repair", "carpet cleaning",
    # Additional high-value verticals
    "orthodontist", "dermatologist", "physical therapist", "optometrist", "pediatrician",
    "real estate agent", "mortgage broker", "financial advisor", "wedding planner", "catering",
    "towing service", "glass repair", "solar installer", "general contractor", "architect",
    "interior designer", "dog grooming", "daycare", "tutoring", "martial arts",
    # Wave 2 verticals (added March 22)
    "auto body shop", "auto detailing", "bail bonds", "barber shop", "car wash",
    "concrete contractor", "deck builder", "demolition contractor", "drywall contractor", "emergency plumber",
    "excavation contractor", "fire damage restoration", "foundation repair", "funeral home", "gutter cleaning",
    "home inspector", "home staging", "irrigation repair", "junk removal", "kitchen remodeling",
    "masonry contractor", "notary public", "pawn shop", "pet boarding", "property management",
    "roofing contractor", "septic service", "sign company", "storage facility", "tax preparer",
    # Wave 3 verticals (added March 23)
    "acupuncture", "allergist", "animal hospital", "attorney", "audiologist",
    "auto glass repair", "bakery", "bathroom remodeling", "boat repair", "bookkeeper",
    "bridal shop", "cabinet maker", "car dealership", "carpet installer", "catering company",
    "cell phone repair", "childcare center", "commercial cleaning", "copy shop", "cosmetic dentist",
    "counselor", "courier service", "cpa", "credit repair", "dance studio",
    "dental implants", "dog trainer", "door repair", "driving school", "dry cleaner",
    "elder care", "emergency dentist", "endodontist", "event planner", "eye doctor",
    "family doctor", "fence installer", "fire sprinkler", "florist", "furnace repair",
    "garage builder", "gastroenterologist", "gym", "hair salon", "hearing aid",
    "home builder", "home security", "house painter", "immigration lawyer", "in-home care",
    "jewelry repair", "karate school", "kennel", "kitchen cabinet", "limo service",
    "maid service", "med spa", "mediator", "mobile mechanic", "nail salon",
    "ob gyn", "oral surgeon", "orthodontics", "pain management", "paving contractor",
    "periodontist", "pharmacy", "piano tuner", "plastic surgeon", "podiatrist",
    "print shop", "private investigator", "psychiatrist", "real estate appraiser", "rehab center",
    "restaurant", "roofer", "rv repair", "security guard", "sewer repair",
    "shutter company", "siding contractor", "skin care clinic", "spa", "speech therapist",
    "sprinkler repair", "stump removal", "surgeon", "tailor", "tattoo shop",
    "tile installer", "title company", "tow truck", "travel agent", "urgent care",
    "used car dealer", "water damage restoration", "water heater repair", "welding", "window installer",
    "yoga studio",
]

# Top 200 US cities by population
CITIES = [
    ("New York", "NY"), ("Los Angeles", "CA"), ("Chicago", "IL"), ("Houston", "TX"),
    ("Phoenix", "AZ"), ("Philadelphia", "PA"), ("San Antonio", "TX"), ("San Diego", "CA"),
    ("Dallas", "TX"), ("Fort Worth", "TX"), ("San Jose", "CA"), ("Austin", "TX"),
    ("Jacksonville", "FL"), ("Columbus", "OH"), ("Charlotte", "NC"), ("Indianapolis", "IN"),
    ("San Francisco", "CA"), ("Seattle", "WA"), ("Denver", "CO"), ("Nashville", "TN"),
    ("Oklahoma City", "OK"), ("Washington", "DC"), ("El Paso", "TX"), ("Las Vegas", "NV"),
    ("Boston", "MA"), ("Portland", "OR"), ("Memphis", "TN"), ("Louisville", "KY"),
    ("Baltimore", "MD"), ("Milwaukee", "WI"), ("Albuquerque", "NM"), ("Tucson", "AZ"),
    ("Fresno", "CA"), ("Sacramento", "CA"), ("Mesa", "AZ"), ("Kansas City", "MO"),
    ("Atlanta", "GA"), ("Omaha", "NE"), ("Colorado Springs", "CO"), ("Raleigh", "NC"),
    ("Long Beach", "CA"), ("Virginia Beach", "VA"), ("Miami", "FL"), ("Oakland", "CA"),
    ("Minneapolis", "MN"), ("Tampa", "FL"), ("Tulsa", "OK"), ("Arlington", "TX"),
    ("New Orleans", "LA"), ("Wichita", "KS"), ("Cleveland", "OH"), ("Bakersfield", "CA"),
    ("Aurora", "CO"), ("Anaheim", "CA"), ("Honolulu", "HI"), ("Santa Ana", "CA"),
    ("Riverside", "CA"), ("Corpus Christi", "TX"), ("Lexington", "KY"), ("Henderson", "NV"),
    ("Stockton", "CA"), ("Saint Paul", "MN"), ("Cincinnati", "OH"), ("St. Louis", "MO"),
    ("Pittsburgh", "PA"), ("Greensboro", "NC"), ("Lincoln", "NE"), ("Anchorage", "AK"),
    ("Plano", "TX"), ("Orlando", "FL"), ("Irvine", "CA"), ("Newark", "NJ"),
    ("Durham", "NC"), ("Chula Vista", "CA"), ("Toledo", "OH"), ("Fort Wayne", "IN"),
    ("St. Petersburg", "FL"), ("Laredo", "TX"), ("Jersey City", "NJ"), ("Chandler", "AZ"),
    ("Madison", "WI"), ("Lubbock", "TX"), ("Scottsdale", "AZ"), ("Reno", "NV"),
    ("Buffalo", "NY"), ("Gilbert", "AZ"), ("Glendale", "AZ"), ("North Las Vegas", "NV"),
    ("Winston-Salem", "NC"), ("Chesapeake", "VA"), ("Norfolk", "VA"), ("Fremont", "CA"),
    ("Garland", "TX"), ("Irving", "TX"), ("Hialeah", "FL"), ("Richmond", "VA"),
    ("Boise", "ID"), ("Spokane", "WA"), ("Baton Rouge", "LA"), ("Tacoma", "WA"),
    # Next 100 cities
    ("San Bernardino", "CA"), ("Modesto", "CA"), ("Fontana", "CA"), ("Des Moines", "IA"),
    ("Moreno Valley", "CA"), ("Santa Clarita", "CA"), ("Fayetteville", "NC"), ("Birmingham", "AL"),
    ("Oxnard", "CA"), ("Rochester", "NY"), ("Port St. Lucie", "FL"), ("Grand Rapids", "MI"),
    ("Huntsville", "AL"), ("Salt Lake City", "UT"), ("Frisco", "TX"), ("Yonkers", "NY"),
    ("Glendale", "CA"), ("Amarillo", "TX"), ("Worcester", "MA"), ("Little Rock", "AR"),
    ("McKinney", "TX"), ("Augusta", "GA"), ("Akron", "OH"), ("Knoxville", "TN"),
    ("Brownsville", "TX"), ("Newport News", "VA"), ("Tempe", "AZ"), ("Providence", "RI"),
    ("Overland Park", "KS"), ("Tallahassee", "FL"), ("Clarksville", "TN"), ("Peoria", "AZ"),
    ("Cape Coral", "FL"), ("Sioux Falls", "SD"), ("Springfield", "MO"), ("Pembroke Pines", "FL"),
    ("Lancaster", "CA"), ("Eugene", "OR"), ("Salem", "OR"), ("Palmdale", "CA"),
    ("Elk Grove", "CA"), ("Corona", "CA"), ("Savannah", "GA"), ("Cary", "NC"),
    ("Fort Collins", "CO"), ("Murfreesboro", "TN"), ("Roseville", "CA"), ("Surprise", "AZ"),
    ("Denton", "TX"), ("Midland", "TX"), ("Thornton", "CO"), ("McAllen", "TX"),
    ("Paterson", "NJ"), ("Lakewood", "CO"), ("Miramar", "FL"), ("Olathe", "KS"),
    ("Dayton", "OH"), ("Charleston", "SC"), ("Pasadena", "TX"), ("Joliet", "IL"),
    ("Hampton", "VA"), ("Naperville", "IL"), ("Bellevue", "WA"), ("Killeen", "TX"),
    ("Sunnyvale", "CA"), ("Murrieta", "CA"), ("Macon", "GA"), ("Mesquite", "TX"),
    ("Hayward", "CA"), ("Bridgeport", "CT"), ("Syracuse", "NY"), ("Escondido", "CA"),
    ("Waco", "TX"), ("Torrance", "CA"), ("Pomona", "CA"), ("Rockford", "IL"),
    ("Columbia", "SC"), ("Carrollton", "TX"), ("West Jordan", "UT"), ("Visalia", "CA"),
    ("Lakeland", "FL"), ("Sterling Heights", "MI"), ("Lewisville", "TX"), ("New Haven", "CT"),
    ("Thousand Oaks", "CA"), ("Cedar Rapids", "IA"), ("West Valley City", "UT"), ("Allen", "TX"),
    ("Round Rock", "TX"), ("College Station", "TX"), ("Richardson", "TX"), ("Stamford", "CT"),
    ("Clearwater", "FL"), ("West Palm Beach", "FL"), ("Concord", "CA"), ("Wilmington", "NC"),
    ("Arvada", "CO"), ("Westminster", "CO"), ("Fargo", "ND"), ("Centennial", "CO"),
    # Cities 201-250
    ("Coral Springs", "FL"), ("Palm Bay", "FL"), ("Costa Mesa", "CA"), ("Elgin", "IL"),
    ("Westminster", "CA"), ("Lowell", "MA"), ("High Point", "NC"), ("Manchester", "NH"),
    ("Provo", "UT"), ("Peoria", "IL"), ("Evansville", "IN"), ("Downey", "CA"),
    ("Pompano Beach", "FL"), ("Antioch", "CA"), ("Temecula", "CA"), ("West Covina", "CA"),
    ("Daly City", "CA"), ("Everett", "WA"), ("Burbank", "CA"), ("Broken Arrow", "OK"),
    ("Carlsbad", "CA"), ("Inglewood", "CA"), ("El Monte", "CA"), ("Rialto", "CA"),
    ("Davie", "FL"), ("Sandy Springs", "GA"), ("Jurupa Valley", "CA"), ("South Bend", "IN"),
    ("Green Bay", "WI"), ("Tyler", "TX"), ("Boulder", "CO"), ("Edinburg", "TX"),
    ("Wichita Falls", "TX"), ("San Mateo", "CA"), ("Leesburg", "VA"), ("Lee's Summit", "MO"),
    ("Davenport", "IA"), ("Tuscaloosa", "AL"), ("Lansing", "MI"), ("Las Cruces", "NM"),
    ("Abilene", "TX"), ("Beaumont", "TX"), ("Norwalk", "CA"), ("Vacaville", "CA"),
    ("Vallejo", "CA"), ("Sparks", "NV"), ("Federal Way", "WA"), ("Berkeley", "CA"),
    ("Woodbridge", "NJ"), ("Santa Maria", "CA"),
    # Cities 251-409 (expansion wave March 26)
    ("Gainesville", "FL"), ("Champaign", "IL"), ("Springfield", "IL"), ("Pueblo", "CO"),
    ("Athens", "GA"), ("Topeka", "KS"), ("Hartford", "CT"), ("Simi Valley", "CA"),
    ("Lafayette", "LA"), ("Yakima", "WA"), ("Duluth", "MN"), ("Erie", "PA"),
    ("Odessa", "TX"), ("Greeley", "CO"), ("Tracy", "CA"), ("Nampa", "ID"),
    ("Longmont", "CO"), ("Bend", "OR"), ("Meridian", "ID"), ("Fishers", "IN"),
    ("Buckeye", "AZ"), ("Goodyear", "AZ"), ("Warner Robins", "GA"), ("Flower Mound", "TX"),
    ("New Braunfels", "TX"), ("Dublin", "CA"), ("Mankato", "MN"), ("Lake Charles", "LA"),
    ("Hagerstown", "MD"), ("Rocky Mount", "NC"), ("Chico", "CA"), ("Redding", "CA"),
    ("Napa", "CA"), ("Bloomington", "IN"), ("Flagstaff", "AZ"), ("Medford", "OR"),
    ("St. George", "UT"), ("Rapid City", "SD"), ("Missoula", "MT"), ("Billings", "MT"),
    ("Great Falls", "MT"), ("Casper", "WY"), ("Cheyenne", "WY"), ("Bismarck", "ND"),
    ("Idaho Falls", "ID"), ("Pocatello", "ID"), ("Twin Falls", "ID"), ("Logan", "UT"),
    ("Ogden", "UT"), ("Orem", "UT"), ("Kennewick", "WA"), ("Richland", "WA"),
    ("Wenatchee", "WA"), ("Bellingham", "WA"), ("Olympia", "WA"), ("Longview", "WA"),
    ("Albany", "OR"), ("Corvallis", "OR"), ("Grants Pass", "OR"), ("Roseburg", "OR"),
    ("Redmond", "OR"), ("Klamath Falls", "OR"), ("Prescott", "AZ"), ("Sierra Vista", "AZ"),
    ("Yuma", "AZ"), ("Lake Havasu City", "AZ"), ("Bullhead City", "AZ"), ("Kingman", "AZ"),
    ("Casa Grande", "AZ"), ("Maricopa", "AZ"), ("Florence", "AZ"), ("Queen Creek", "AZ"),
    ("San Marcos", "TX"), ("Georgetown", "TX"), ("Pflugerville", "TX"), ("Kyle", "TX"),
    ("Temple", "TX"), ("Bryan", "TX"), ("Lufkin", "TX"), ("Texarkana", "TX"),
    ("Victoria", "TX"), ("Sherman", "TX"), ("Weatherford", "TX"), ("Granbury", "TX"),
    ("Mansfield", "TX"), ("Burleson", "TX"), ("Cleburne", "TX"), ("Conroe", "TX"),
    ("Pearland", "TX"), ("League City", "TX"), ("Sugar Land", "TX"), ("Missouri City", "TX"),
    ("Baytown", "TX"), ("Galveston", "TX"), ("Port Arthur", "TX"), ("Longview", "TX"),
    ("Tyler", "TX"), ("Lumberton", "TX"), ("Harlingen", "TX"), ("Pharr", "TX"),
    ("Mission", "TX"), ("Edinburg", "TX"), ("Hattiesburg", "MS"), ("Gulfport", "MS"),
    ("Biloxi", "MS"), ("Jackson", "MS"), ("Tupelo", "MS"), ("Meridian", "MS"),
    ("Dothan", "AL"), ("Auburn", "AL"), ("Decatur", "AL"), ("Florence", "AL"),
    ("Gadsden", "AL"), ("Mobile", "AL"), ("Montgomery", "AL"), ("Pensacola", "FL"),
    ("Panama City", "FL"), ("Tallahassee", "FL"), ("Ocala", "FL"), ("Daytona Beach", "FL"),
    ("Melbourne", "FL"), ("Vero Beach", "FL"), ("Fort Pierce", "FL"), ("Stuart", "FL"),
    ("Naples", "FL"), ("Fort Myers", "FL"), ("Sarasota", "FL"), ("Bradenton", "FL"),
    ("Punta Gorda", "FL"), ("Winter Haven", "FL"), ("Kissimmee", "FL"), ("Sanford", "FL"),
    ("Deltona", "FL"), ("Palm Coast", "FL"), ("St. Augustine", "FL"), ("Gainesville", "GA"),
    ("Dalton", "GA"), ("Rome", "GA"), ("Valdosta", "GA"), ("Albany", "GA"),
    ("Brunswick", "GA"), ("Statesboro", "GA"), ("Hinesville", "GA"), ("Pooler", "GA"),
    ("Aiken", "SC"), ("Florence", "SC"), ("Myrtle Beach", "SC"), ("Sumter", "SC"),
    ("Greenville", "SC"), ("Spartanburg", "SC"), ("Anderson", "SC"), ("Rock Hill", "SC"),
    ("Gastonia", "NC"), ("Hickory", "NC"), ("Asheville", "NC"), ("Wilmington", "DE"),
    ("Dover", "DE"), ("Harrisburg", "PA"), ("York", "PA"), ("Lancaster", "PA"),
    ("Reading", "PA"), ("Allentown", "PA"), ("Scranton", "PA"),
]

SKIP_DOMAINS = {
    "yelp.com", "yellowpages.com", "bbb.org", "angi.com", "angieslist.com",
    "homeadvisor.com", "thumbtack.com", "google.com", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "linkedin.com", "youtube.com",
    "reddit.com", "wikipedia.org", "bing.com", "yahoo.com", "pinterest.com",
    "nextdoor.com", "mapquest.com", "apple.com", "amazon.com",
    "tripadvisor.com", "glassdoor.com", "indeed.com", "craigslist.org",
    "manta.com", "superpages.com", "whitepages.com", "foursquare.com",
    "buildzoom.com", "houzz.com", "bark.com", "porch.com",
    "tiktok.com", "trustpilot.com", "groupon.com", "expertise.com",
    "birdeye.com", "podium.com", "care.com", "taskrabbit.com",
    "homeserve.com", "networx.com", "checkatrade.com", "threebestrated.com",
    "kbb.com", "nerdwallet.com", "chamberofcommerce.com",
}

running = True
csv_lock = threading.Lock()


def handle_signal(signum, frame):
    global running
    print("\nShutting down...")
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def clean_website(url):
    """Normalize a business website URL."""
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").lower()
        if not domain:
            return None
        if any(skip in domain for skip in SKIP_DOMAINS):
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return None


def load_state():
    """Load progress state for resuming interrupted runs."""
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"completed_combos": [], "total_urls": 0, "total_queries": 0}


def save_state(state):
    """Save progress state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def save_urls_to_csv(urls_data, vertical, city, state_code):
    """Save harvested URLs to target CSV. Thread-safe."""
    os.makedirs(TARGETS_DIR, exist_ok=True)
    filename = f"{vertical}_{city.lower().replace(' ', '-')}_{state_code.lower()}.csv"
    filepath = os.path.join(TARGETS_DIR, filename)

    # Load existing to dedupe
    existing = set()
    with csv_lock:
        if os.path.isfile(filepath):
            with open(filepath, "r") as f:
                for row in csv.DictReader(f):
                    existing.add(row.get("url", "").strip())

    now = datetime.now(timezone.utc).isoformat()
    new_rows = []
    for url_info in urls_data:
        url = url_info["url"]
        if url not in existing:
            new_rows.append({
                "url": url,
                "vertical": vertical,
                "city": city,
                "state": state_code,
                "harvested": now,
                "scored": "False",
                "business_name": url_info.get("name", ""),
                "phone": url_info.get("phone", ""),
                "address": url_info.get("address", ""),
                "rating": url_info.get("rating", ""),
                "reviews": url_info.get("reviews", ""),
            })

    if not new_rows:
        return 0

    with csv_lock:
        file_exists = os.path.isfile(filepath)
        with open(filepath, "a", newline="") as f:
            fieldnames = ["url", "vertical", "city", "state", "harvested", "scored",
                         "business_name", "phone", "address", "rating", "reviews"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_rows)

    return len(new_rows)


def search_serper_maps(api_key, query, num=20):
    """Query Serper.dev Google Maps API. Returns list of place results."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": num,
    }

    try:
        resp = requests.post(SERPER_ENDPOINT, headers=headers, json=payload, timeout=30)
        if resp.status_code == 429:
            print("    [!] Rate limited. Sleeping 10s...")
            time.sleep(10)
            resp = requests.post(SERPER_ENDPOINT, headers=headers, json=payload, timeout=30)

        if resp.status_code != 200:
            print(f"    [!] Serper error {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        return data.get("places", [])

    except Exception as e:
        print(f"    [!] Request error: {e}")
        return []


def harvest_combo(api_key, vertical, city, state_code):
    """Harvest one vertical+city combo from Serper Maps."""
    query = f"{vertical} in {city}, {state_code}"
    places = search_serper_maps(api_key, query)

    urls_data = []
    seen = set()

    for place in places:
        website = place.get("website")
        cleaned = clean_website(website)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            urls_data.append({
                "url": cleaned,
                "name": place.get("title", ""),
                "phone": place.get("phoneNumber", ""),
                "address": place.get("address", ""),
                "rating": place.get("rating", ""),
                "reviews": place.get("ratingCount", ""),
            })

    added = 0
    if urls_data:
        added = save_urls_to_csv(urls_data, vertical, city, state_code)

    return (vertical, city, state_code, len(urls_data), added)


def build_combos(num_cities=200):
    """Build all vertical x city combos."""
    cities = CITIES[:num_cities]
    combos = []
    for vertical in VERTICALS:
        for city, state_code in cities:
            combos.append((vertical, city, state_code))
    return combos


def run_harvest(api_key, workers=5, num_cities=200, dry_run=False, max_queries=0):
    """Main harvest loop."""
    global running

    all_combos = build_combos(num_cities)
    state = load_state()
    completed = set(tuple(c) for c in state.get("completed_combos", []))
    total_urls = state.get("total_urls", 0)
    total_queries = state.get("total_queries", 0)

    # Filter out already-completed combos
    remaining = [c for c in all_combos if c not in completed]

    # Cap remaining if max_queries is set
    if max_queries > 0 and len(remaining) > max_queries:
        remaining = remaining[:max_queries]

    print("=" * 60)
    print("  Serper.dev Google Maps Harvester")
    print("=" * 60)
    print(f"  Verticals:      {len(VERTICALS)}")
    print(f"  Cities:         {num_cities}")
    print(f"  Total combos:   {len(all_combos)}")
    print(f"  Already done:   {len(completed)}")
    print(f"  Remaining:      {len(remaining)}")
    if max_queries > 0:
        print(f"  Max queries:    {max_queries}")
    print(f"  Workers:        {workers}")
    print(f"  Est. queries:   {len(remaining)}")
    print(f"  Est. URLs:      ~{len(remaining) * 8:,} (avg 8 with website per query)")
    print("=" * 60)

    if dry_run:
        print("\n  DRY RUN -- no queries will be made.")
        print(f"  To run: remove --dry-run flag")
        return

    print()
    batch_size = workers
    batch_num = 0
    session_added = 0
    session_queries = 0

    for i in range(0, len(remaining), batch_size):
        if not running:
            break
        if max_queries > 0 and session_queries >= max_queries:
            print(f"\n  Reached max queries limit ({max_queries}). Stopping.")
            break

        batch = remaining[i:i + batch_size]
        batch_num += 1
        batch_start = time.time()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(harvest_combo, api_key, v, c, s): (v, c, s)
                for v, c, s in batch
            }

            for future in as_completed(futures):
                if not running:
                    break
                try:
                    vertical, city, st, found, added = future.result(timeout=60)
                    session_added += added
                    session_queries += 1
                    total_urls += added
                    total_queries += 1
                    completed.add((vertical, city, st))

                    if added > 0:
                        print(f"    +{added:>3} | {vertical} in {city}, {st} ({found} found)")
                except Exception as e:
                    combo = futures[future]
                    print(f"    [!] Error: {combo[0]} in {combo[1]}: {e}")

        elapsed = time.time() - batch_start
        done_pct = (len(completed) / len(all_combos)) * 100

        if batch_num % 10 == 0 or batch_num <= 3:
            print(f"  [{batch_num}] {done_pct:.1f}% done | +{session_added} URLs | {session_queries} queries | {elapsed:.1f}s")

        # Save state every batch
        state = {
            "completed_combos": [list(c) for c in completed],
            "total_urls": total_urls,
            "total_queries": total_queries,
            "last_run": datetime.now(timezone.utc).isoformat(),
        }
        save_state(state)

        # Small delay between batches to be respectful
        if running:
            time.sleep(0.5)

    print()
    print("=" * 60)
    print(f"  DONE")
    print(f"  Total queries:  {total_queries}")
    print(f"  Total URLs:     {total_urls}")
    print(f"  Est. cost:      ${total_queries / 1000:.2f}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Serper.dev Google Maps bulk harvester")
    parser.add_argument("--api-key", required=True, help="Serper.dev API key")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    parser.add_argument("--cities", type=int, default=200, help="Number of cities to cover (default: 200)")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without making API calls")
    parser.add_argument("--max-queries", type=int, default=0, help="Stop after this many queries (0 = unlimited)")
    args = parser.parse_args()

    run_harvest(api_key=args.api_key, workers=args.workers, num_cities=args.cities, dry_run=args.dry_run, max_queries=args.max_queries)


if __name__ == "__main__":
    main()
