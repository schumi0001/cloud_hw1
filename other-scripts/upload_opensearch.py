import json
from collections import Counter
from getpass import getpass

import boto3
import requests


endpoint = "https://search-dining-restaurants-fvsi4vtxbj6jurrwsog4w7ljtq.us-east-1.es.amazonaws.com"
index = "restaurants"


def main():
    password = getpass("Password for diningadmin: ")
    session = requests.Session()
    session.auth = ("diningadmin", password)

    # Use the AWS credentials already configured on your computer.
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table("yelp-restaurants")

    # Keep reading until we have every page from DynamoDB.
    print("Reading restaurant IDs and cuisines from DynamoDB...", flush=True)
    restaurants = []
    options = {
        "ProjectionExpression": "business_id, cuisine",
        "ConsistentRead": True,
    }
    while True:
        page = table.scan(**options)
        restaurants.extend(page["Items"])
        if not page.get("LastEvaluatedKey"):
            break
        options["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    if not restaurants:
        raise SystemExit("The DynamoDB table is empty. Nothing was uploaded.")

    # Each bulk operation has an action line followed by a document line.
    # Using business_id as _id updates the same document on a rerun.
    lines = []
    for restaurant in restaurants:
        lines.append(json.dumps({"index": {"_id": restaurant["business_id"]}}))
        lines.append(json.dumps({
            "RestaurantID": restaurant["business_id"],
            "Cuisine": restaurant["cuisine"],
        }))
    body = "\n".join(lines) + "\n"

    print(f"Uploading {len(restaurants)} restaurants...", flush=True)
    response = session.post(
        f"{endpoint}/{index}/Restaurant/_bulk",
        params={"refresh": "true"},
        headers={"Content-Type": "application/x-ndjson"},
        data=body.encode("utf-8"),
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()

    # HTTP 200 can still contain failed individual bulk operations.
    if result["errors"]:
        failed = [item["index"] for item in result["items"]
                  if item["index"]["status"] >= 300]
        for item in failed[:3]:
            print(item["_id"], item.get("error"))
        raise SystemExit(f"{len(failed)} uploads failed. Fix the error and rerun.")

    # Ask Elasticsearch for the actual document counts after the upload.
    response = session.post(
        f"{endpoint}/{index}/_search",
        json={
            "size": 0,
            "track_total_hits": True,
            "aggs": {"cuisines": {"terms": {"field": "Cuisine", "size": 100}}},
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    counts = {bucket["key"]: bucket["doc_count"]
              for bucket in result["aggregations"]["cuisines"]["buckets"]}
    total = result["hits"]["total"]["value"]

    print("\nRestaurants in the Elasticsearch index:")
    for cuisine, count in sorted(counts.items()):
        print(f"{cuisine}: {count}")
    print(f"Total restaurants: {total}")

    expected = Counter(restaurant["cuisine"] for restaurant in restaurants)
    if result["_shards"]["failed"] or total != len(restaurants) or counts != expected:
        raise SystemExit("Verification failed: index counts do not match DynamoDB.")
    print("Upload complete. Counts match DynamoDB.")


if __name__ == "__main__":
    main()
