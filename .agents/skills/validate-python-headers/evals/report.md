# validate-python-headers skill evaluation

Reference environment: Codex CLI 0.149.0, `gpt-5.6-sol`, medium reasoning, fresh Git fixture and process per run. Each workflow ran once with the skill and once without it; timing and token figures therefore describe these observed runs, not repeated-sample confidence.

## Iteration 2 result

| Workflow | With skill | Without skill |
| --- | ---: | ---: |
| Read-only findings | 4/4 | 4/4 |
| Conservative fix | 5/5 | 4/5 |
| Missing policy | 5/5 | 2/5 |
| Invalid policy | 4/4 | 2/4 |
| Integration setup | 5/5 | 4/5 |
| **Total** | **23/23** | **16/23** |

Across the five runs:

- mean execution time: 112.2 seconds with skill, 146.4 seconds without skill;
- mean tokens: 385,057 with skill, 567,433 without skill;
- the skill reduced mean time by 23% and mean tokens by 32%.

The strongest differences were safety contracts:

- missing policy: the skill did not infer an earliest year from Git and reported schema 1, exit 2, and `VPH900`;
- invalid policy: the skill used JSON and stopped on the command error;
- integration setup: the skill used `<RELEASE_TAG_OR_SHA>` and reported the open gate instead of inventing a released `v0.6.0` ref;
- conservative repair: the skill used JSON check before JSON fix and verified the targeted diff.

## Iteration history

Iteration 1 exposed one skill defect: the guided integration wrote `v0.6.0` before that release existed. The instructions now require a verified released ref or an explicit placeholder plus open gate. The integration score improved from 3/5 to 5/5 after that revision.

## Remaining RC gate

`trigger-evals.json` contains ten positive and ten hard near-miss prompts. The skill and eval schema are validated, but the planned three-run activation benchmark is intentionally left for the release-candidate gate because routing behavior is host/model dependent and running it before the final RC would measure a moving artifact.

A Claude Code 2.1.241 install/detection smoke was prepared with the same `SKILL.md`, but the external run stopped before inference because its OAuth session had expired. Cross-host detection therefore remains unverified rather than being inferred from schema validity.
