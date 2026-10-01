import json
import re
import boto3

sqs = boto3.client("sqs", region_name="us-east-1")
queue_url = "https://sqs.us-east-1.amazonaws.com/229128716465/Q1"


def lambda_handler(event, context):
    session = event["sessionState"]
    intent = session["intent"]["name"]
    state = "Fulfilled"

    if intent == "GreetingIntent":
        msg = "Hi there, how can I help?"

    elif intent == "ThankYouIntent":
        msg = "You're welcome!"

    elif intent == "DiningSuggestionsIntent":
        source = event["invocationSource"]
        slots = session["intent"].get("slots") or {}
        session["intent"]["slots"] = slots

        prompts = {
            "Location": "Which city or area would you like to dine in?",
            "Cuisine": "What type of cuisine would you like?",
            "DiningTime": "What time would you like to dine? Include AM or PM.",
            "NumberOfPeople": "How many people are in your party?",
            "Email": "What email address should I send the recommendations to?"
        }

        # Read the values Lex has collected so far.
        data = {}
        for name in prompts:
            slot = slots.get(name)
            data[name] = ""

            if slot:
                data[name] = (
                    slot["value"].get("interpretedValue") or ""
                ).strip()

        cuisines = ["chinese", "indian", "italian", "japanese", "mexican"]
        bad = None

        if slots.get("Location") and data["Location"].lower() != "manhattan":
            bad = "Location"
            msg = "We currently support Manhattan. Please enter Manhattan to continue."

        elif slots.get("Cuisine") and data["Cuisine"].lower() not in cuisines:
            bad = "Cuisine"
            msg = "Please choose Chinese, Indian, Italian, Japanese, or Mexican."

        elif slots.get("DiningTime") and not re.fullmatch(
            r"([01][0-9]|2[0-3]):[0-5][0-9]", data["DiningTime"]
        ):
            bad = "DiningTime"
            msg = "Please give a specific time with AM or PM, such as 7 PM."

        elif slots.get("NumberOfPeople") and not re.fullmatch(
            r"[1-9][0-9]*", data["NumberOfPeople"]
        ):
            bad = "NumberOfPeople"
            msg = "Please enter a whole number greater than zero."

        elif slots.get("Email") and not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", data["Email"]
        ):
            bad = "Email"
            msg = "Please enter an email address like name@example.com."

        # not send an incomplete request to the queue.
        if bad is None and source == "FulfillmentCodeHook":
            for name in prompts:
                if not data[name]:
                    bad = name
                    msg = prompts[name]
                    break

        # clear the invalid answer and ask for that slot again.
        if bad:
            slots[bad] = None
            session["intent"]["state"] = "InProgress"
            session["dialogAction"] = {
                "type": "ElicitSlot",
                "slotToElicit": bad
            }

            return {
                "sessionState": session,
                "messages": [
                    {"contentType": "PlainText", "content": msg}
                ]
            }

        # during validation, Lex continue the conversation.
        if source != "FulfillmentCodeHook":
            session["dialogAction"] = {"type": "Delegate"}
            return {"sessionState": session}

        data["Location"] = "manhattan"
        data["Cuisine"] = data["Cuisine"].lower()
        data["NumberOfPeople"] = int(data["NumberOfPeople"])

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(data)
        )

        msg = "I've received your request. You will get restaurant suggestions by email."

    else:
        msg = "Sorry, I didn't understand that. You can ask for restaurant suggestions."
        state = "Failed"

    session["intent"]["state"] = state
    session["dialogAction"] = {"type": "Close"}

    return {
        "sessionState": session,
        "messages": [
            {"contentType": "PlainText", "content": msg}
        ]
    }