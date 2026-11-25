---
name: vibeops-modify-oracle-data
description: Modify authorized data in oracle through registered operations and external environment profiles. Use when an existing SDLC agent needs an explicitly requested change from oracle.
compatibility: Requires Python 3.11+, the complete plugin including shared/python, approved dependencies, external profiles and network access.
---

# vibeops-modify-oracle-data

Read ../../docs/DATA_ACCESS.md for setup and shared contract, and ../../docs/NAMING.md for terminology. Never invent endpoints, credentials or operation schemas.
1. Establish the user's requested target, environment and exact change and authorization. Do not infer production access.
2. Read only the selected service operation definition and relevant business wiki sections. Use the external ORACLE_ACCESS_CONFIG database profile and approved writes catalog. The operator profile selects the credential source.
3. For changes, first collect the affected record IDs/current state through the corresponding read skill. Set expected_rows for Oracle. Ensure profile allow_write and operation allowlist are configured; --apply expresses execution intent and is not a substitute for user authorization.
4. Create a protected JSON request file or use stdin. Run python <this-skill>/scripts/oracle_client.py --database ID --request FILE --apply. Resolve paths from the installed skill directory.
5. Inspect ok, outcome and affected rows or HTTP status. Never automatically retry a write. On timeout or unknown outcome, reconcile actual state using the read skill before deciding on another request. HTTP 2xx is acceptance, not proof that an asynchronous business action finished.
6. Verify the requested postcondition using a fresh read and report what is confirmed versus pending. A committed DB change cannot be undone by a later rollback; use an authorized compensating change if required. Never disclose credentials or unnecessary raw data.

This skill uses shared client code; it does not provide a separate agent or model runtime. The host's permissions and the service/DB account enforce the actual access boundary.

Consult ../../wiki/Credentials.md for approved profile mappings. Let the client resolve credentials.
