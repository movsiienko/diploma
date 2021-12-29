import os
from http import HTTPStatus

import boto3
import simplejson
from boto3.dynamodb.conditions import Key

from src.constants import CORS_HEADERS

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("TABLE_NAME"))


def handler(event, _):
    items = table.query(IndexName="type_calculated_at", KeyConditionExpression=Key("type").eq("CALCULATION"))
    return {
        "body": simplejson.dumps(
            {
                "calculations": [
                    {
                        "calculation_id": i["calculation_id"],
                        "result": i["result"],
                        "input": i["input"],
                        "calculated_at": i["calculated_at"],
                    }
                    for i in items.get("Items")
                ]
            }
        ),
        "headers": CORS_HEADERS,
        "statusCode": HTTPStatus.OK,
    }
