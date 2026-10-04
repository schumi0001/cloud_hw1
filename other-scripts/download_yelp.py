import json
import os
import random
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shapely.geometry import Point, shape


cuisines = {
    "indian": "indpak",
    "chinese": "chinese",
    "italian": "italian",
    "japanese": "japanese",
    "mexican": "mexican"
}

areas = [
    "Manhattan, NY",
    "Financial District, Manhattan, NY",
    "Chinatown, Manhattan, NY",
    "East Village, Manhattan, NY",
    "Chelsea, Manhattan, NY",
    "Murray Hill, Manhattan, NY",
    "Midtown, Manhattan, NY",
    "Upper East Side, Manhattan, NY",
    "Upper West Side, Manhattan, NY",
    "Harlem, Manhattan, NY",
    "Washington Heights, Manhattan, NY",
    "Inwood, Manhattan, NY"
]

data_dir = Path(__file__).resolve().parent / "data"
cache_dir = data_dir / "yelp_cache"


def get_json(url, headers=None):
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def get_boundary():
    path = data_dir / "manhattan.geojson"
    if not path.exists():
        query = urlencode({"$where": "boroname='Manhattan'"})
        data = get_json("https://data.cityofnewyork.us/resource/gthc-hcne.geojson?" + query)
        path.write_text(json.dumps(data), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    return shape(data["features"][0]["geometry"])


def get_page(alias, area, offset, key):
    path = cache_dir / f"{alias}_{area}_{offset}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 86400:
        return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime

    query = urlencode({
        "location": area,
        "categories": alias,
        "term": "restaurants",
        "limit": min(50, 240 - offset),
        "offset": offset
    })
    time.sleep(0.3)
    data = get_json(
        "https://api.yelp.com/v3/businesses/search?" + query,
        {"Authorization": "Bearer " + key}
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    return data, path.stat().st_mtime


def make_record(business, cuisine, alias, boundary):
    location = business.get("location") or {}
    coordinates = business.get("coordinates") or {}
    lat = coordinates.get("latitude")
    lon = coordinates.get("longitude")
    categories = [c["alias"] for c in business.get("categories", [])]

    if business.get("is_closed") or alias not in categories:
        return None
    if lat is None or lon is None or not boundary.covers(Point(lon, lat)):
        return None
    if not all([business.get("id"), business.get("name"),
                location.get("address1"), location.get("display_address"),
                location.get("zip_code")]):
        return None
    if business.get("rating") is None or business.get("review_count") is None:
        return None

    return {
        "business_id": business["id"],
        "name": business["name"],
        "address": ", ".join(location["display_address"]),
        "coordinates": {"latitude": lat, "longitude": lon},
        "review_count": business["review_count"],
        "rating": business["rating"],
        "zip_code": location["zip_code"],
        "cuisine": cuisine
    }


def main():
    key = os.environ.get("YELP_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set YELP_API_KEY before running this script.")

    cache_dir.mkdir(parents=True, exist_ok=True)
    boundary = get_boundary()
    restaurants = {}
    counts = {}
    oldest_fetch = time.time()

    for cuisine, alias in cuisines.items():
        candidates = {}
        for area in areas:
            for offset in range(0, 240, 50):
                page, fetched_at = get_page(alias, area, offset, key)
                oldest_fetch = min(oldest_fetch, fetched_at)
                businesses = page.get("businesses", [])
                for business in businesses:
                    record = make_record(business, cuisine, alias, boundary)
                    if record and record["business_id"] not in restaurants:
                        candidates[record["business_id"]] = record
                if offset + len(businesses) >= page.get("total", 0) or not businesses:
                    break
                if len(candidates) >= 300:
                    break
            print(f"{cuisine}: {len(candidates)} candidates after {area}", flush=True)
            if len(candidates) >= 300:
                break

        chosen = random.sample(list(candidates.values()), min(220, len(candidates)))
        for record in chosen:
            restaurants[record["business_id"]] = record
        counts[cuisine] = len(chosen)

    ready = len(restaurants) >= 1000 and all(n >= 200 for n in counts.values())
    output = data_dir / "restaurants.json"
    output.write_text(json.dumps({
        "oldestFetchEpoch": oldest_fetch,
        "ready": ready,
        "counts": counts,
        "restaurants": list(restaurants.values())
    }, indent=2), encoding="utf-8")

    print("\nSelected restaurants:")
    for cuisine, count in counts.items():
        print(f"{cuisine}: {count}")
    print(f"Total unique restaurants: {len(restaurants)}")
    print(f"Saved to: {output}")
    if not ready:
        raise SystemExit("Not enough restaurants yet. Share the counts before uploading.")
    print("Download complete. Ready for the DynamoDB import step.")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"HTTP {error.code}: {error.read().decode()}")
    except (URLError, TimeoutError) as error:
        raise SystemExit(f"Connection error: {error}. Completed pages are cached.")
