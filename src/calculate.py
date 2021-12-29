import json
import os
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from uuid import uuid4

import boto3
import marshmallow
import pandas as pd
import simplejson
from marshmallow import Schema, fields

from src.constants import CORS_HEADERS

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("TABLE_NAME"))


class InputSchema(Schema):
    transport_amount = fields.Integer(required=True)
    fail_probability = fields.Number(required=True)
    disadvantage_losses = fields.Number(required=True)
    excess_losses = fields.Number(required=True)


def handler(event, _):
    try:
        body = InputSchema().loads(event.get("body"))
    except marshmallow.ValidationError as e:
        return {
            "statusCode": HTTPStatus.UNPROCESSABLE_ENTITY,
            "body": json.dumps(e.normalized_messages()),
            "headers": CORS_HEADERS,
        }
    calculation_id = str(uuid4())
    result = calculate(
        body["transport_amount"], body["fail_probability"], body["disadvantage_losses"], body["excess_losses"]
    )
    result = simplejson.loads(json.dumps(result), parse_float=Decimal)
    body = simplejson.loads(json.dumps(body), parse_float=Decimal)
    item = {
        "calculation_id": calculation_id,
        "result": result,
        "input": body,
        "calculated_at": datetime.now().isoformat(),
    }
    table.put_item(
        Item={
            "PK": f"CALCULATION#{calculation_id}",
            "SK": f"CALCULATION#{calculation_id}",
            "type": "CALCULATION",
            **item,
        }
    )
    return {"body": simplejson.dumps(item), "headers": CORS_HEADERS, "statusCode": HTTPStatus.CREATED}


def calculate(total_tr_count, p1, unreleased_damage, excess_reverse_damage):
    start_point = int(total_tr_count * 0.03)
    end_point = int(total_tr_count * 0.2)
    df = pd.DataFrame(columns=["r", "sum_damage"])
    for r in range(start_point, end_point + 1):
        table = build_table(r, total_tr_count, unreleased_damage, excess_reverse_damage, p1)
        df = df.append({"r": r, "sum_damage": table["sum_damage"].sum()}, ignore_index=True)
    min_damage = df["sum_damage"].min()
    return {"count": df[df["sum_damage"] == df["sum_damage"].min()]["r"].item(), "sum_damage": min_damage}


def combinations_count(n: int, k: int) -> int:
    if 0 <= k <= n:
        nn = 1
        kk = 1
        for t in range(1, min(k, n - k) + 1):
            nn *= n
            kk *= t
            n -= 1
        return nn // kk
    else:
        return 0


def get_pu(p1: float, u: int, a: int) -> float:
    return combinations_count(a, u) * pow(p1, u) * pow(1 - p1, a - u)


def build_table(r: int, a: int, z: int, y: int, p1: float) -> pd.DataFrame:
    data = {"unreleased": [], "broken": [], "excess_reserve": []}
    for i in range(a + 1):
        data["unreleased"].append(i)
        data["broken"].append(i - r if i - r > 0 else 0)
        data["excess_reserve"].append(r - i if r - i > 0 else 0)
    df = pd.DataFrame(data)
    df["unrelease_probability"] = df.apply(lambda row: get_pu(p1, row["unreleased"], a), axis=1)
    df["unrelease_damage"] = df["broken"] * z
    df["excess_reserve_damage"] = df["excess_reserve"] * y
    df["sum_damage"] = (df["excess_reserve_damage"] + df["unrelease_damage"]) * df["unrelease_probability"]
    return df
