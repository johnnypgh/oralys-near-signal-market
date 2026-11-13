# Sample data rules

- Everything in `sample-data/` is made up for the hackathon demo. No real transcripts, events, people or customer data.
- The feed file must open with a `notice` that starts with `SAMPLE DATA`, and every signal must carry `"label": "SAMPLE DATA"`.
- Every transcript string starts with `SAMPLE DATA.`
- Only the keyed hash of a transcript goes on chain. The text stays off chain.
- No private Oralys code or data is copied into this repo.
- `_tools/intake.py` refuses a feed that breaks these rules.
