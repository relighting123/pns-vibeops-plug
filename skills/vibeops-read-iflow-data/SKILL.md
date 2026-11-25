---
name: vibeops-read-iflow-data
description: Read data from iflow through registered operations and external environment profiles. Use when an existing SDLC agent needs bounded evidence from iflow.
compatibility: Requires Python 3.11+, the complete plugin including shared/python, approved dependencies, external profiles and network access.
---

# vibeops-read-iflow-data

Read ../../docs/DATA_ACCESS.md for setup and shared contract, and ../../docs/NAMING.md for terminology. Never invent endpoints, credentials or operation schemas.
1. Establish the user's requested target, environment and read criteria. Do not infer production access.
2. Read only the selected service operation definition and relevant business wiki sections. Use the external HTTP_ACCESS_CONFIG profile and operation catalog. The operator profile selects the credential source.
3. Use only operations classified read, regardless of HTTP method. Batch independent reads of one profile when useful.
4. Create a protected JSON request file or use stdin. Run python <this-skill>/scripts/iflow_client.py --profile ID --request FILE. Resolve paths from the installed skill directory.
5. Inspect ok, truncated and returned evidence. Do not equate empty/truncated output with absence. Do not raise budgets automatically.
6. Return the selected operation, target ID, relevant evidence, limits and timing. Never disclose credentials or unnecessary raw data.

This skill uses shared client code; it does not provide a separate agent or model runtime. The host's permissions and the service/DB account enforce the actual access boundary.

Consult ../../wiki/Credentials.md for approved profile mappings. Let the client resolve credentials.
