import json
import boto3

lex = boto3.client("lexv2-runtime", region_name="us-east-1")


def lambda_handler(event, context):
    status = 200

    try:
        # Read the message sent by the website
        body = json.loads(event["body"])
        message = body["messages"][0]["unstructured"]

        # Send the text to Lex
        reply = lex.recognize_text(
            botId="BGEEBY4AOO",
            botAliasId="TSTALIASID",
            localeId="en_US",
            sessionId=message["id"],
            text=message["text"]
        )

        # Convert Lex's replies into our frontend's format
        messages = []

        for item in reply.get("messages", []):
            if item["contentType"] == "PlainText":
                messages.append({
                    "type": "unstructured",
                    "unstructured": {
                        "text": item["content"]
                    }
                })

        response_body = {"messages": messages}

    except Exception as error:
        print("LF0 error:", error)
        status = 500
        response_body = {
            "message": "Could not get a reply from the bot."
        }

    return {
        "statusCode": status,
        "body": json.dumps(response_body),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
    }