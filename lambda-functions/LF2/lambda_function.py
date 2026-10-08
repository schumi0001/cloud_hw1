import json
import os
import random
from datetime import datetime
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config


region = "us-east-1"
queue_url = "https://sqs.us-east-1.amazonaws.com/229128716465/Q1"
endpoint = "https://search-dining-restaurants-fvsi4vtxbj6jurrwsog4w7ljtq.us-east-1.es.amazonaws.com"

session = boto3.Session(region_name=region)
config = Config(connect_timeout=3, read_timeout=10,
                retries={"mode": "standard", "total_max_attempts": 2})
sqs = session.client("sqs", config=config)
ses = session.client("ses", config=config)
table = session.resource("dynamodb", config=config).Table("yelp-restaurants")


def find_restaurants(cuisine):
    # Filter by cuisine, then randomly choose three matching documents.
    query = {
        "size": 3,
        "query": {
            "function_score": {
                "query": {"term": {"Cuisine": cuisine}},
                "random_score": {
                    "seed": random.randrange(2147483647),
                    "field": "_seq_no",
                },
                "boost_mode": "replace",
            }
        },
    }

    # Sign the search request with LF2's IAM role credentials.
    url = endpoint + "/restaurants/_search"
    body = json.dumps(query).encode("utf-8")
    request = AWSRequest(method="POST", url=url, data=body,
                         headers={"Content-Type": "application/json"})
    credentials = session.get_credentials().get_frozen_credentials()
    SigV4Auth(credentials, "es", region).add_auth(request)
    signed_request = Request(url, data=body, method="POST",
                             headers=dict(request.headers.items()))
    with urlopen(signed_request, timeout=10) as response:
        result = json.load(response)

    if result.get("timed_out") or result["_shards"]["failed"]:
        raise RuntimeError("Restaurant search did not complete successfully.")

    hits = result["hits"]["hits"]
    if not hits:
        raise RuntimeError(f"No restaurants found for cuisine: {cuisine}")

    # Elasticsearch has the IDs; DynamoDB has the full restaurant details.
    restaurants = []
    for hit in hits:
        business_id = hit["_source"]["RestaurantID"]
        item = table.get_item(Key={"business_id": business_id}).get("Item")
        if not item:
            raise RuntimeError(f"Restaurant missing from DynamoDB: {business_id}")
        restaurants.append(item)
    return restaurants


def make_email(data, restaurants):
    lines = [
        "Hello! Here are your restaurant suggestions:",
        "",
        f"Location: {data['Location'].title()}",
        f"Cuisine: {data['Cuisine'].title()}",
        f"Party size: {data['NumberOfPeople']}",
        f"Dining date: {data.get('DiningDate', 'Not provided')}",
        f"Dining time: {datetime.strptime(data['DiningTime'], '%H:%M').strftime('%I:%M %p').lstrip('0')}",
        "",
    ]
    for number, restaurant in enumerate(restaurants, start=1):
        lines.append(f"{number}. {restaurant['name']}")
        lines.append(f"   Address: {restaurant['address']}")
        if restaurant.get("rating") is not None:
            lines.append(f"   Rating: {restaurant['rating']}/5")
        if restaurant.get("review_count") is not None:
            lines.append(f"   Reviews: {restaurant['review_count']}")
        lines.append("")
    lines.append("Enjoy your meal! These are suggestions; no reservation has been made.")
    return "\n".join(lines)


def lambda_handler(event, context):
    sender = os.environ["SENDER_EMAIL"]

    # The schedule invokes LF2; LF2 itself pulls one request from Q1.
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=5,
        VisibilityTimeout=180,
    )
    messages = response.get("Messages", [])
    if not messages:
        print("Q1 is empty.")
        return {"processed": 0}

    message = messages[0]
    data = json.loads(message["Body"])
    data["Cuisine"] = data["Cuisine"].strip().lower()
    restaurants = find_restaurants(data["Cuisine"])
    email_body = make_email(data, restaurants)

    result = ses.send_email(
        Source=sender,
        Destination={"ToAddresses": [data["Email"]]},
        Message={
            "Subject": {"Data": "Your Dining Concierge recommendations", "Charset": "UTF-8"},
            "Body": {"Text": {"Data": email_body, "Charset": "UTF-8"}},
        },
    )

    # Remove the request only after SES accepts the email.
    # If search, DynamoDB, or SES raises an error, this line is not reached.
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
    print(f"Processed SQS message {message['MessageId']}; SES ID {result['MessageId']}")
    return {"processed": 1, "emailMessageId": result["MessageId"]}
