# Strategy Brief: Sanctum Operations Interface

| Field | Value |
|---|---|
| Status | Draft |
| Date | 2026-05-16 |
| Owner | Digital Sanctum |
| Primary systems | Sanctum Chat, Sanctum Router, Sanctum CLI, Sanctum Core |
| Product area | Agent operations, conversational workflows, API execution safety |

## 1. Executive Summary

Sanctum has evolved from a guarded Core API into a broader ecosystem of CLI, MCP, Router, and Chat interfaces. Each layer improved part of the operator or agent experience, but the current agent-facing workflow still asks probabilistic callers to produce exact command structures for stateful, rule-heavy operations.

The strategic direction should shift from command syntax repair to a conversational Sanctum Operations Interface: a stateful layer that accepts intent from humans or agents, gathers missing information, validates requirements, previews risky actions, executes through deterministic tools or API clients, and returns structured results.

Sanctum Chat is the strongest candidate for this experience because it already provides conversational context, model routing through Sanctum Router, tool and agent integration, and both web and API access.

## 2. Background: Journey So Far

Sanctum Core was originally built with strict guards and validation to prevent dirty data from entering the database. This remains the correct foundation: Core should reject incomplete, malformed, unsafe, or lifecycle-invalid data.

The first operational interface was a shell-based Sanctum CLI that called the Core API. This gave operators a lightweight way to interact with Sanctum from the terminal, but it was limited as the platform grew.

An MCP interface was then introduced for Claude and other AI agents. MCP made Sanctum operations more directly available to agents, but the tool surface grew large enough to consume valuable model context and increase operational complexity.

To reduce MCP context load and provide a more conventional automation surface, a second-generation Python Click-based Sanctum CLI was implemented. This gave Sanctum a stronger command structure, domain separation, and explicit options.

In practice, coding agents had significant friction with the Python CLI. Agents frequently produced malformed commands on the first attempt, then repeatedly queried help output and retried until discovering the right syntax. The problem was not just poor command memory; the CLI required exact syntax for operations whose valid shape often depends on server state, lifecycle rules, identity, and missing business data.

Sanctum Router was then introduced as an AI-powered natural-language middleware intended to infer a caller's intent and form a correct request for the CLI. This improved ergonomics in some cases, but the one-shot inference model remained unreliable for complex workflows. Many Sanctum operations require clarification and stateful slot filling rather than a single translated command.

## 3. Problem Statement

Sanctum currently exposes too much command-shape responsibility to humans and agents.

Agents and users often express valid high-level intent, such as "resolve this ticket" or "create a KB article from this delivery", but the actual operation requires additional state and data:

- correct domain and agent identity
- required IDs or resolvable entity names
- lifecycle status and available transitions
- phase criteria
- billable item gates
- confirmation for writes or external effects
- evidence requirements for delivery workflows
- API-specific validation rules

The Core API correctly rejects incomplete or invalid requests. However, the current interfaces often discover missing information only after a failed execution attempt. This creates retry loops, wasted tokens, inconsistent outcomes, and operator frustration.

The core problem is not that agents need a better way to memorize CLI syntax. The core problem is that Sanctum needs an operations layer that can hold conversational workflow state, collect missing fields, validate before execution, and execute only when the request is complete.

## 4. Why Previous Approaches Fell Short

### 4.1 Shell CLI

The shell CLI was useful for early operational access but did not provide enough structure for a growing domain surface.

### 4.2 MCP

MCP made tools accessible to agents, but the surface area expanded to the point where tool definitions consumed valuable model context. As Sanctum domains grew, this approach became harder to scale cleanly.

### 4.3 Python Click CLI

The Python CLI provided a strong deterministic command interface. It is valuable for humans, scripts, and automation that already know the exact command shape.

However, Click syntax is brittle for probabilistic coding agents. A misplaced global flag, singular command group, wrong option name, missing required field, or invalid enum value can fail the first attempt. Agents then spend multiple turns discovering syntax rather than completing the operation.

### 4.4 Natural-Language Router Middleware

Sanctum Router improved the ability to interpret intent, but a one-shot resolver is the wrong shape for many Sanctum operations. Complex operations require a conversation:

- inspect current state
- determine missing information
- ask targeted questions
- validate candidate actions
- preview the operation
- execute only after confirmation or policy approval

The issue is not merely natural-language parsing accuracy. It is the absence of durable workflow state and deterministic operation schemas.

## 5. Desired Result

Sanctum should provide a reliable conversational operations surface for both humans and agents.

The desired future state:

- A user or agent can express operational intent in natural language.
- The system identifies the relevant Sanctum domain and workflow.
- The system inspects required state before attempting writes.
- Missing fields are collected conversationally.
- The operation is validated against schemas, permissions, lifecycle rules, and API constraints.
- Risky operations are previewed before execution.
- Execution occurs through deterministic tools, shared client functions, or Core APIs rather than free-form shell command generation.
- Results are returned as both human-readable summaries and structured payloads for agent callers.
- Sanctum Core remains the final source of truth and continues enforcing data integrity.

## 6. Proposed Direction

Create a conversational Sanctum Operations Interface backed by workflow agents and deterministic tools.

This layer should be accessible from:

- Sanctum Chat web UI for human operators
- Sanctum Chat API for coding agents and other harnesses
- future automation surfaces that need structured operation results

The interface should not primarily ask models to construct CLI strings. Instead, it should map intent into typed operations and workflows.

Recommended conceptual architecture:

```text
User / Agent
  -> Sanctum Chat
  -> Sanctum Router
  -> Sanctum Operations Agent
  -> Operation Schemas + Workflow State
  -> Deterministic Tools / sanctum_client / Sanctum APIs
  -> Structured Result + Conversational Summary
```

The existing CLI should continue to exist as a precise terminal and scripting interface. It may also be used as a compatibility execution path where necessary. However, agents should not need to learn Click syntax as their primary way to perform Sanctum work.

## 7. Tool And Agent Model

The recommended model separates deterministic tools from higher-level workflow agents.

Tools are narrow, typed, and deterministic. Examples:

- `ticket.show`
- `ticket.update`
- `ticket.transition`
- `ticket.resolve`
- `time_entry.create`
- `article.publish`
- `search.query`

Workflow agents orchestrate multi-step operations using tools. Examples:

- `deliver_ticket`
- `resolve_ticket`
- `triage_ticket`
- `write_kb_article`
- `prepare_release`
- `verify_deployment`

This allows the system to keep execution reliable while still supporting conversational, multi-turn workflows.

## 8. Initial Use Case

The first proving workflow should be ticket resolution or ticket delivery.

This workflow is a strong candidate because it exercises the hardest parts of Sanctum operations:

- ticket lookup
- lifecycle status inspection
- available transition validation
- phase criteria checks
- billable item gate checks
- time entry creation
- resolution comment collection
- engineering delivery evidence when code-bearing
- final status verification

Example interaction:

```text
User: Resolve ticket 3502.

System: Ticket 3502 is in implementation and has no time entry. To resolve it I need:
1. confirmation that implementation is complete
2. time to log
3. resolution summary

User: Implementation is complete. Log 30 minutes. Resolution: fixed Router token refresh handling and verified CLI assist.

System: I will mark implementation_complete=true, add a 30 minute time entry, transition through the required status path, and resolve the ticket with that comment. Proceed?
```

The successful outcome is not that the model generated the correct CLI command. The successful outcome is that the system completed the workflow safely and predictably.

## 9. Success Criteria

The strategy is successful if:

- agents no longer need repeated CLI help-query retry loops for supported workflows
- missing data is requested before execution rather than discovered through API failure
- Core API validation failures decrease for supported operations
- write operations are previewed and confirmed according to risk policy
- the same workflow can serve Chat users and headless agent callers
- responses include structured data suitable for automation
- operational safety is preserved or improved

Candidate metrics:

- first-attempt supported-workflow completion rate
- average number of failed CLI/API attempts per operation
- number of clarification turns before execution
- number of Core 422 validation errors for supported workflows
- operator intervention rate
- successful ticket delivery/resolution rate with required evidence

## 10. Relationship To Existing CLI Assist Work

The existing CLI assist direction remains useful for command-line ergonomics, deterministic error repair, and shell-based workflows.

This strategy extends the thinking beyond CLI repair. It reframes the long-term interface around conversational operations rather than command construction.

Recommended positioning:

- keep CLI assist for terminal users, scripts, and backwards-compatible command repair
- build Sanctum Operations Interface for Chat users and agent-native workflows
- share operation schemas, validation logic, and deterministic execution code where possible
- avoid duplicating business rules in multiple layers

## 11. Key Open Questions

- Should the Operations Interface call `sanctum_client` directly, call Core APIs directly, or invoke CLI internals as an execution adapter?
- Should workflow state live in Sanctum Chat, Sanctum Router, or a new Sanctum Operations service?
- What is the right structured response contract for headless agent callers?
- How should confirmation work for trusted automation versus human-driven Chat sessions?
- Which operation schemas should be authored first, and how should they be versioned?
- How should execution telemetry feed future improvements without leaking sensitive data?

## 12. Recommended Next Steps

1. Validate this strategy with the operator and stakeholders.
2. Produce an Architecture Decision Record choosing the target ownership boundary.
3. Draft a technical design for operation schemas, workflow state, tool contracts, and execution adapters.
4. Build a narrow prototype for `resolve_ticket` or `deliver_ticket` through Sanctum Chat.
5. Compare prototype outcomes against current CLI and Router workflows using real ticket operations.
