# Quantitative verification report

Record the pre-execution review in a table with REQ ID, scenario ID, input and preconditions, expected result, assertion, and review decision. Include the full set of required scenarios even when a runnable case is missing. After execution record the command, exit code, revision, dataset source/version, sample size and evidence location. For a quantitative acceptance criterion report its target, unit, observed value and difference if measured. For example, with a goal of p95 ≤ 6.0 s, a measured 6.1 s is 0.1 s above target. Include the measurement population and conditions.

Prepare a JSON array containing one row per required scenario. Count a scenario once even when several test rows or commands exercise it. For scenario IDs reused by different requirements, qualify the ID with its requirement.

```json
[
  {"requirement":"REQ-001","scenario":"REQ-001-normal","review":"ready","result":"passed","evidence":"test-results.xml#normal"},
  {"requirement":"REQ-001","scenario":"REQ-001-hold","review":"ready","result":"failed","evidence":"test-results.xml#hold"},
  {"requirement":"REQ-002","scenario":"REQ-002-retry","review":"missing","result":"unverified"}
]
```

Review values are `ready`, `rejected` and `missing`. Result values are `passed`, `failed`, `blocked` and `unverified`. A pass or failure requires a ready case and observed evidence. Use blocked for an identified execution obstacle. Use unverified when a required case has no reliable result. If a scenario needs several assertions or data rows, mark it passed only when all needed observations pass.

Run `python /absolute/plugin/root/skills/vibeops-verify-change/scripts/summarize_results.py results.json` and include its output in the test report. Pass rate uses executed scenarios as the denominator. Execution coverage uses all required scenarios. A requirement passes when all of its required scenarios pass. A zero denominator displays as N/A. Report dataset size separately from the number of scenarios.
