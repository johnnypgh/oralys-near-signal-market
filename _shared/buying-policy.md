# Buying policy (stable rules)

The numbers live in one place: `_shared/policy.json`. This file explains how they are applied.

1. Only consider signals whose `topic` is listed in `topics`.
2. Skip any signal whose advertised `quality_score` is below `min_quality`. Do not open a request for it.
3. Skip any signal priced above `max_price_near`.
4. Walk the feed in order. Buy while the remaining budget covers the price. Never exceed `budget_near` in total.
5. Every request goes on chain with the same `min_quality`, so the contract also refuses a signed score below the bar.
6. Every request uses `ttl_seconds` as its deadline. If nothing valid arrives in time, call `refund`.
7. A model may rank signals and write the reasons, but it cannot override rules 1 to 4. The Check in
   `stages/02_evaluate/CONTEXT.md` re-applies them with a script.
