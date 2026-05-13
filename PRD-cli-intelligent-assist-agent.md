# PRD: Sanctum CLI Intelligent Assist Agent

| Field | Value |
|---|---|
| Status | Draft v1.0 |
| Date | 2026-05-11 |
| Owner | Digital Sanctum |
| Primary repo | `sanctum-cli` |
| Supporting repo | `sanctum-router` |
| Product area | Agent operations, CLI UX, Sanctum Core integration |
| Related artefact | `BUSINESS-CASE-cli-intelligent-error-interpreter.md` in `sanctum-router` |

## 1. Summary

Build an intelligent assist layer into Sanctum CLI so AI agents and operators can recover from malformed CLI calls and, in later phases, express operational intent in natural language. The feature must cover the full Sanctum CLI surface, not only project-management commands.

The CLI remains the primary interface for agents. Sanctum Router provides model routing, intent interpretation, and policy-aware reasoning when deterministic repair is not enough. The CLI owns command parsing, confirmation, execution, safety gates, audit logging, and integration with Sanctum Core and related Sanctum apps/services.

The MVP is an error interpreter: when a CLI invocation fails due to known command-shape errors, the CLI captures the failed command and error output, generates a corrected command using deterministic rules where possible, optionally calls Sanctum Router for inference, asks for confirmation when needed, and executes only validated operations.

The long-term capability is a Sanctum CLI Agent: a command-native assistant that can translate requests such as "find all milestones and tickets for Sanctum Router" or "draft a resolution comment for ticket 3293 and show me the command to resolve it" into validated CLI operations.

## 2. Problem Statement

AI agents using Sanctum CLI frequently mis-call the CLI. Analysis of 299 Opencode sessions and 6,026 Sanctum CLI invocations found 486 known CLI-level errors. 180 of 299 CLI-using sessions had at least one CLI error, with an average of 3.8 errors per affected session.

Common failures include:

- Placing global flags such as `--json` after the command instead of before the command group.
- Using non-existent options such as `--project` instead of `--project-id`.
- Using singular command groups such as `ticket` instead of `tickets`.
- Omitting required options.
- Passing invalid enum, date, UUID, or identifier values.
- Guessing invoice, article, ticket, mockup, flow, or time-entry command syntax from memory instead of inspecting the command schema.

Click often emits useful deterministic errors, including `Did you mean` suggestions, but calling agents repeatedly fail to interpret and apply those corrections. This wastes tokens, time, context window, API calls, and operator attention.

## 3. Goals

- Reduce failed Sanctum CLI retry loops caused by malformed command syntax.
- Make the first post-confirmation execution correct for supported intents.
- Preserve Sanctum CLI as the stable operational interface for agents and humans.
- Use Sanctum Router for inference only where deterministic command-schema repair is insufficient.
- Support the complete CLI command surface across Sanctum Core and related apps/services.
- Provide a scaffoldable implementation plan for the Sanctum CLI agent to create tickets, phases, tests, and documentation.
- Capture structured correction telemetry so recurring CLI UX issues can be fixed deterministically.

## 4. Non-Goals

- Do not replace Sanctum CLI with a direct Router API as the primary operator interface.
- Do not make the LLM responsible for writing final shell commands free-form.
- Do not auto-execute write, destructive, or externally visible operations without explicit confirmation.
- Do not introduce long-term free-form personal memory for the CLI Agent.
- Do not broaden this into a general assistant for arbitrary shell commands outside the Sanctum CLI domain.
- Do not bypass existing Sanctum Core permissions, ticket lifecycle rules, phase criteria, or billable item gates.

## 5. Users and Callers

| Caller | Usage |
|---|---|
| Opencode agents | Run CLI commands during ticket delivery, documentation, verification, project management, and service operations. |
| Human operator | Runs `sanctum` directly and can opt into assist mode for command repair or natural-language operations. |
| Sanctum delivery agents | Surgeon, Architect, Sentinel, Scribe, Oracle, Guardian, Hermes, Chat, Mock, and other configured identities. |
| Automation jobs | May use structured non-interactive assist responses in CI, scripts, or service workflows where enabled. |

## 6. Scope: CLI Domains to Support

The feature must treat Sanctum CLI as an ecosystem operations tool, not just a project/ticket API wrapper. The assist layer must be designed to support all first-class CLI command domains and any future domains added via the command registry.

Required initial domain coverage:

| Domain | Common operations assist must understand |
|---|---|
| Tickets | Show, list, create, update, transition, resolve, comment, assign, phase criteria, available transitions, billable gate checks. |
| Time entries | Create, list, validate start/end ISO timestamps, associate with tickets. |
| Projects | List, show, resolve by name, inspect milestones/tickets, update metadata where supported. |
| Milestones | List, show, create/update where supported, filter by project, resolve by name/UUID. |
| Articles/KB | Show, list, search, create/update, publish where supported, handle `--content`, identifiers, slugs, categories. |
| Search | Route queries through the search command with correct agent identity and output format. |
| Artefacts | Create, show, link, update metadata, avoid malformed content/payload flags. |
| Invoices | Show, list, create/update where supported, send, send receipt, validate recipient/CC flags and IDs. |
| Catalog/products | List, show, search product catalog items and services. |
| Contacts/accounts/CRM | List, show, create/update where supported, resolve names/IDs, avoid wrong entity identifiers. |
| Notifications | List, show, send or create where supported, distinguish notification records from delivery actions. |
| Mockups | Create/update/show mockups, validate `--mime-type`, `--content`, project/ticket associations. |
| Forms | Use supported Forms commands when present, including API/operator operations and submission lookup. |
| Flow | Use `sanctum flow` commands, API key requirements, definitions, instances, simulations, step updates. |
| Monitor/service operations | Health/status checks, service inspection, and any monitor-specific commands exposed by CLI. |
| Auth/user identity | Commands for agent/user identity where supported; never expose or log tokens. |
| Global flags | `--agent`, `--user`, `--json`, `--api-key`, output flags, environment expectations. |

The implementation must not hard-code only the table above. It must introspect or register the command tree so new CLI domains become assistable with minimal extra code.

## 7. Product Shape

### 7.1 Phase 1: Error Interpreter MVP

Agents continue calling Sanctum CLI directly. Assist activates after a failed command or through an explicit command.

Example failed call:

```bash
sanctum --agent surgeon tickets show --json 3293
```

Current error:

```text
Error: No such option: --json
Hint: --json is a global flag - place it before the command name.
```

Assisted behaviour:

```text
Sanctum CLI Assist inferred you intended to show ticket 3293 as JSON.

Corrected command:
sanctum --agent surgeon --json tickets show 3293

Proceed? [y/N]
```

For non-interactive agent mode, return a structured payload instead of an interactive prompt.

### 7.2 Phase 2: Natural-Language Assist Command

Add an explicit intent interface:

```bash
sanctum --agent surgeon assist "Find all milestones and tickets for Sanctum Router"
```

The CLI Agent resolves the project, plans operations, validates the plan, executes read operations, and returns a combined response.

### 7.3 Phase 3: Agent-Native Structured Protocol

Expose machine-readable repair and intent responses for Opencode/agent callers:

```bash
sanctum --agent surgeon --json assist "Find all unresolved tickets for project Sanctum Router grouped by milestone"
```

Response shape:

```json
{
  "status": "success",
  "intent": "Find unresolved tickets for project Sanctum Router grouped by milestone",
  "resolved_entities": {
    "project": {
      "id": "...",
      "name": "Sanctum Router"
    }
  },
  "operations": [
    {
      "domain": "projects",
      "action": "resolve_by_name",
      "risk": "read"
    },
    {
      "domain": "milestones",
      "action": "list",
      "risk": "read"
    },
    {
      "domain": "tickets",
      "action": "list",
      "risk": "read"
    }
  ],
  "result": {
    "milestones": [],
    "tickets_by_milestone": []
  }
}
```

## 8. Architecture

### 8.1 Ownership Boundary

| Component | Responsibility |
|---|---|
| `sanctum-cli` | Detect CLI errors, capture context, own CLI UX, introspect command schema, validate operations, confirm risky actions, execute commands/API calls, log correction outcomes. |
| `sanctum-router` | Route inference requests, classify ambiguous intent, choose model, enforce model policy, return structured interpretation. |
| Sanctum Core | Authoritative data source for tickets, articles, projects, milestones, invoices, CRM, artefacts, catalog, notifications, and related domains. |
| Satellite services | Authoritative APIs for domains outside Core where CLI supports them, such as Flow, Forms, Monitor, Mock, or Router. |

### 8.2 Internal CLI Modules

Recommended modules in `sanctum-cli`:

| Module | Purpose |
|---|---|
| `sanctum_cli/assist/__init__.py` | Assist package entrypoint. |
| `sanctum_cli/assist/errors.py` | Parse Click/API error output into structured error classes. |
| `sanctum_cli/assist/patterns.py` | Deterministic correction patterns for known failures. |
| `sanctum_cli/assist/schema.py` | Command registry/introspection for Click groups, commands, arguments, options, global flags, types, choices. |
| `sanctum_cli/assist/intent.py` | Typed operation plan models and validation. |
| `sanctum_cli/assist/router_client.py` | Client for Router inference endpoints. |
| `sanctum_cli/assist/executor.py` | Execute validated operation plans via existing CLI command functions or API clients. |
| `sanctum_cli/assist/safety.py` | Risk classification, confirmation requirements, destructive-operation refusal rules. |
| `sanctum_cli/assist/session.py` | Short-lived assist session context. |
| `sanctum_cli/assist/feedback.py` | Sanitized correction telemetry. |
| `sanctum_cli/commands/assist.py` | `assist`, `explain-error`, and related user-facing commands. |

### 8.3 Router Supporting Endpoint

Router should expose an endpoint for inference when deterministic repair cannot produce a high-confidence result.

Proposed endpoint:

```http
POST /v1/cli-interpret
```

Request:

```json
{
  "mode": "error_repair",
  "failed_command": "sanctum --agent surgeon tickets show --json 3293",
  "error_output": "Error: No such option: --json",
  "calling_agent": "surgeon",
  "cwd": "/home/preginald/Dev/sanctum-router",
  "available_domains": ["tickets", "projects", "articles"],
  "schema_digest": "sha256:...",
  "sanitized_context": {
    "task_hint": "deliver ticket 3293"
  }
}
```

Response:

```json
{
  "status": "interpreted",
  "confidence": 0.94,
  "match_type": "inferred",
  "inferred_intent": "Show ticket 3293 as JSON",
  "operation_plan": [
    {
      "domain": "tickets",
      "action": "show",
      "parameters": {
        "ticket_id": 3293,
        "json": true
      },
      "risk": "read"
    }
  ],
  "needs_confirmation": false,
  "message": "Move --json before the command group."
}
```

Router must return typed operation plans, not shell commands as the authoritative output. The CLI may display generated commands, but final generation and validation happen inside `sanctum-cli`.

## 9. Command UX

### 9.1 Assist Mode Configuration

Support all of the following:

```bash
SANCTUM_CLI_ASSIST=1 sanctum --agent surgeon tickets show --json 3293
```

```bash
sanctum --assist --agent surgeon tickets show --json 3293
```

```bash
sanctum --agent surgeon assist "Find all milestones and tickets for Sanctum Router"
```

```bash
sanctum --agent surgeon explain-error --failed-command "sanctum tickets show --json 3293" --error-output "Error: No such option: --json"
```

### 9.2 Interactive Output

For human terminal sessions:

```text
Sanctum CLI Assist detected a malformed command.

Inferred intent:
Show ticket 3293 as JSON using the surgeon identity.

Corrected command:
sanctum --agent surgeon --json tickets show 3293

Risk: read-only
Confidence: 0.98

Run corrected command? [Y/n]
```

### 9.3 Non-Interactive JSON Output

For agent/tool sessions:

```json
{
  "status": "assist_confirmation_required",
  "inferred_intent": "Resolve ticket 3293",
  "risk": "write",
  "confidence": 0.88,
  "generated_command": "sanctum --agent surgeon tickets resolve 3293 -b '<body>'",
  "expected_outcome": "Add a resolution comment and transition ticket 3293 to resolved.",
  "missing_fields": ["resolution_body"],
  "confirmation_prompt": "Provide a resolution body and confirm before execution."
}
```

## 10. Operation Plan Model

The CLI Agent must convert all inferred user intent into a typed operation plan before execution.

Example:

```json
{
  "operations": [
    {
      "id": "resolve_project",
      "domain": "projects",
      "action": "resolve_by_name",
      "parameters": {
        "name": "Sanctum Router"
      },
      "risk": "read"
    },
    {
      "id": "list_milestones",
      "domain": "milestones",
      "action": "list",
      "parameters": {
        "project_id": "${resolve_project.id}"
      },
      "risk": "read"
    },
    {
      "id": "list_tickets",
      "domain": "tickets",
      "action": "list",
      "parameters": {
        "project_id": "${resolve_project.id}"
      },
      "risk": "read"
    }
  ]
}
```

Validation requirements:

- Domain exists in command registry.
- Action exists for the domain.
- Required parameters are present.
- Parameter types match expected types.
- Enum values are valid.
- Referenced operation outputs exist.
- Calling agent identity is allowed for the operation.
- Risk class is assigned before execution.
- Write/destructive operations require confirmation.

## 11. Correctness Strategy

The CLI Agent must not rely on the LLM to write correct commands. The LLM may infer intent; deterministic code must validate and generate execution calls.

Required correctness controls:

- Generate commands/API calls from typed templates or direct Python command adapters.
- Validate operation plans against a command schema generated from Click or a manually maintained registry.
- Dry-run parse generated CLI commands before execution where command execution is shell-style.
- Prefer direct invocation of existing Python command functions or API clients over shelling out to `sanctum` recursively.
- Run preflight checks for domain-specific business rules.
- Return a structured unsupported/missing-field response instead of guessing.

Acceptance standard:

> For supported intents, the CLI Agent must either execute a validated correct operation on the first post-confirmation attempt or refuse with a specific missing-field or unsupported-operation message. It must not guess-execute malformed commands.

## 12. Safety and Risk Classification

Every operation must be classified before execution.

| Risk | Examples | Execution rule |
|---|---|---|
| `read` | Show/list/search tickets, articles, projects, monitor status. | May auto-execute in assist mode after validation. |
| `write` | Create/update tickets, articles, comments, time entries, mockups, contacts. | Requires explicit confirmation unless caller provides a trusted non-interactive confirmation flag. |
| `external_effect` | Send invoice, send notification, publish article, trigger deploy/action. | Requires explicit confirmation and expected outcome summary. |
| `destructive` | Delete, revoke, irreversible state change, credential rotation. | Refuse by default or require explicit operator-level confirmation if such operations are ever supported. |

The assist layer must never bypass existing server-side permissions. It must use the calling agent or user identity.

## 13. Context and Memory Model

The CLI Agent needs bounded operational memory only.

### 13.1 Per-Request Context

- Failed command or natural-language intent.
- Error output.
- Calling agent or user identity.
- Current working directory.
- CLI version and schema digest.
- Safe task hints when available.
- Redacted environment metadata only where needed.

### 13.2 Short-Lived Session Context

- `assist_session_id`.
- Prior failed attempts in the same repair loop.
- Suggestions accepted/rejected.
- Missing values supplied by caller.
- Expiry: 15-60 minutes.

### 13.3 Deterministic Schema Context

- Command groups.
- Commands.
- Options and arguments.
- Required/optional flags.
- Choices/enums.
- Global flag placement rules.
- Agent identity requirements.

### 13.4 Feedback Store

Store sanitized training/correction records:

```json
{
  "failed_command_redacted": "sanctum --agent surgeon tickets show --json 3293",
  "error_class": "no_such_option",
  "corrected_operation": {
    "domain": "tickets",
    "action": "show"
  },
  "accepted": true,
  "match_type": "deterministic",
  "cli_version": "...",
  "schema_digest": "sha256:..."
}
```

Do not store tokens, passwords, API keys, bearer headers, secret payloads, or raw environment dumps.

## 14. Deterministic Pattern Library

Phase 1 must include deterministic handlers for the highest-frequency errors.

| Pattern | Example | Expected correction |
|---|---|---|
| Global `--json` misplaced | `sanctum tickets show --json 3293` | Move `--json` before command group. |
| Click `Did you mean` | `--project` with hint `--project-id` | Substitute hinted option after schema validation. |
| Singular/plural command | `ticket list` | Suggest `tickets list` if command exists. |
| Missing required option | `Missing option '--description'` | Prompt for missing value or infer only if safely present in context. |
| Unexpected extra argument | Extra email/ID/date | Match against required missing flags and command signature. |
| Invalid enum | Bad status/type | Show valid choices and ask for selection. |
| Invalid UUID/ID | Wrong identifier shape | Resolve by name where domain supports it; otherwise ask for valid ID. |
| Global `--agent` omitted | `sanctum tickets list` | Infer from context only if safe; otherwise ask for agent. |
| `--api-key` missing for Flow | Flow command auth error | Prompt for API key env/config, do not expose key. |
| Content flag malformed | Article/mockup content issues | Suggest file/content usage based on supported command options. |

## 15. Domain-Specific Preflight Rules

### 15.1 Tickets

- Fetch ticket before transition when status-sensitive.
- Read `available_transitions` before recommending status changes.
- Apply required phase criteria before leaving gated statuses.
- Require time entry or material before resolution when Billable Item Gate applies.
- Prefer `tickets resolve` for resolution comments where supported.

### 15.2 Articles/KB

- Distinguish article identifier, slug, and UUID.
- Use `--content` only where supported.
- Confirm before publishing or overwriting article content.
- Prefer scribe identity for article operations unless caller explicitly chooses another valid identity.

### 15.3 Invoices and Notifications

- Treat send actions as `external_effect`.
- Confirm recipients, CC, subject/message where applicable.
- Validate invoice/contact/account identifiers before sending.

### 15.4 Mockups and Artefacts

- Validate MIME type.
- Confirm large content payload handling.
- Validate links to ticket/project/article where provided.

### 15.5 Flow and Satellite Services

- Respect service-specific authentication such as Flow API keys.
- Do not log API keys.
- Validate definitions, instance IDs, and step IDs before write actions.

### 15.6 Search

- Treat search as read-only.
- Preserve quoted queries.
- Prefer oracle identity for broad ecosystem search when caller has not specified a more appropriate identity.

## 16. Router Model Policy

Use Router only after deterministic schema repair cannot produce a high-confidence result or when natural-language intent is explicitly requested.

Suggested model routing:

- Pattern matched correction: no LLM call.
- Low-risk ambiguous read intent: cheap fast model.
- Multi-step operational planning: stronger reasoning model.
- Write/external-effect operation planning: stronger model plus deterministic validation and confirmation.
- Destructive operation: no automatic inference execution.

Router responses must include confidence, reasoning summary, operation plan, risk class, missing fields, and whether confirmation is required.

## 17. Observability and Metrics

Track:

- Number of CLI errors intercepted.
- Error classes by command/domain.
- Deterministic vs Router-assisted correction rate.
- Accepted vs rejected suggestions.
- First post-confirmation success rate.
- Average retries avoided.
- Latency added by assist.
- Top confusing commands/options.
- Commands refused due to safety rules.

Success metrics for MVP:

- Reduce repeated CLI syntax retry loops by at least 70% for covered error patterns.
- Achieve at least 95% first post-confirmation success for deterministic patterns.
- Zero auto-executed write/external-effect operations without confirmation.
- Zero secret leakage in assist logs during tests.

## 18. Implementation Phases

### Phase 0: Discovery and Scaffold

- Inventory current CLI command tree and global flags.
- Identify all command groups and supported domain modules.
- Create implementation project in Sanctum Core.
- Create tickets for CLI work, Router work, tests, docs, and deployment.
- Link this PRD as the source artefact.

### Phase 1: Deterministic Error Interpreter

- Add error parsing and assist response models.
- Add command schema registry/introspection.
- Implement top deterministic correction patterns.
- Add `SANCTUM_CLI_ASSIST=1` and `--assist` support.
- Add `explain-error` command for offline repair.
- Add tests for known real-world failures.
- No Router dependency required for deterministic patterns.

### Phase 2: Router-Backed Intent Interpretation

- Add Router client.
- Add `POST /v1/cli-interpret` support in Router.
- Send sanitized context and command schema digest.
- Accept typed operation plans from Router.
- Validate returned plans before display/execution.
- Add tests with mocked Router responses.

### Phase 3: Natural-Language `assist` Command

- Add `sanctum --agent <agent> assist "..."`.
- Support read-only multi-step plans across common domains.
- Support name-to-ID resolution for projects, tickets where possible, articles, contacts, accounts, and milestones.
- Return combined structured results in JSON mode.
- Require confirmation for writes.

### Phase 4: Write Workflows and Confirmation Protocol

- Add safe write workflows for comments, time entries, article drafts, mockup updates, ticket status changes, and other common operations.
- Add non-interactive confirmation protocol for agent callers.
- Add domain-specific preflight rules.
- Add external-effect confirmation for invoice/notification sends and publish actions.

### Phase 5: Feedback Loop and UX Improvements

- Store sanitized correction outcomes.
- Generate reports for recurring CLI confusion.
- Add aliases or deterministic CLI improvements where data supports them.
- Add KB documentation and operating procedures.

## 19. Testing Requirements

### 19.1 Unit Tests

- Error parser classification.
- Pattern correction logic.
- Command schema generation.
- Operation plan validation.
- Safety/risk classification.
- Redaction of secrets.
- Router client request/response handling.

### 19.2 Integration Tests

- Invoke CLI with known bad commands and verify assist suggestions.
- Verify deterministic corrections dry-run parse successfully.
- Verify read-only corrections execute when enabled.
- Verify write operations require confirmation.
- Verify malformed Router operation plans are rejected.
- Verify global flags are placed correctly.

### 19.3 Regression Fixtures

Use real failure patterns from the Opencode session analysis, including:

- `--json` after command.
- `--project` vs `--project-id`.
- `ticket` vs `tickets`.
- Invoice `send-receipt` recipient/CC variants.
- Missing required options.
- Invalid enum values.
- Flow API key/auth handling.

### 19.4 Security Tests

- Tokens, passwords, API keys, bearer headers, and `.env` values are redacted.
- Write/external-effect commands cannot auto-run without confirmation.
- Destructive commands are refused or operator-gated.
- Calling identity is preserved in all generated operations.

## 20. Documentation Requirements

- Update `README.md` with assist mode overview.
- Add CLI help text for `assist` and `explain-error`.
- Create KB article: `Sanctum CLI Intelligent Assist Agent - Operator Guide`.
- Create KB article or section: `Sanctum CLI Assist Safety Model`.
- Document Router endpoint contract if `POST /v1/cli-interpret` is implemented.
- Document feedback/telemetry retention and redaction rules.

## 21. Acceptance Criteria

MVP acceptance:

- `SANCTUM_CLI_ASSIST=1` activates assist behaviour for malformed CLI calls.
- `--assist` activates assist behaviour for a single invocation.
- `explain-error` can produce structured suggestions from a failed command and error output.
- Deterministic handlers cover at least the top 10 known error patterns from session analysis.
- Corrected commands are generated from schema/templates, not free-form model text.
- Generated commands pass dry-run parse or operation-plan validation before execution.
- Read-only deterministic corrections can execute after validation when configured.
- Write/external-effect operations require confirmation.
- JSON mode returns machine-readable assist payloads.
- Tests cover parser errors, corrections, validation, safety, and redaction.

Full feature acceptance:

- `sanctum --agent <agent> assist "<intent>"` supports common read workflows across tickets, projects, milestones, articles, search, invoices, contacts/accounts, artefacts, catalog, mockups, Flow, Forms, Monitor, and service commands available in the CLI.
- Router-backed interpretation produces typed operation plans only.
- CLI validates all Router operation plans before execution.
- First post-confirmation execution succeeds for at least 95% of supported deterministic and schema-valid intents.
- Unsupported or underspecified intents return clear missing-field/unsupported-operation responses.
- Correction telemetry identifies recurring CLI UX issues without storing secrets.

## 22. Project Scaffold Guidance for Sanctum CLI Agent

When taking over from this PRD, scaffold a Sanctum Core project with milestones similar to:

1. **Phase 1: Command Schema and Deterministic Repair**
2. **Phase 2: Assist UX and JSON Protocol**
3. **Phase 3: Router Interpretation Endpoint**
4. **Phase 4: Natural-Language Assist Workflows**
5. **Phase 5: Safety, Telemetry, and Documentation**

Initial tickets should include:

- Inventory CLI command tree and generate assist schema.
- Implement structured error parser.
- Implement deterministic correction pattern library.
- Add `--assist` and `SANCTUM_CLI_ASSIST` activation.
- Add `explain-error` command.
- Add operation plan model and validator.
- Add risk classification and confirmation protocol.
- Add Router client and mocked integration tests.
- Implement Router `POST /v1/cli-interpret` endpoint.
- Add natural-language `assist` command for read workflows.
- Add domain preflight rules for tickets, articles, invoices, mockups, Flow, and service operations.
- Add telemetry/redaction store.
- Write operator KB documentation.
- Verify with Opencode-style CLI failure fixtures.

Each ticket should include explicit acceptance criteria, test requirements, and whether it touches `sanctum-cli`, `sanctum-router`, or documentation.

## 23. Open Questions

- Should `--assist` be a global flag, or should assist activation be environment-only for MVP to avoid Click parser complications?
- Should deterministic read-only corrections auto-execute by default in agent contexts, or only return suggestions until confidence is proven in production?
- Where should correction telemetry be stored: local file, Sanctum Core table, Router observability, or a dedicated CLI feedback endpoint?
- Which satellite service command schemas are currently available in `sanctum-cli`, and which need adapter work before natural-language assist can cover them?
- What is the exact non-interactive confirmation contract Opencode agents should use for write operations?
