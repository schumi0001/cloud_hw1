# Task 5: Yelp restaurants and DynamoDB

The restaurant data was downloaded locally with Python and uploaded to DynamoDB.
The table was originally created in the AWS console. `create_yelp_table.py` is
included so the same table settings can also be recreated with Python.

## Table settings

- Region: `us-east-1`
- Table name: `yelp-restaurants`
- Partition key: `business_id` (String)
- No sort key
- Capacity mode: On-demand

Each item has `business_id`, `name`, `address`, `coordinates`, `review_count`,
`rating`, `zip_code`, `cuisine`, and `insertedAtTimestamp`.
The timestamp is an ordinary attribute, stored in UTC when the item is uploaded.

## Scripts

- `create_yelp_table.py`: creates the table if it does not already exist.
- `download_yelp.py`: searches Yelp by cuisine and Manhattan area, checks coordinates
  against the NYC Manhattan boundary, filters out incomplete records, and randomly
  selects up to 220 restaurants per cuisine. Business IDs are deduplicated across
  all five cuisines. The result is saved to `other-scripts/data/restaurants.json`.
- `upload_yelp.py`: reads the JSON, checks the data age, duplicates, and cuisine
  counts, converts decimal values for DynamoDB, adds the insertion timestamp, and
  uploads the items with Boto3's batch writer.

## Setup and commands

Run these commands from the repository root when setting up the data again.
AWS CLI credentials must already be configured for the intended AWS account.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install boto3 shapely
```

The import used the `YelpRestaurantsImport` IAM policy, allowing
`dynamodb:DescribeTable`, `dynamodb:BatchWriteItem`, and `dynamodb:Scan` on
`arn:aws:dynamodb:us-east-1:229128716465:table/yelp-restaurants`.
Creating the table through the script additionally requires
`dynamodb:CreateTable` on that table ARN. This additional permission is only
needed if the table is missing; it was not part of the import policy.

```bash
python3 other-scripts/create_yelp_table.py
export YELP_API_KEY='YOUR_EXISTING_YELP_API_KEY'
python3 other-scripts/download_yelp.py
python3 other-scripts/upload_yelp.py
```

The API key is read from the environment. `.venv/` and `other-scripts/data/`
are excluded from Git. The downloader reuses Yelp response files for up to
24 hours, and the uploader rejects input whose oldest fetch is 24 hours old
or older. Download fresh data before a later import.

## Completed import

On October 4, 2026, the import verification reported 1,100 unique restaurants:

| Cuisine | Restaurants |
| --- | ---: |
| Indian | 220 |
| Chinese | 220 |
| Italian | 220 |
| Japanese | 220 |
| Mexican | 220 |
| Total | 1,100 |

The DynamoDB console also showed 1,100 items after retrieving all result pages.
Re-uploading an existing business ID replaces that item, including its timestamp.

Reference: [Boto3 DynamoDB guide](https://docs.aws.amazon.com/boto3/latest/guide/dynamodb.html).
