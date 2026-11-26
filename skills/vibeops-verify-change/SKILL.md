---
name: vibeops-verify-change
description: Run acceptance and regression checks against a proposed implementation.
---

# vibeops-verify-change

Derive inputs and expected results from the accepted requirements before reading the implementation summary. Exercise normal and material exception scenarios through the actual entry point. Compare observations with those expectations under the same REQ/scenario IDs. Record uncovered cases as unverified. Inspect the project test configuration and execute the appropriate commands using the host terminal. Check that tests were discovered. Add missing boundary and failure cases. Record command, exit code, observed output and tested commit or working-tree state in the assigned report_path (standalone default artifacts/test-report.md). Never infer success from a model summary or weaken a test to fit broken behavior.
