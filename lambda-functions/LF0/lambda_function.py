import json

def lambda_handler(event, context):
    # TODO implement
    response_body = {
        "messages": [
            {
             "type": "unstructured",
             "unstructured": {
            #    "id": "string",
              "text": "I’m still under development. Please come back later.",
            #   "timestamp": "string"
                 }
            }
        ]
    }
    return {
        'statusCode': 200,
        'body': json.dumps(response_body),
        'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
        }
    }
