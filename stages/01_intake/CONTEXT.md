# 01_intake: pull the SAMPLE DATA signal feed

model: none (script)

## Inputs
- `sample-data/signal-feed.json` (this run's feed, SAMPLE DATA)
- `_shared/sample-data-rules.md` (stable rules)

## Process
1. Run `python3 -I _tools/intake.py`. It validates the labels and copies the feed.
2. Open `stages/01_intake/output/feed.json` and skim the titles. Stop if anything looks like real data.

## Outputs
- `stages/01_intake/output/feed.json`

## Check
- `python3 -I _tools/intake.py --check` prints `CHECK OK`. Do not go to stage 02 until it does.
