# Slushie AWS Cost Estimate

## Purpose
This document gives a **simple monthly cost estimate** for the base-layer AWS architecture used in the Slushie case study.

The design assumes:

- Historical JSON data is stored in **Amazon S3**
- **AWS Lambda** reads and processes the JSON
- Processed metrics are stored in **Amazon DynamoDB**
- A dashboard is shown with a **very simple web page or static report**

This is a **student lab / proof-of-concept estimate**, not a production quote.

## Base Architecture
- **Amazon S3**: store raw JSON and processed files
- **AWS Lambda**: process JSON and calculate metrics
- **Amazon DynamoDB**: store machine metrics and status
- **Dashboard**: simple web dashboard or report

## Cost Assumptions
These are small, lab-sized assumptions:

- Raw + processed data stored in S3: **1 GB**
- Lambda runs: **100,000 invocations per month**
- Lambda memory/runtime: light processing only
- DynamoDB storage: **1 GB**
- DynamoDB reads/writes: low student/demo traffic
- Dashboard usage: very small class/demo usage

## Estimated Monthly Costs

| Service | Use | Estimated Monthly Cost |
|---|---|---:|
| Amazon S3 | Store raw JSON + processed files (about 1 GB) | $0.03 |
| AWS Lambda | Process JSON and generate metrics | $0.00 - $1.00 |
| Amazon DynamoDB | Store machine metrics/status | $1.00 - $3.00 |
| Dashboard (simple web app) | Very basic display layer | $0.00 - $1.00 |

## Estimated Totals

### Learner-lab version
Use:
- S3
- Lambda
- DynamoDB
- simple dashboard

**Estimated total: about $1 to $5 per month**

## Best Recommendation For This Project
For this case study, the most cost-effective option is:

- **Amazon S3** for raw JSON data
- **AWS Lambda** for processing
- **Amazon DynamoDB** for storing processed machine metrics
- **Simple dashboard** instead of QuickSight

This keeps the project:

- cheap
- easy to explain
- easy to build in an AWS lab
- aligned with the JSON-based architecture

## Notes
- In an AWS lab environment, some of these costs may be covered or simulated.
- AWS Free Tier may reduce actual charges even further.
- For a class project, it is okay to present these as **rough estimates**.

## One-Sentence Summary
The base-layer Slushie AWS architecture should cost **about $1 to $5 per month** in a learner-lab-friendly setup.

