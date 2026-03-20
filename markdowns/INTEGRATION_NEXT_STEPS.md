# Slushie Integration Next Steps

This is the “make everything work together” checklist for the learner-lab proof of concept:

- Amplify-hosted front-end (`index.html`)
- S3 bucket (raw telemetry JSON)
- Lambda (processes JSON into machine summaries)
- DynamoDB (stores the summaries for the dashboard)

## 1) Confirm DynamoDB table schema matches the Lambda output

Your Lambda writes each machine summary directly as a DynamoDB item (it includes at least `machine_id`, `window_start`, `window_end`, `status`, `off_minutes`, `percentage_full`, `temp_avg`, `cups_total_est`, `top_hours`).

1. Open the DynamoDB table you created.
2. Check the table key schema.
3. Ensure your table partition key is present in the items the Lambda writes.
4. If your table uses a partition+sort key (common), ensure both key attributes exist in the Lambda item.
5. If your keys are different (for example you used `PK`/`SK`), you will need to update the Lambda to write items with those exact attribute names.

## 2) Set Lambda environment variables (so it knows what to do)

1. Open AWS Lambda and select your metric-processing Lambda.
2. In **Configuration -> Environment variables**, set `DYNAMODB_TABLE` = your table name, `MACHINE_IDS` = `1,2,3` (or whatever you want to include), and `ALLOWED_DATES` = `2024-05-29` (comma-separated).
3. Save.

Your code (`lambda_function.py`) reads:
- `MACHINE_IDS` (optional)
- `ALLOWED_DATES` (optional)
- `DYNAMODB_TABLE` (optional)

## 3) Give the Lambda permission to read S3 and write DynamoDB

1. Go to your Lambda **Configuration -> Permissions**.
2. Open the execution role attached to the Lambda.
3. Add/confirm these permissions: `s3:GetObject` for the bucket where you will place the raw JSON, and `dynamodb:PutItem` (or `dynamodb:BatchWriteItem`) for your DynamoDB table.
4. Save.

## 4) Upload your raw JSON to S3 (the input)

1. Upload `slushie_machines_data_huge.json` (or your sample/trimmed raw JSON) into your S3 bucket.
2. Record the S3 object key (the path/filename inside the bucket).
3. Decide whether you want manual invocation (simplest for the demo) or automatic invocation via an S3 “ObjectCreated” trigger.

## 5) Invoke the Lambda and verify DynamoDB writes

### Option A: Manual test invocation (recommended first)

1. In Lambda, go to **Test** and create a new test event.
2. Use an event that provides the payload directly or points to S3.

If you want to point to S3, try this shape:

```json
{
  "bucket": "YOUR_BUCKET_NAME",
  "key": "YOUR_OBJECT_KEY.json",
  "table_name": "YOUR_DYNAMODB_TABLE_NAME"
}
```

Notes:
Lambda also accepts `payload` (inline) and reads the raw telemetry JSON from the `payload` dict. Your Lambda returns `summaries` in the response body, and it also writes to DynamoDB if `table_name` or `DYNAMODB_TABLE` is set. Run the test, confirm the response shows `statusCode: 200` and `machine_count` is `3` (if you used machines 1–3), then confirm DynamoDB items were created. Spot-check that the stored items include `machine_id`, `status`, `off_minutes`, `percentage_full`, `temp_avg`, and `cups_total_est`.

### Option B: S3 trigger (once manual works)

1. In Lambda, add a trigger: **S3**.
2. Choose your bucket.
3. Choose event type **ObjectCreated**.
4. (Optional) Add a suffix filter to only trigger on your raw JSON keys.
5. Save.
6. Upload the JSON again to confirm the trigger fires.

## 6) Connect Amplify front-end to the real data (not the hardcoded demo)

Right now, `index.html` renders a hardcoded `const data = [...]` array. To make the dashboard reflect DynamoDB results, you need an API the browser can call.

1. Create an HTTP endpoint that the browser can call (typical approach: API Gateway + Lambda, or a new Lambda behind an existing API).
2. That endpoint should read the latest summaries from DynamoDB and return JSON in the same shape that `index.html` expects: `machine_id`, `status`, `off_minutes`, `percentage_full`, `temp_avg`, and `cups_total_est`.
3. Update `index.html` to replace the hardcoded `data` array with a `fetch(...)` to your new endpoint.
4. Deploy the updated front-end through Amplify.

### Minimal expectation for the Lambda “read” endpoint

The read endpoint doesn’t need to re-run the heavy processing. It only needs to:
- `scan` or `query` DynamoDB for the most recent items for each `machine_id`
- return an array like:

```json
[
  { "machine_id": "1", "status": "AtRisk", "off_minutes": 95, "percentage_full": 98.05, "temp_avg": 30.34, "cups_total_est": 8381 },
  { "machine_id": "2", "status": "Down", "off_minutes": 1145, "percentage_full": 11.27, "temp_avg": 30.99, "cups_total_est": 1452 },
  { "machine_id": "3", "status": "AtRisk", "off_minutes": 65, "percentage_full": 33.95, "temp_avg": 30.15, "cups_total_est": 3092 }
]
```

## 7) End-to-end demo run

1. Upload raw JSON to S3 (or drop a new file if using the trigger).
2. Confirm the Lambda processed it and wrote items to DynamoDB.
3. Open the Amplify page in the browser.
4. Confirm it calls your read endpoint and renders the new values (not the demo placeholders).

## 8) Troubleshooting checklist

1. If Lambda fails, look at CloudWatch logs, check whether your DynamoDB key schema matches the item attributes, and verify the Lambda role has `s3:GetObject` and DynamoDB write permissions.
2. If the dashboard shows empty/old data, confirm the read endpoint returns the expected JSON fields and check browser console for CORS errors.
3. If DynamoDB items exist but values are missing, confirm type conversions are compatible with your table (the Lambda converts floats to `Decimal`) and confirm your read endpoint returns numeric fields (or formats them consistently).

