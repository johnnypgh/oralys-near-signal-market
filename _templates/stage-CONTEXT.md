# NN_name: one line job

model: none (script) | z-ai/glm-5.3-flash (any stage that touches private data)

## Inputs
- `exact/path/to/this-run-input.json`
- `_shared/the-rule-it-needs.md`

## Process
1. Numbered steps. Deterministic steps call a script in `_tools/`.

## Outputs
- `stages/NN_name/output/the-file.ext`

## Check
- The command or the person that must pass before the next stage.
