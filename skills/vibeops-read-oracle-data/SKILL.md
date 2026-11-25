---
name: vibeops-read-oracle-data
description: Query Oracle data or inspect column metadata using approved connection profiles and registered SELECT queries. Use when SDLC work needs database evidence, schema verification, or bounded Oracle reads across supported Thin and Thick environments.
compatibility: Requires Python 3.11+, python-oracledb, an authorized read-only DB account, local profile configuration and database network access. Thick mode additionally requires a compatible Oracle Client.
---

# Query Oracle

This is a shared capability for existing agents, not a dedicated DB agent. Use the host terminal. No MCP or agent runtime is required.

1. Establish the question, authorized database ID and required fields. Never infer a production target or request credentials in chat. If the ID is ambiguous, resolve it before querying.
2. Read [execution procedure](references/execution.md). For missing connection setup or version errors, read [connection knowledge](references/connections.md). For SQL/result decisions, read [Oracle query rules](references/query-rules.md). Load only the needed page.
3. Use the operator-provided profile via ORACLE_QUERY_CONFIG or --config. Use the operator-selected config and local credential references. Do not print their contents or alter credentials/registered SQL to bypass policy.
4. If database-specific meaning is needed, use sibling vibeops-search-wiki with the target project's DB-specific knowledge path from project instructions. Search only that DB scope. Common references here contain no company schema knowledge. If no mapping exists, report missing knowledge rather than reading all DB wikis.
5. Write a JSON request containing check, describe or an allowed registered query ID and bind values. Use a protected local file or stdin for sensitive binds. Do not insert untrusted values into SQL strings.
6. Run `python <this-skill>/scripts/oracle_client.py --database ID --request REQUEST_FILE` using the installed skill's absolute path. For multiple related queries on one DB, send up to 20 requests in one invocation so the connection and read-only transaction are reused. Separate database IDs/modes require separate invocations.
7. Inspect ok, actual database version, returned_rows and truncated. A truncated or empty result is not proof that no matching data exists. Result timeouts and errors are not test successes. Do not automatically retry a long-running query or expand the query budget.
8. Return the query ID, database ID, observation, limitations and timing without exposing credentials or unnecessary raw records. DB evidence supplements but never replaces implementation tests.

Only approved SELECT statements from an operator-owned catalog are executed. The syntax guard is not a security sandbox. DB read-only privileges and host execution permissions are required. Current authentication supports username/password via environment or local credential references; Wallet/external-auth profiles are not implemented. Do not claim all Oracle 11g combinations are supported.

Use shared/python/oracle_client through scripts/oracle_client.py. Changes belong to sibling vibeops-modify-oracle-data and must never be routed through a SELECT. See ../../docs/DATA_ACCESS.md for dependency installation and external configuration.

Consult ../../wiki/Credentials.md for approved profile mappings. Let the client resolve credentials.
