---
name: vibeops-verify-change
description: Review test cases against accepted requirements before running acceptance and regression checks and report quantitative results from observed test data.
---

# vibeops-verify-change

1. Before executing tests, derive expected outcomes from the accepted requirements and scenario IDs independently of the implementation summary. Review each proposed case for the actual entry point, input and preconditions, expected result, and assertion that could detect an incorrect implementation. Cover normal behavior and applicable boundary, exception and regression scenarios. Fix incorrect cases based on the specification. Record missing or ambiguous cases and leave them unverified until resolved. Freeze the reviewed case IDs and expected outcomes before running checks.
2. Run the reviewed checks with representative test data. Check that tests were discovered and record the command, exit code, observed output, tested revision or working-tree state, and dataset source/version. Record the data slice or sample size and each scenario's observed outcome with a reference to execution evidence. Never infer a pass from a model summary, an empty run, or a test that failed to execute. Redact sensitive data.
3. Follow [quantitative reporting](references/quantitative-report.md) to build the evidence JSON and calculate the Markdown summary using the installed `vibeops-verify-change/scripts/summarize_results.py`. Use the absolute path under the plugin root when running in a ticket worktree or using generated role instructions. Include the summary and case-review decisions in the assigned report_path (standalone default artifacts/test-report.md). Highlight failed, blocked, and unverified scenarios. Return gaps to the orchestrator before recommending completion.
