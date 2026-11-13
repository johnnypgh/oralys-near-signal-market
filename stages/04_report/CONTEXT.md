# 04_report: what was bought and why

model: none (script)

## Inputs
- `stages/02_evaluate/output/decisions.json`
- `stages/03_settle/output/receipts.json`
- `_shared/copy-rules.md`

## Process
1. Run `python3 -I _tools/report.py`. It builds the table only from the two input files.
2. Read `stages/04_report/output/report.md` as the person who will sign off on it.

## Outputs
- `stages/04_report/output/report.md`

## Check
- `python3 -I _tools/report.py --check` prints `CHECK OK`: no em or en dashes, says SAMPLE DATA,
  and matches this run's files exactly.
