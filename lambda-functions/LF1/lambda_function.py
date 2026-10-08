import json
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import boto3

sqs = boto3.client("sqs", region_name="us-east-1")
queue_url = "https://sqs.us-east-1.amazonaws.com/229128716465/Q1"
ny_time = ZoneInfo("America/New_York")

# These are our chatbot's allowed dining hours, not restaurant opening hours.
opening_time = time(8, 0)
closing_time = time(22, 0)
cuisines = ["chinese", "indian", "italian", "japanese", "mexican"]
number_words = dict(zip(
    "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen".split(),
    range(1, 16)
))

prompts = {
    "Location": "I'd be happy to help! Which city or area would you like to dine in?",
    "Cuisine": "What type of cuisine are you in the mood for?",
    "NumberOfPeople": "How many people will be joining? You can choose 1 to 15.",
    "DiningDate": "Just a few more details. What date would you like to dine? You can say today, tomorrow, or a specific date.",
    "DiningTime": "What time works for you? Please choose between 8 AM and 10 PM, New York time.",
    "PhoneNumber": "Almost there! What phone number should I include with your request?",
    "Email": "One last thing: what email address should I send your recommendations to?"
}
errors = {
    "Location": "Sorry, I only have restaurant suggestions for Manhattan right now. Please enter Manhattan to continue.",
    "Cuisine": "I don't have suggestions for that cuisine yet. Please choose Chinese, Indian, Italian, Japanese, or Mexican.",
    "NumberOfPeople": "Please choose a whole number from 1 to 15, such as 2 or five.",
    "DiningDate": "Please give me a valid date, such as tomorrow or a specific date in YYYY-MM-DD format.",
    "DiningTime": "I couldn't make out that time. Please include AM or PM, like 7 PM, or use 24-hour time, like 19:00.",
    "PhoneNumber": "That doesn't look like a valid phone number. Please enter 10 digits, with an optional +1 country code.",
    "Email": "That doesn't look like a valid email address. Could you enter one like name@example.com?"
}


def clean_answer(text):
    text = text.replace("’", "'")
    text = " ".join(text.lower().strip().rstrip(".!?").replace(",", " ").split())
    text = re.sub(r"^please\s+|\s+please$", "", text)
    return text.strip()


def is_manhattan(text):
    return bool(re.fullmatch(
        r"(?:(?:(?:can|could) (?:you|we)|let'?s) )?"
        r"(?:try |how about |in |i would like to dine in |i'd like to dine in )?"
        r"manhattan(?: (?:new york|ny))?", clean_answer(text)
    ))


def read_time(raw, interpreted):
    text = re.sub(r"^(?:at|around|about)\s+", "", clean_answer(raw))
    if text in ["noon", "midday"]:
        return "12:00"
    if text == "midnight":
        return "00:00"

    # Parse explicit replies ourselves, even when Lex leaves the time slot empty.
    for word, number in number_words.items():
        text = re.sub(r"^" + word + r"(?=\s|$)", str(number), text)
    text = text.replace("in the morning", "am").replace("in the evening", "pm")
    match = re.fullmatch(r"([0-9]{1,2})(?::([0-9]{2}))?\s*([ap])\.?\s*m\.?", text)
    if match:
        hour, minute, period = match.groups()
        hour, minute = int(hour), int(minute or "0")
        if 1 <= hour <= 12 and 0 <= minute <= 59:
            hour = hour % 12 + (12 if period == "p" else 0)
            return f"{hour:02d}:{minute:02d}"
        return None

    if re.fullmatch(r"(?:[01]?[0-9]|2[0-3]):[0-5][0-9]", text):
        hour, minute = text.split(":")
        return f"{int(hour):02d}:{minute}"

    # Do not let Lex turn an invalid numeric answer such as "13 PM" into a valid time.
    # Other spoken phrases can still use Lex's interpretation.
    if not re.search(r"[0-9]", raw) and raw.strip() and clean_answer(raw) != "please":
        if not re.search(r"\bnot\b", raw, re.IGNORECASE):
            if re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", interpreted):
                return interpreted
    if not raw and re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", interpreted):
        return interpreted
    return None


def read_date(raw, interpreted, today):
    text = re.sub(r"^on\s+", "", clean_answer(raw))
    offsets = {"yesterday": -1, "today": 0, "tonight": 0, "tomorrow": 1, "the day after tomorrow": 2}
    if text in offsets:
        return today + timedelta(days=offsets[text])
    # Ask for an actual day rather than letting Lex pick one from a broad period.
    if re.search(r"\b(week|month|year)\b", text):
        return None
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            return date.fromisoformat(text)
        if re.fullmatch(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", text):
            return datetime.strptime(text, "%m/%d/%Y").date()
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", interpreted):
            return date.fromisoformat(interpreted)
    except ValueError:
        pass
    return None


def read_phone(raw, interpreted):
    text = clean_answer(raw)
    text = re.sub(r"^(?:my (?:phone )?number is|it's|it is)\s+", "", text)
    # Use Lex for spoken digits, but don't silently drop letters from a typed number.
    if not re.search(r"[0-9]", text):
        text = interpreted
    if not re.fullmatch(r"\+?[0-9() .-]+", text):
        return None
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10 and len(set(digits)) > 1:
        return "+1" + digits
    return None


def save_slot(slots, name, value):
    # Keep accepted values in a consistent format for later turns and the SQS message.
    slots[name] = {"shape": "Scalar", "value": {
        "originalValue": value, "interpretedValue": value, "resolvedValues": [value]
    }}


def ask_for_slot(session, name, message):
    session["intent"]["slots"][name] = None
    session["intent"]["state"] = "InProgress"
    attributes = session["sessionAttributes"]
    attributes["waitingFor"] = name
    attributes["diningSlots"] = json.dumps(session["intent"]["slots"])
    session["dialogAction"] = {"type": "ElicitSlot", "slotToElicit": name}
    return {"sessionState": session, "messages": [{"contentType": "PlainText", "content": message}]}


def lambda_handler(event, context):
    session = event["sessionState"]
    attributes = session.get("sessionAttributes") or {}
    session["sessionAttributes"] = attributes
    intent = session["intent"]["name"]
    source = event.get("invocationSource", "DialogCodeHook")
    text = event.get("inputTranscript") or ""
    waiting = attributes.get("waitingFor")
    now = datetime.now(ny_time)
    state = "Fulfilled"

    # A greeting or a thank-you in the middle should not erase the user's answers.
    if intent in ["GreetingIntent", "ThankYouIntent"] and waiting in prompts and attributes.get("diningSlots"):
        session["intent"] = {"name": "DiningSuggestionsIntent", "state": "InProgress",
                             "slots": json.loads(attributes["diningSlots"])}
        reply = "Hi again! " if intent == "GreetingIntent" else "You're welcome! "
        return ask_for_slot(session, waiting, reply + prompts[waiting])

    # If Lex calls LF1 through FallbackIntent, keep the unfinished dining conversation.
    if intent == "FallbackIntent" and waiting in prompts and attributes.get("diningSlots"):
        intent = "DiningSuggestionsIntent"
        session["intent"] = {"name": intent, "state": "InProgress",
                             "slots": json.loads(attributes["diningSlots"])}
        source = "DialogCodeHook"

    if intent == "GreetingIntent":
        message = "Hi! How can I help you today?"
    elif intent == "ThankYouIntent":
        message = "You're very welcome! Enjoy your meal, and come back whenever you need more ideas."
    elif intent == "DiningSuggestionsIntent":
        slots = session["intent"].get("slots") or {}
        session["intent"]["slots"] = slots
        data = {}
        dining_date = None

        for name in prompts:
            value = (slots.get(name) or {}).get("value") or {}
            interpreted = (value.get("interpretedValue") or "").strip()
            raw = (value.get("originalValue") or interpreted).strip()
            answering = waiting == name and source == "DialogCodeHook"
            if answering:
                raw = text.strip()
            if not raw and not interpreted:
                prefix = ""
                if not answering and waiting == "Location" and data.get("Location"):
                    prefix = "Got it, Manhattan! "
                elif not answering and waiting == "Cuisine" and data.get("Cuisine"):
                    prefix = f"{data['Cuisine'].title()} sounds good! "
                elif not answering and waiting == "NumberOfPeople" and data.get("NumberOfPeople"):
                    prefix = f"Got it, a party of {data['NumberOfPeople']}. "
                return ask_for_slot(session, name, errors[name] if answering else prefix + prompts[name])

            error = errors[name]
            answer = None
            if name == "Location":
                if is_manhattan(raw):
                    answer = "manhattan"
            elif name == "Cuisine":
                candidate = re.sub(r"^(?:i'd like|i would like|let's try)\s+", "", clean_answer(raw))
                candidate = re.sub(r"\s+(?:food|cuisine)$", "", candidate)
                if candidate in cuisines:
                    answer = candidate
            elif name == "NumberOfPeople":
                candidate = clean_answer(raw) if answering or re.search(r"[0-9]", raw) else interpreted
                candidate = str(number_words.get(candidate, candidate))
                if not re.search(r"\b(minus|negative|not)\b", raw, re.IGNORECASE):
                    if re.fullmatch(r"[1-9][0-9]?", candidate) and int(candidate) <= 15:
                        answer = candidate
                    elif not re.search(r"[0-9]", raw) and re.fullmatch(r"[1-9][0-9]?", interpreted):
                        if int(interpreted) <= 15:
                            answer = interpreted
            elif name == "DiningDate":
                dining_date = read_date(raw, interpreted, now.date())
                if dining_date and dining_date < now.date():
                    error = "That date has already passed. Could you choose today or a future date?"
                elif dining_date == now.date() and now.time() >= closing_time:
                    error = "Today's dining hours have ended. Could you choose tomorrow or a later date?"
                elif dining_date:
                    answer = dining_date.isoformat()
            elif name == "DiningTime":
                answer = read_time(raw, interpreted)
                if answer:
                    chosen_time = time.fromisoformat(answer)
                    if not opening_time <= chosen_time <= closing_time:
                        answer = None
                        error = "Please choose a dining time between 8 AM and 10 PM, New York time. What time would you prefer?"
                    elif datetime.combine(dining_date, chosen_time, tzinfo=ny_time) <= now:
                        answer = None
                        error = "That time has already passed for your chosen date. Could you choose a later time today, between 8 AM and 10 PM?"
            elif name == "PhoneNumber":
                answer = read_phone(raw, interpreted)
            elif name == "Email":
                candidate = raw.strip() if answering else interpreted
                if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate):
                    answer = candidate

            if not answer:
                return ask_for_slot(session, name, error)
            data[name] = answer
            save_slot(slots, name, answer)

        attributes.pop("waitingFor", None)
        attributes.pop("diningSlots", None)
        if source != "FulfillmentCodeHook":
            session["dialogAction"] = {"type": "Delegate"}
            return {"sessionState": session}

        # Only a complete, valid request is added to Q1. LF2 still sends the email.
        data["NumberOfPeople"] = int(data["NumberOfPeople"])
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(data))
        message = "You're all set! I've received your request and will email you three restaurant suggestions shortly. Enjoy your meal!"
    else:
        message = "Sorry, I didn't quite understand. You can say 'I need restaurant suggestions' to get started."
        state = "Failed"

    attributes.pop("waitingFor", None)
    attributes.pop("diningSlots", None)
    session["intent"]["state"] = state
    action = "ElicitIntent" if intent in ["GreetingIntent", "FallbackIntent"] else "Close"
    session["dialogAction"] = {"type": action}
    return {"sessionState": session, "messages": [{"contentType": "PlainText", "content": message}]}
