# PetroBrain TODO

## Top-Notch AI Upgrade: Grounded Source Packs

Goal: make every important PetroBrain answer verifiable, cited, and audit-ready. The user should understand what the AI relied on, what was calculated, what was not verified, and what needs human confirmation.

### Phase 1 - Answer Evidence Panel

- [x] Add a structured `evidence_pack` object to chat responses.
- [x] Include uploaded SOP/manual citations with document title, revision, and clause.
- [x] Include user-safe deterministic calculation outputs.
- [x] Include formulas used by deterministic tools.
- [x] Include web/current sources only as source links, without exposing search queries.
- [x] Include a `not_verified` list for missing documents, missing current-source checks, and guardrail gaps.
- [x] Add frontend UI for a compact evidence panel under important answers.
- [x] Hide internal tool names and raw payloads from this panel.
- [x] Add tests proving raw tool inputs, search queries, and internal identifiers are not rendered to users.
- [ ] Add document chunk IDs to evidence sources once chunk IDs are exposed by retrieval.
- [ ] Add optional user-visible calculation inputs for fields that are safe to disclose back to the same user.

### Phase 2 - Confidence and Verification

- [ ] Add answer confidence labels: `High`, `Medium`, `Low`, `Needs verification`.
- [ ] Base confidence on source quality, calculation completeness, and missing inputs.
- [ ] Mark safety-critical answers with a mandatory human-verification banner.
- [ ] Mark regulatory/compliance answers with source-date and jurisdiction checks.
- [ ] Add a "What I checked" summary in plain language.
- [ ] Add a "What I could not check" summary in plain language.
- [ ] Add backend tests for confidence scoring and missing-input detection.

### Phase 3 - Source Pack Builder

- [ ] Create a normalized source-pack model for each answer.
- [ ] Store source packs with the conversation/audit event.
- [ ] Generate source packs from RAG citations, deterministic tool calls, uploaded files, and web sources.
- [ ] Deduplicate sources across repeated chunks or repeated URLs.
- [ ] Add source-pack export as JSON.
- [ ] Add source-pack export as PDF or printable report.
- [ ] Add admin view for inspecting source packs without exposing secrets or raw prompts.

### Phase 4 - Domain-Specific Answer Modes

- [ ] Add `Engineering Answer` mode for calculations, assumptions, formulas, and limits.
- [ ] Add `HSE / Emissions Answer` mode for factors, tiers, source records, and regulatory notes.
- [ ] Add `Permit / PTW Answer` mode for required controls, isolations, and approval notes.
- [ ] Add `Executive Summary` mode for short business-facing summaries with risk flags.
- [ ] Add `Field Mode` for concise offline-friendly guidance.
- [ ] Persist the selected answer mode per user.

### Phase 5 - Role-Based Workspaces

- [ ] Create workspace profiles for Engineer, HSE/Emissions, Admin, Field, and Executive users.
- [ ] Tune default modules, prompts, and visible navigation per role.
- [ ] Keep permissions enforced by backend RBAC, not only frontend hiding.
- [ ] Add role-specific dashboards.
- [ ] Add role-specific sample questions and empty states.
- [ ] Add tests for role visibility and protected routes.

### Phase 6 - Trust and Audit Hardening

- [ ] Add an answer audit trail that links final answer, evidence pack, tool outputs, and source IDs.
- [ ] Store hashes of sensitive raw prompts/answers instead of raw private content where possible.
- [ ] Add "copy answer with sources" action.
- [ ] Add "download verification packet" action.
- [ ] Add admin retention controls for source packs and audit events.
- [ ] Add redaction tests for source packs and exported reports.

### Phase 7 - Product Polish

- [ ] Replace debug-sounding labels with user-safe language everywhere.
- [ ] Review every visible string for internal names, raw IDs, secrets, tokens, or provider names.
- [ ] Add loading states like `Checking sources`, `Calculating`, and `Preparing verification`.
- [ ] Add empty states that guide users to upload SOPs or provide missing inputs.
- [ ] Add visual source badges: SOP, Calculation, Web, User Input, Admin Record.
- [ ] Add accessibility tests for evidence panels and source lists.

## Definition of Done

- [ ] Important answers include source-backed evidence.
- [ ] Safety-critical answers clearly require human verification.
- [ ] No internal tool names, raw JSON, prompts, tokens, secrets, or private search queries are shown to users.
- [ ] Backend audit logs retain enough detail for investigation without exposing secrets.
- [ ] Frontend tests prove sensitive/internal data stays hidden.
- [ ] Full backend and frontend test suites pass.
