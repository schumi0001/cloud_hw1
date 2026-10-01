# Task 3 setup

- Region: us-east-1
- Bot: DiningConciergeBot
- Language: English (US)
- TestBotAlias uses LF1, version $LATEST.
- GreetingIntent and ThankYouIntent use LF1 for fulfillment.
- DiningSuggestionsIntent uses LF1 for validation and fulfillment.
- Q1 is a Standard SQS queue.
- LF1's execution role has the SendToQ1 policy.