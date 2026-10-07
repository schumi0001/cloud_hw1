# Task 7 - LF2

For this task, I created LF2 to handle the restaurant requests saved in Q1.
All the AWS resources are in `us-east-1`.

## How it works

EventBridge runs LF2 every minute. LF2 reads one message from Q1 and uses the
cuisine in that message to find three random restaurants in OpenSearch.
Then it uses their IDs to get the names, addresses, ratings, and review counts
from the `yelp-restaurants` DynamoDB table.

LF2 sends the suggestions to the email address from the chat using SES.
After SES accepts the email, LF2 deletes the message from Q1. If the queue is
empty, it returns `processed: 0` without doing the restaurant search.

## SES

I verified `fg726@nyu.edu` in SES and used it as both the sender and recipient
for testing. While SES is in the sandbox, the recipient email also needs to
be verified.

## LF2 setup

- Runtime: Python 3.14
- Memory: 256 MB
- Timeout: 60 seconds
- Handler: `lambda_function.lambda_handler`
- Environment variable: `SENDER_EMAIL` = `fg726@nyu.edu`
- Execution role: `LF2-role-xx5107wb`
- VPC: none

I copied `lambda-functions/LF2/lambda_function.py` into the Lambda editor and
deployed it. The inline policy `LF2Services` gives LF2 access to Q1, DynamoDB,
OpenSearch, and SES. The policy is saved in `other-scripts/iam/lf2_policy.json`.

I also ran the two requests in `other-scripts/lf2_opensearch_setup.http` in
Kibana Dev Tools. These create the search role and map LF2's IAM role to it
so LF2 can read the `restaurants` index.

## EventBridge schedule

- Name: `lf2-every-minute`
- Group: `default`
- Rate: `rate(1 minute)`
- Flexible time window: Off
- Target: Lambda function `LF2`
- Payload: `{}`
- Status: Enabled
- Scheduler retries: Off
- Dead-letter queue: None
- Action after completion: NONE

I used the option to create a new role for the schedule. LF2's asynchronous
retry attempts are set to 0 too. If processing fails before deletion, the
request stays in Q1 and becomes available again after 180 seconds for a
later run to try.

## Testing

First, I finished a conversation on the website and ran LF2 manually with
the test event `{}`. It returned `processed: 1`, and I received an email
with three Italian restaurant suggestions for Manhattan.

After setting up the schedule, I tried another conversation without clicking
the Lambda Test button. The recommendation email arrived automatically.
