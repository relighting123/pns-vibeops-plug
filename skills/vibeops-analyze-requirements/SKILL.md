---
name: vibeops-analyze-requirements
description: Analyze feature requirements and acceptance criteria before design or development.
---

# vibeops-analyze-requirements

Read the user request and relevant project documents. Write the assigned report_path (standalone default artifacts/requirements.md) with stable REQ IDs, observable acceptance criteria, scope exclusions, constraints and unresolved decisions. Preserve imported requirement IDs. Ask only about decisions that block correct implementation; record other assumptions. Do not invent missing API contracts.

## Business behavior interview

Apply the requester’s mode per decision. In auto mode (also called YOLO), infer reversible details from project evidence, label assumptions and leave unsupported consequential policy open. In selective mode (default), ask only about unresolved choices that change observable outcomes. In deep mode, follow each answer into its relevant counterexample, one question at a time. Honor item overrides such as “only interview me on HOLD”. Keep existing external approval gates.

For “when A, do X”, model A, non-A and unknown A; distinguish preserving existing behavior from prohibiting it. Consider empty input, exact boundaries, duplicates, concurrent execution, partial failure and existing data. Select applicable cases from evidence; never recite this list as a questionnaire. For example, if non-A keeps its existing behavior, investigate whether HOLD overrides A; if only A is allowed, investigate a change from A before execution.

For each REQ record decided behavior, normal scenario, material exceptions, confirmed/assumed/open status with source, and verification method. Give each scenario a stable ID with inputs, trigger and observable expected result. Stop asking when normal and material exceptions can be written as tests. If a decision remains open, identify impacted scenarios and continue independent work.

## Refine the spec with the requester

1. First inspect existing requirements, relevant code and examples. Summarize the intended user outcome and identify decisions whose answers would change implementation or acceptance tests.
2. Ask the single most consequential unanswered question. Give concrete alternatives and explain their observable effects. Ask in the user's language. A delegated analyst returns the question to the parent session, which owns the conversation.
3. After each answer, update the matching REQ ID in the selected report. For each entry record the outcome, acceptance example (given/when/then), decision source, and status (confirmed, assumed or open). Preserve prior IDs and revise affected criteria if the user corrects an answer.
4. Repeat only while a consequential ambiguity remains. Avoid questions answered by project evidence. If the user defers a decision, identify dependent work and continue independent work. For a clear request, proceed directly. On resume, read the current spec before asking.
5. Hand design and test the REQ IDs, confirmed criteria and remaining assumptions. Test reports link each criterion to its observed result; an open decision stays visible through review.

Example: for "notify me about duplicate requests", ask what identifies a duplicate before choosing storage or timing. If the user specifies the same request ID within ten minutes, record a repeat after nine minutes as an acceptance example and clarify the exact boundary only if it affects behavior.

For quantitative requests, follow sibling vibeops-quantify-requirements/SKILL.md and retain its evidence and measurement conditions under the same REQ ID.

For an ITSM intake assignment, use the operator-provided read-only Oracle profile and the assigned private handoff directory. Run `SDLC_DATA_ROLE=requirements python scripts/itsm_intake.py --config CONFIG --output NEW_FILE` relative to this skill. Return the unchanged handoff path and count to the parent without posting to GitLab. If the read fails, report the failure and discard the partial file.

For ITSM intake, verify the target system and component against the [ITSM to GitLab project mapping](../../wiki/ITSM-GitLab-Mapping.md). If no single verified operational row matches, ask the requester before ticket publication.
