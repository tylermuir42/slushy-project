import json
import os
from decimal import Decimal
from typing import Any, Dict, List

import boto3


def _to_jsonable(value: Any) -> Any:
    # DynamoDB returns numbers as Decimal; convert so `json.dumps` works.
    if isinstance(value, Decimal):
        # Best-effort conversion; these are expected to be simple numeric metrics.
        return float(value)
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    table_name = os.environ["DYNAMODB_TABLE"]
    machine_ids = os.environ.get("MACHINE_IDS", "1,2,3")
    mids = [m.strip() for m in machine_ids.split(",") if m.strip()]

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Assumes the table has:
    # - partition key:  machine_id (S)
    # - sort key:       window_start (S)
    # Then we can query each machine for its most recent window.
    results: List[Dict[str, Any]] = []

    for mid in mids:
        response = table.query(
            KeyConditionExpression="#mid = :mid",
            ExpressionAttributeNames={"#mid": "machine_id"},
            ExpressionAttributeValues={":mid": mid},
            ScanIndexForward=False,  # newest window_start first
            Limit=1,
        )
        items = response.get("Items") or []
        if not items:
            continue
        item = _to_jsonable(items[0])

        results.append(
            {
                "machine_id": item.get("machine_id"),
                "status": item.get("status"),
                "off_minutes": item.get("off_minutes"),
                "percentage_full": item.get("percentage_full"),
                "temp_avg": item.get("temp_avg"),
                "cups_total_est": item.get("cups_total_est"),
            }
        )

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
        "body": json.dumps(results),
    }

