# Slushie 4-Person Sprint Plan

## Goal
Finish a learner-lab proof of concept in one short working session using:

- `S3`
- `Lambda`
- `DynamoDB`
- a simple dashboard or report

## Team Roles

### Person 1: AWS Setup
- Create one S3 bucket for raw and processed data
- Create one Lambda function for metric processing
- Create one DynamoDB table for machine summaries
- Upload the JSON sample or summary output

### Person 2: Data Processing
- Use `analyze_sample.py`
- Keep the scope to machines `1`, `2`, and `3`
- Keep the time window to `2024-05-29`
- Output only:
  - `machine_id`
  - `status`
  - `off_minutes`
  - `percentage_full`
  - `temp_avg`
  - `cups_total_est`

### Person 3: Diagram + Story
- Create the architecture diagram
- Explain that the JSON is simulated telemetry
- Connect the output to the business goals:
  - reduce retailer burden
  - increase cups sold
  - provide actionable insights

### Person 4: Dashboard / Output View
- Use `sample_machine_summary.json` as the demo data source
- Build the lightest possible output:
  - simple HTML page
  - machine status cards
  - low fill, downtime, and cups sold
- If the UI takes too long, present screenshots or the JSON output directly

## Suggested Time Box
- `0:00-0:30` setup and role split
- `0:30-1:30` sample processing and summary output
- `1:30-2:30` dashboard/report and architecture diagram
- `2:30-3:30` slides, cost estimate, screenshots, and cleanup

## Non-Negotiables
- Keep the architecture simple
- Do not process the full dataset live
- Do not use QuickSight
- Do not add extra AWS services unless time is left over

