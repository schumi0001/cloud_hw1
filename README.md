# Cloud HW1 - Dining Concierge

This chatbot asks for dining preferences and emails three restaurant suggestions
in Manhattan. The frontend is hosted on S3, and the AWS resources are in
`us-east-1`.

[Open the chatbot](http://fg726-cloud-hw1-frontend.s3-website-us-east-1.amazonaws.com)

## How it works

1. The website sends the message to API Gateway using `POST /chatbot`.
2. LF0 sends the message and conversation ID to Amazon Lex.
3. Lex uses LF1 to validate the answers and collect the location, cuisine,
   party size, date, time, phone number, and email address.
4. When the request is complete, LF1 adds it to the SQS queue `Q1`.
5. EventBridge runs LF2 every minute. LF2 reads one request, searches for three
   restaurants by cuisine, gets their details from DynamoDB, and sends the
   email through SES. It deletes the queue message after SES accepts the email.

The email includes the dining date and time in AM/PM format. The chatbot gives
suggestions; it does not make a reservation.

## Folders

| Folder | Contents |
| --- | --- |
| `frontend/` | Website files and the API Gateway JavaScript SDK |
| `lambda-functions/` | Python code for LF0, LF1, and LF2 |
| `other-scripts/` | Data import scripts, IAM policies, Lex export, Swagger file, and setup notes |

## Restaurant data and validation

The `yelp-restaurants` DynamoDB table contains 1,100 unique restaurants: 220
each for Chinese, Indian, Italian, Japanese, and Mexican cuisine. The
`restaurants` index in Amazon OpenSearch Service uses Elasticsearch 7.10 and
stores only `RestaurantID` and `Cuisine`. Full restaurant details are in
DynamoDB. Yelp is used by the data download script, not during conversations.

LF1 checks the answers and asks again when something is invalid:

- Location must be Manhattan, and cuisine must be one of the five listed above.
- Party size must be a whole number from 1 to 15.
- The dining date and time must be in the future, using New York time.
- Allowed dining times are 8 AM through 10 PM. These are the chatbot's limits,
  not the individual restaurants' opening hours.
- Phone numbers and email addresses are checked for their format.

## AWS setup notes

The API stage is `part2`. The frontend's API URL is configured in
`frontend/assets/js/sdk/apigClient.js`.

The Lex bot is `DiningConciergeBot`, using English (US) and `TestBotAlias`.
The alias's English (US) settings connect to LF1. DiningSuggestionsIntent uses
validation and fulfillment hooks. GreetingIntent, ThankYouIntent, and
FallbackIntent use fulfillment hooks. The latest Draft export is in
`other-scripts/lex/`; the Lambda code is saved separately.

SES is still in the sandbox, so the recipient must be verified in `us-east-1`.
I used `fg726@nyu.edu` as the verified sender and recipient for the demo.
LF2 reads the sender from its `SENDER_EMAIL` environment variable.

The setup steps are saved here:

- [Task 3: Lex, LF1, and SQS](other-scripts/task3_setup.md)
- [Task 4: LF0 and frontend connection](other-scripts/task4_setup.md)
- [Task 5: Yelp data and DynamoDB](other-scripts/task5_setup.md)
- [Task 6: Restaurant search index](other-scripts/task6_setup.md)
- [Task 7: LF2, SES, and the schedule](other-scripts/task7_setup.md)

These files use my AWS resource names and IDs. To recreate the project in
another account, update the API URL, Lex bot and alias IDs, queue URLs,
OpenSearch endpoint, IAM resource ARNs, and sender email for that account.
After importing Lex, connect the alias to LF1 and build the bot. Upload the
contents of `frontend/` to the S3 website bucket and deploy API Gateway with
Lambda proxy integration and CORS enabled.
