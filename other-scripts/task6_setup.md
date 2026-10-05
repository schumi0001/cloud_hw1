# Task 6 - Restaurant search index

## Domain setup

Created the domain in the Amazon OpenSearch Service console with these settings:

| Setting | Value |
| --- | --- |
| Domain | dining-restaurants |
| Region | us-east-1 |
| Engine | Elasticsearch 7.10 |
| Template | Dev/test |
| Availability Zones | 1, without standby |
| Data nodes | 1 x t3.small.search |
| Storage | 10 GiB gp3 EBS |
| Dedicated master nodes | Disabled |
| Network | Public access |
| Authentication | Fine-grained access control, internal user diningadmin |
| Encryption | HTTPS, node-to-node encryption, encryption at rest |

The setup also created an OpenSearch UI application named `aos-dining-restaurants`
with a workspace named `dining-restaurants`. Index setup and testing were done in
the domain's Kibana Dev Tools console.

[Domain endpoint](https://search-dining-restaurants-fvsi4vtxbj6jurrwsog4w7ljtq.us-east-1.es.amazonaws.com)

## Index setup

- Index name: `restaurants`
- Mapping type: `Restaurant`
- Fields: `RestaurantID` and `Cuisine`, both `keyword`
- Shards: 1 primary, 0 replicas

The index was created in Kibana with `PUT /restaurants?include_type_name=true`
and the JSON body saved in `other-scripts/restaurants_index.json`.

To recreate the index when it does not already exist, run this from the repository
root. Curl will prompt for the diningadmin password.

```bash
curl --user diningadmin \
  --request PUT \
  'https://search-dining-restaurants-fvsi4vtxbj6jurrwsog4w7ljtq.us-east-1.es.amazonaws.com/restaurants?include_type_name=true' \
  --header 'Content-Type: application/json' \
  --data-binary @other-scripts/restaurants_index.json
```

If the domain is recreated with a different endpoint, update the URL above and
the `endpoint` variable in `upload_opensearch.py`.

## Upload

The upload script reads all pages of the `yelp-restaurants` DynamoDB table. It
copies `business_id` to `RestaurantID` and `cuisine` to `Cuisine`, then uploads
these two fields using the bulk API. DynamoDB records are not modified.

Each document uses the business ID as its `_id`, so rerunning the upload replaces
the same documents rather than adding duplicates. It checks individual bulk
errors and compares the index's total and cuisine counts with DynamoDB.

The script uses the AWS credentials already configured on the computer to read
DynamoDB. These credentials need `dynamodb:Scan` permission on `yelp-restaurants`.
It separately prompts for the diningadmin password to access Elasticsearch.

Run from the repository root with the existing virtual environment:

```bash
source .venv/bin/activate
python3 -m pip install boto3 requests
python3 other-scripts/upload_opensearch.py
```

## Verified results - October 5, 2026

| Cuisine | Documents |
| --- | ---: |
| chinese | 220 |
| indian | 220 |
| italian | 220 |
| japanese | 220 |
| mexican | 220 |
| Total | 1100 |

The upload reported that the index counts matched DynamoDB.

The following search was also tested in Kibana Dev Tools:

```http
GET /restaurants/_search
{
  "size": 3,
  "query": {
    "term": {
      "Cuisine": "italian"
    }
  }
}
```

It returned 220 total matches and displayed three documents. All three had
`_type: Restaurant` and only `RestaurantID` and `Cuisine` in `_source`. The query
did not time out and had no failed shards.

The search index stores IDs and cuisines. Full restaurant details remain in
DynamoDB and can be retrieved using the returned IDs.
