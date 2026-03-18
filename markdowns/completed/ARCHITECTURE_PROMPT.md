# Lucidchart AI Prompt

Use this prompt to generate a simple learner-lab architecture diagram:

```text
Create a very simple AWS architecture diagram for a student case study called “Slushie-as-a-Service.”

This is an AWS learner lab project with no real machines. The system is based on a JSON file of slushie machine telemetry data.

Title: Slushie Learner Lab Architecture

Show these components from left to right:

1. Amazon S3
Label: Raw JSON Data
Description: historical machine telemetry

2. AWS Lambda
Label: Process Metrics
Description: reads the JSON sample and calculates downtime, fill level, temperature average, and estimated cups sold

3. Amazon DynamoDB
Label: Machine Summary Table
Description: stores machine_id, status, off_minutes, percentage_full, temp_avg, and cups_total_est

4. Simple Dashboard or Report
Label: Ops Dashboard
Description: shows machine status, low fill warning, downtime, and estimated cups sold

Connections:
- S3 -> Lambda
- Lambda -> DynamoDB
- DynamoDB -> Dashboard

Style:
- Keep it minimal
- Use only 4 main boxes
- Use official AWS icons if available
- Make it look like a simple student proof of concept
```

