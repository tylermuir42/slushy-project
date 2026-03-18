# Slushi Case Study (Simple Slide Outline)

## Slide 1 — Title
- Slushie-as-a-Service: Reducing burden, increasing cups sold
- Team / course / date

## Slide 2 — Problem + stakeholders
- Retailers don’t want to own/repair machines
- Frazil needs machines **on + cold + not empty**
- Goal: reduce burden + increase cups sold + actionable insights

## Slide 3 — Data overview
- Fields: temperature, % full, is_on, slushies_filled, timestamps, maintenance metadata
- Sample used: Machines 1–3 on 2024-05-29 (5-min readings)

## Slide 4 — What we asked (guiding questions)
- Peak hours?
- Downtime hotspots?
- Stock-out risk?
- Temp readiness?
- What can become “next best action”?

## Slide 5 — Key metrics (table)
- Include the 3-row summary table from `CASE_STUDY.md`

## Slide 6 — Insights (3–5 bullets)
- Downtime kills sales (Machine 2)
- Low-fill causes silent lost sales
- Peak hours are clustered → schedule refills/checks
- Temperature is a reliable alert signal
- Maintenance fields are noisy → drive actions from behavior

## Slide 7 — Recommendations (prioritized)
- Downtime alerts + escalation
- Low-fill prevention before peak
- Temp-out-of-range alerts
- Weekly auto-checklist (chores) to reduce burden

## Slide 8 — Product concept (dashboard)
- Healthy / At Risk / Down
- Low-fill warning
- Simple machine summary cards

## Slide 9 — Architecture (simple)
- S3 raw JSON → Lambda processing → DynamoDB summary → simple dashboard/report
- Emphasize: learner-lab friendly, low cost, easy to demo

## Slide 10 — Phases / next steps
- Build the small proof of concept first, then improve thresholds or UI if time remains

