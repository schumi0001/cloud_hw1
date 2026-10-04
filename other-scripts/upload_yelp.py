import json
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import boto3


def main():
    path = Path(__file__).resolve().parent / "data" / "restaurants.json"

    # DynamoDB uses Decimal for numbers that have a decimal point.
    with path.open(encoding="utf-8") as file:
        data = json.load(file, parse_float=Decimal)
    restaurants = data["restaurants"]

    if time.time() - float(data["oldestFetchEpoch"]) >= 86400:
        raise SystemExit("The Yelp data is over 24 hours old. Run download_yelp.py again first.")

    required_fields = [
        "business_id", "name", "address", "coordinates",
        "review_count", "rating", "zip_code", "cuisine"
    ]
    for restaurant in restaurants:
        if not all(field in restaurant for field in required_fields):
            raise SystemExit("A restaurant is missing a required field.")

    ids = [restaurant["business_id"] for restaurant in restaurants]
    if len(ids) != len(set(ids)):
        raise SystemExit("The JSON contains duplicate business IDs.")

    counts = Counter(restaurant["cuisine"] for restaurant in restaurants)
    cuisines = ["indian", "chinese", "italian", "japanese", "mexican"]
    if (not data.get("ready") or len(restaurants) < 1000
            or any(counts[cuisine] < 200 for cuisine in cuisines)):
        raise SystemExit(f"Not enough restaurants to import: {dict(counts)}")

    # Uses the AWS credentials already configured on your computer.
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table("yelp-restaurants")
    table.load()

    expected_arn = "arn:aws:dynamodb:us-east-1:229128716465:table/yelp-restaurants"
    if table.table_arn != expected_arn:
        raise SystemExit("The table is in a different AWS account or region.")
    if table.key_schema != [{"AttributeName": "business_id", "KeyType": "HASH"}]:
        raise SystemExit("The table must use business_id as its only primary key.")

    print(f"Uploading {len(restaurants)} restaurants to {table.name}...", flush=True)
    with table.batch_writer() as batch:
        for restaurant in restaurants:
            restaurant["insertedAtTimestamp"] = datetime.now(timezone.utc).isoformat()
            batch.put_item(Item=restaurant)

    # Read all pages so verification also works when the table exceeds 1 MB.
    print("Upload finished. Reading the table to verify the records...", flush=True)
    saved = {}
    options = {"ConsistentRead": True}
    while True:
        response = table.scan(**options)
        for item in response.get("Items", []):
            saved[item["business_id"]] = item
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        options["ExclusiveStartKey"] = last_key

    mismatches = [
        restaurant["business_id"] for restaurant in restaurants
        if saved.get(restaurant["business_id"]) != restaurant
    ]
    if mismatches:
        raise SystemExit(f"Verification failed for {len(mismatches)} restaurants.")

    print("\nVerified records from this import:")
    for cuisine in cuisines:
        print(f"{cuisine}: {counts[cuisine]}")
    print(f"Verified unique restaurants: {len(restaurants)}")
    print(f"Total items in table: {len(saved)}")
    print("DynamoDB import complete.")


if __name__ == "__main__":
    main()
