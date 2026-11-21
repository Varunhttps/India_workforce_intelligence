# Manager Action & Opportunity Intelligence

This module ranks distinct industry/workforce-problem groups and recommends an investigation action. It is decision-support, not a prediction or replacement for manager judgment.

## Prioritization score (0–100)
- **Source breadth (0–25):** 5 points per distinct URL, capped at 25.
- **Geographic breadth (0–15):** 3 points per distinct attributed country, capped at 15.
- **Repeat observation (0–15):** 5 points per observation week; where week metadata is missing, repeated records contribute a small proxy capped at 10.
- **Recency (0–20):** newest evidence ≤30 days: 20; ≤90: 12; older: 5; missing: 0.
- **Impact wording (0–25):** critical disruption/safety language: 25; operational impact language: 18; other non-empty impact: 8; absent: 0.
- **Momentum bonus (0–10):** +10 when weekly momentum suggests emerging, expanding or potentially worsening evidence; score capped at 100.

The score ranks research priorities and does not establish the real-world severity of a workforce issue. Scores can be high because coverage is broad, not because impact is verified.

## Action routing
- Hiring/recruitment terms → validate hiring demand and pipeline.
- Skills/training terms → run a skills-gap assessment.
- Automation/technology terms → assess technology and workflow options.
- Maintenance/production/quality terms → investigate operational root causes.
- Retention/turnover/wellbeing terms → review retention and workforce experience.
- Otherwise → validate problem with stakeholders.

Each result includes suggested next step, score rationale, weekly momentum, evidence links and country coverage. Manufacturing is treated as a priority context through action routing, but the scoring works globally and across industries.

## Suggested decision thresholds
- **Act / validate now:** 70+
- **Investigate next:** 45–69
- **Monitor:** 0–44

Thresholds are heuristics; managers should confirm scope, context and evidence before allocating resources.
