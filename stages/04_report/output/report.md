# Buyer agent run report

SAMPLE DATA. Every signal in this run is made up for the demo.

- Network: sandbox
- Market contract: market.sandbox
- Buyer: buyer.sandbox
- Seller payout account: seller.sandbox
- Decisions made by: z-ai/glm-5.3-flash via https://cloud-api.near.ai/v1
- Policy: budget 0.1 NEAR, minimum quality 70, price cap 0.05 NEAR
- Spent: 0.06 NEAR on 3 signals

| Signal | Score | Price (NEAR) | Decision | Why | Request | Status |
| --- | --- | --- | --- | --- | --- | --- |
| sample-001 | 88 | 0.02 | buy | Topic transit-board is allowed, quality 88 meets the 70 bar, price 0.02 is within cap and budget. | #0 | Fulfilled |
| sample-002 | 74 | 0.02 | buy | Topic earnings-call is allowed, quality 74 meets the bar, price 0.02 fits remaining budget. | #1 | Fulfilled |
| sample-003 | 52 | 0.02 | skip | Quality 52 is below min_quality 70, so no request is opened. |  |  |
| sample-004 | 91 | 0.02 | buy | Topic press-briefing is allowed, quality 91 meets the bar, price 0.02 fits remaining budget. | #2 | Fulfilled |
| sample-005 | 39 | 0.02 | skip | Quality 39 is below min_quality 70, so no request is opened. |  |  |
| sample-006 | 63 | 0.02 | skip | Quality 63 is below min_quality 70, so no request is opened. |  |  |
