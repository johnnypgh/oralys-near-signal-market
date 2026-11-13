# Pipeline

One run = one pass of a buyer agent over one SAMPLE DATA signal feed. Paths are relative to the repo root.

| Stage | Job | Reads | Writes | Model | Check |
| --- | --- | --- | --- | --- | --- |
| [01_intake](stages/01_intake/CONTEXT.md) | Pull and validate the feed | `sample-data/signal-feed.json` | `stages/01_intake/output/feed.json` | none (script) | `python3 -I _tools/intake.py --check` |
| [02_evaluate](stages/02_evaluate/CONTEXT.md) | Decide what to buy | feed + `_shared/policy.json` | `stages/02_evaluate/output/decisions.json` | z-ai/glm-5.3-flash, or script without a key | `python3 -I _tools/evaluate.py --check` + person |
| [03_settle](stages/03_settle/CONTEXT.md) | Pay on the contract | decisions + feed | `stages/03_settle/output/receipts.json` | none (script) | `python3 -I _tools/check_receipts.py` |
| [04_report](stages/04_report/CONTEXT.md) | Summarize | decisions + receipts | `stages/04_report/output/report.md` | none (script) | `python3 -I _tools/report.py --check` |
| [05_intents_quote](stages/05_intents_quote/CONTEXT.md) | Stretch: dry USDC quote | `_tools/intents_quote.py` | `stages/05_intents_quote/output/quote.json` | none (script) | `python3 -I _tools/intents_quote.py --check` |

Stop at every check. A stage does not start until the one before it prints `CHECK OK`.
Run everything at once with `_tools/run_pipeline.sh` (it stops at the first failed check).
