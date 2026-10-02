# Task 4

- Updated LF0 to send user messages to Lex V2 using boto3.
- Region: us-east-1
- Bot: DiningConciergeBot
- Bot ID: BGEEBY4AOO
- Alias: TestBotAlias (TSTALIASID)
- Language: en_US
- Added the CallLex policy to LF0's execution role.
- LF0 returns Lex replies using the frontend's messages format.
- Kept the JSON and CORS response headers.
- Updated chat.js to send a conversation ID with each message.
- The ID stays the same until the page is refreshed.
- Uploaded the updated chat.js to S3 at assets/js/chat.js.
- Continued using POST /chatbot in the part2 API stage.
- Tested the conversation through the website, including invalid inputs.
- Confirmed the completed request appeared in SQS queue Q1.