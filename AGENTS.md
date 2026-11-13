# Oralys Signal Market: agent entry map

You are in an ICM workspace. Folders are the steps, CONTEXT.md files are the contracts, `_tools/` does the deterministic work.
Load only what the current stage needs.

## Where to go
- The pipeline, one table: [CONTEXT.md](CONTEXT.md)
- Running a stage: open that stage's CONTEXT.md under `stages/` and follow Inputs, Process, Outputs, Check.
- Stable rules (read, do not edit during a run): [_shared/buying-policy.md](_shared/buying-policy.md),
  [_shared/policy.json](_shared/policy.json), [_shared/sample-data-rules.md](_shared/sample-data-rules.md),
  [_shared/copy-rules.md](_shared/copy-rules.md), [_shared/network.md](_shared/network.md)
- Blank starters: [_templates/](_templates/)
- Scripts: [_tools/](_tools/) (Python standard library, plus `_tools/settle.ts` run with `npx tsx`)
- Smart contract and its tests: [contract/](contract/) (Rust, near-sdk)
- Agent library used by the scripts: [agent/src/](agent/src/)
- Human overview and setup: [README.md](README.md)

## Rules for any agent working here
1. Stop at every Check and wait for the person before the next stage.
2. Never print, log or commit keys. NEAR keys live in `~/.near-credentials/`, oracle keys in `.keys/` (gitignored), the model key in env `NEAR_AI_CLOUD_API_KEY`.
3. Testnet or local sandbox only. No mainnet, no real money. Stage 05 is dry quotes only.
4. All data is SAMPLE DATA. Do not add real transcripts.
5. Follow the copy rules for anything you write.
6. Status lives on disk: whatever exists in a stage's output folder is where the run stands.
7. No deploys, no git push, no new remotes from an agent session. Testnet signing and deploys are done by a person outside the agent.
8. Never ask for, accept or read credentials, seed phrases or signing keys.

## Walk test
`python3 -I _tools/links.py` checks that every path in these map files resolves.
