---
name: vibeops-deploy-release
description: Deploy an authorized, tested revision and verify health with rollback readiness.
---

# vibeops-deploy-release

Read the handed-off test and review reports (standalone defaults artifacts/test-report.md and artifacts/review.md). Verify the tested source has not changed. Identify the exact target, deploy command, health check and rollback procedure from project configuration. Use existing user authorization; request authorization only if it is absent. Execute through host tools, record the revision and outcomes in the assigned report_path (standalone default artifacts/deployment.md). On failure execute the agreed rollback. If external effects are uncertain, inspect the target before any retry.
