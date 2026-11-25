---
name: vibeops-quantify-requirements
description: Turn requests involving speed, cost, capacity, quality or a numeric limit into evidence-backed acceptance criteria through a focused interview.
---

Read the current REQ entry and inspect relevant authorized logs, benchmarks or reports. Use this procedure inside the existing requirements interview. A delegated analyst sends its next question to the parent.

1. Identify the user outcome and the measurable quantity. For latency define start and end events. For rates define numerator and denominator. Specify unit, population, time window and aggregation.
2. Obtain the baseline from reproducible evidence. Record source or command, environment, date, sample count and measured result. Label a user estimate as reported. If evidence is unavailable, record unknown and the specific measurement needed. Use the role's existing access scope.
3. Track five fields per REQ: metric definition, measurement conditions, evidenced baseline, confirmed target with comparator, and repeatable acceptance check. Report completeness as filled / applicable fields and name the gaps. Exclude a baseline only for a documented reason such as a new feature with an absolute limit. A proposed threshold stays open until confirmed. This count describes spec completeness only.
4. Ask one question about the gap most likely to change acceptance. Use prior answers to refine the next question. For a relative improvement compute the implied threshold from the baseline using matching units and direction. Stop once the test can be written and consequential decisions are resolved, or record deferred decisions when the requester stops.
5. Update the existing REQ in artifacts/requirements.md and pass the measurement procedure to verification. Verification records the actual result, evidence and pass/fail under the same conditions. Mark unmeasured outcomes unverified.

Worked example (synthetic): “make responses faster.” First determine whether the user cares about first token or complete response. Suppose a replay of 100 requests measures p95 from submission to final token at 8.0 seconds. A confirmed 25% reduction gives p95 ≤ 6.0 seconds. Replay the same workload, model, concurrency and cache conditions. A measured 6.1 seconds fails. Never reuse these example values as defaults.

Design references: [Superpowers brainstorming](https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md) grounds questions in project evidence. [OMX deep interview](https://github.com/Yeachan-Heo/oh-my-codex/blob/main/skills/deep-interview/SKILL.md) uses scored ambiguity and bounded questioning. This adaptation counts explicit measurement fields for transparent SDLC handoff.
