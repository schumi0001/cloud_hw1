import boto3
from botocore.exceptions import ClientError


def main():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table("yelp-restaurants")

    # Keep the existing table if it was already created in the console.
    try:
        table.load()
        print("yelp-restaurants already exists.")
        return
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    table = dynamodb.create_table(
        TableName="yelp-restaurants",
        KeySchema=[{"AttributeName": "business_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "business_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST"
    )

    table.wait_until_exists()
    print("yelp-restaurants is ready.")


if __name__ == "__main__":
    main()
