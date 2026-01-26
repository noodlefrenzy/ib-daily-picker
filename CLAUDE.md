---
# CLAUDE.md Template Configuration
version: "1.0.0"
project_type: "[PROJECT_TYPE]"  # web-app | cli | backend | library | monorepo
testing_philosophy: "[TESTING_PHILOSOPHY]"  # tdd | tad | bdd | lightweight | manual | hybrid
bootstrap_source: null  # Set by /plan-0-constitution when bootstrapping
last_updated: "[YYYY-MM-DD]"
---

<!-- SECTION: QUICK_START -->
<!-- REQUIRED -->
# [PROJECT_NAME]

## Project Overview

<!-- USER CONTENT START: overview -->
[Brief description of what this project does, its main purpose, and key value proposition.]
<!-- USER CONTENT END: overview -->

## Development Commands

```bash
# Essential commands - customize for your project
[INSTALL_CMD]     # e.g., npm install, pnpm install, pip install -e .
[DEV_CMD]         # e.g., npm run dev, pnpm dev, python main.py
[TEST_CMD]        # e.g., npm test, pytest, go test ./...
[BUILD_CMD]       # e.g., npm run build, cargo build, go build
[LINT_CMD]        # e.g., npm run lint, ruff check, golangci-lint run
```

## Current Status

<!-- USER CONTENT START: status -->
**Focus:** [Current development focus or milestone]

**Recent Changes:**
- [Most recent significant change]
- [Previous change]

**Known Issues:**
- [Any blocking or critical issues]
<!-- USER CONTENT END: status -->

---

<!-- SECTION: CORE_GUIDANCE -->
<!-- REQUIRED -->
## Core Guidance

### Code Style Principles

**General:**
- Functional, immutable patterns preferred
- async/await exclusively (no `.then()` chains)
- No `any` types or unchecked casts (TypeScript)
- Prefer `import type` for type-only imports
- Underscore prefix (`_var`) for intentionally unused variables

**Error Handling:**
- Validate at boundaries (user input, external APIs)
- Fail fast with clear error messages
- Don't swallow errors silently

**Dependencies:**
- Explicit over implicit
- No circular dependencies
- Clear dependency direction (apps -> packages -> external)

<!-- USER CONTENT START: code_style_additions -->
<!-- Add project-specific style rules here -->
<!-- USER CONTENT END: code_style_additions -->

### File Operations Checklist

**When renaming, moving, or deleting files:**

1. Search for references to the old path:
   ```bash
   grep -r "old-filename" --include="*.md" --include="*.ts" --include="*.tsx"
   ```
2. Check for README.md or index files in the same/parent directory
3. Check any ADR index if touching ADRs
4. Update any documentation, imports, or links that reference changed files
5. Verify links still work after changes

### Testing Philosophy

<!-- CONDITIONAL: testing_philosophy != manual -->
**Test Documentation Block Format:**

For TAD/TDD workflows, every test file should include a Test Doc block:

```
/**
 * TEST DOC: [Feature/Component Name]
 *
 * WHAT: [What behavior is being tested]
 * WHY: [Why this test exists - what bug/requirement it covers]
 * HOW: [Brief description of test approach]
 *
 * CASES:
 * - [Case 1]: [Expected behavior]
 * - [Case 2]: [Expected behavior]
 *
 * EDGE CASES:
 * - [Edge case]: [How it's handled]
 */
```
<!-- END CONDITIONAL -->

**Testing Approach:**
| Philosophy | When to Use | Key Principle |
|------------|-------------|---------------|
| TDD | New features with clear specs | Write test first, then implementation |
| TAD | Exploratory development | Tests document discoveries |
| BDD | User-facing features | Describe behavior from user perspective |
| Lightweight | Simple utilities | Focus on edge cases and contracts |
| Manual | UI-heavy features | Supplement with manual verification |
| Hybrid | Complex projects | Mix approaches per component |

<!-- USER CONTENT START: testing_specifics -->
<!-- Add project-specific testing guidance here -->
<!-- USER CONTENT END: testing_specifics -->

### Verification Philosophy

**Multi-layer verification catches different bugs:**

| Layer | What It Catches | What It Misses |
|-------|-----------------|----------------|
| Type checking | Import/export mismatches, type errors | Runtime behavior, UI interactions |
| Linting | Style issues, common mistakes | Logic errors, integration issues |
| Unit tests | Function-level logic | Integration, UI flow |
| Integration tests | Component interactions | UI polish, UX issues |
| Manual testing | UI interactions, user flows | Edge cases without explicit testing |

**Do not skip layers.** Each catches issues the others miss.

**Pre-Commit Verification:**
```bash
# Run all verification layers before committing
[TYPE_CHECK_CMD]  # e.g., tsc --noEmit, mypy, go vet
[LINT_CMD]        # e.g., eslint, ruff, golangci-lint
[TEST_CMD]        # e.g., jest, pytest, go test
```

---

<!-- SECTION: DOCUMENTATION_REQUIREMENTS -->
<!-- REQUIRED -->
## Documentation Requirements

### Exit Criteria (REQUIRED)

**Before considering any task complete, verify documentation is in sync:**

1. **Architecture Decision Records (ADRs):**
   - [ ] Does this change diverge from any existing ADR? -> Update or supersede it
   - [ ] Does this introduce a significant architectural decision? -> Create a new ADR
   - [ ] Are any ADRs now outdated due to this change? -> Update status

2. **README Files:**
   - [ ] Does the relevant README reflect current behavior?
   - [ ] Are setup instructions still accurate?
   - [ ] Are any documented features now changed or removed?

3. **Plan/Spec Status:**
   - [ ] If implementing a plan, is the status updated (DRAFT -> ACCEPTED -> SUPERSEDED)?
   - [ ] Are related plans cross-referenced if they overlap?

4. **Project Instructions:**
   - [ ] Does this change affect conventions documented in CLAUDE.md?
   - [ ] Is the project status section still accurate?
   - [ ] Are any architecture descriptions now outdated?

**Why this matters:** Documentation drift causes confusion, wasted investigation time, and bugs when developers follow outdated guidance.

### README Synchronization

**Triggers - Update README when:**
- Adding/removing commands or scripts
- Changing setup or installation steps
- Adding/removing features
- Changing environment requirements
- Modifying API endpoints or interfaces

**README Checklist:**
```
[ ] Project description accurate
[ ] Installation steps work on fresh clone
[ ] All documented commands are valid
[ ] Environment variables documented
[ ] Dependencies listed with versions
[ ] Examples reflect current API
```

### ADR Management

**ADR Triggers (create a new ADR when):**
- Choosing between multiple viable approaches (document why this one)
- Deviating from established patterns (document the exception)
- Making technology choices (document alternatives considered)
- Changing how components/packages interact (document the architecture)

**ADR Format:**
```markdown
# ADR-[NUMBER]: [TITLE]

## Status
[DRAFT | ACCEPTED | SUPERSEDED by ADR-XXX | DEPRECATED]

## Context
[Why is this decision needed? What problem are we solving?]

## Decision
[What did we decide?]

## Consequences
### Positive
- [Benefit 1]

### Negative
- [Tradeoff 1]

### Neutral
- [Observation 1]

## References
- [Related ADRs, external docs, discussions]
```

**ADR Maintenance:**
- Review ADRs quarterly or when major changes occur
- Mark superseded ADRs clearly with pointer to replacement
- Keep ADR index updated (docs/adr/README.md or similar)

### Micro-Context Standards

**File Headers (for complex files):**
```
/**
 * [FILENAME]
 *
 * PURPOSE: [What this file does]
 * OWNER: [Team or person responsible]
 * DEPENDENCIES: [Key external dependencies]
 *
 * ARCHITECTURE NOTES:
 * [Any non-obvious design decisions or patterns]
 */
```

**Front-Matter (for documentation files):**
```yaml
---
title: [Document Title]
status: [draft | review | final]
last_updated: [YYYY-MM-DD]
related:
  - [path/to/related/doc.md]
---
```

**Contextual Comments:**
- Use `// WHY:` for non-obvious decisions
- Use `// TODO:` with ticket/issue reference
- Use `// HACK:` with explanation and remediation plan
- Use `// PERF:` for performance-critical sections

---

<!-- SECTION: PROJECT_SPECIFIC -->
<!-- OPTIONAL -->
## Project Architecture

<!-- USER CONTENT START: architecture -->
### Overview

[Describe the high-level architecture - layers, components, data flow]

### Directory Structure

```
[PROJECT_ROOT]/
  src/
    [Describe key directories]
  tests/
    [Test organization]
  docs/
    [Documentation structure]
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| [LAYER] | [TECH] | [WHY] |

### Domain Concepts

| Concept | Definition | Where Used |
|---------|------------|------------|
| [TERM] | [MEANING] | [LOCATIONS] |

### Integration Points

| External System | Purpose | Interface |
|-----------------|---------|-----------|
| [SYSTEM] | [WHY] | [HOW - API, SDK, etc.] |
<!-- USER CONTENT END: architecture -->

---

<!-- SECTION: WORKFLOWS -->
<!-- CONDITIONAL: project_type = web-app OR project_type = mobile -->
## Manual UI Testing (CRITICAL)

**TypeScript/compilation passing is NOT sufficient.** Before committing any UI changes:

1. **Start the app(s)** and manually test every feature you touched
2. **Click every button** - verify handlers are actually connected
3. **Test complete user flows** - Create -> Read -> Update -> Delete
4. **Test affected platforms** if changes touch shared code

**UI Testing Checklist:**
```
For each new/modified feature:
[ ] Started the app(s)
[ ] Clicked through the UI - buttons, forms, modals
[ ] Verified data persists - created item appears in list
[ ] Verified actions work - edit updates, delete removes
[ ] Checked console for errors - no red errors in DevTools
[ ] Tested on affected platforms
```

**Common issues this catches:**
- Event handlers not connected (button does nothing)
- Navigation missing required parameters
- Drag-and-drop listeners blocking click handlers
- Missing CSS/styles for new components
- State not updating after mutations

**Root cause of missed bugs:** Assuming "code compiles" means "feature works."
<!-- END CONDITIONAL -->

<!-- USER CONTENT START: workflows -->
### CI/CD Conventions

[Describe your CI/CD pipeline, branch strategies, deployment process]

### Deployment Considerations

[Environment-specific configs, feature flags, rollback procedures]
<!-- USER CONTENT END: workflows -->

---

<!-- SECTION: LEARNING_REFLECTION -->
<!-- REQUIRED -->
## Learning & Reflection

### Recent Learnings

<!--
After completing each phase or significant task, capture learnings here.
This section is prompted by /plan-6-implement-phase completion.

Entry Format:
## [DATE] - [TOPIC TITLE]

**Context:** [What were you working on?]

**Discovery:** [What did you learn? What surprised you?]

**Impact:** [How does this affect future work?]

**References:** [Related files, PRs, ADRs]

**Tags:** #gotcha | #pattern | #antipattern | #performance | #security | #ux
-->

<!-- USER CONTENT START: learnings -->
### [YYYY-MM-DD] - Example: API Rate Limiting Gotcha

**Context:** Implementing batch data sync feature

**Discovery:** The external API has undocumented rate limits of 100 req/min. Discovered when production sync started failing at scale.

**Impact:** Need to implement exponential backoff and request queuing for all external API calls.

**References:**
- `src/services/api-client.ts:45`
- PR #123
- ADR-007

**Tags:** #gotcha #api #performance
<!-- USER CONTENT END: learnings -->

### Known Issues & Technical Debt

<!-- USER CONTENT START: tech_debt -->
| Issue | Severity | Context | Remediation |
|-------|----------|---------|-------------|
| [ISSUE] | High/Med/Low | [Why it exists] | [Plan to fix] |
<!-- USER CONTENT END: tech_debt -->

### Post-Implementation Notes

<!-- USER CONTENT START: post_impl -->
<!-- Add notes after major implementations about what worked, what didn't -->
<!-- USER CONTENT END: post_impl -->

---

<!-- SECTION: APPENDICES -->
## Appendices

### Appendix A: Commit Format Standards

```
<type>(<scope>): <description>

[optional body]

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes nor adds |
| `docs` | Documentation only |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |

**Scope:** Use the most specific relevant area (component, package, feature)

**Examples:**
```
feat(auth): add OAuth2 login flow
fix(api): handle null response from user endpoint
refactor(utils): extract date formatting to shared module
docs(readme): update installation instructions
```

### Appendix B: Complexity Scoring Reference

Use CS 1-5 instead of time estimates:

| Score | Scope | Risk | Examples |
|-------|-------|------|----------|
| **CS-1** | Single file, isolated change | Minimal | Fix typo, update constant, add log |
| **CS-2** | Few files, minimal integration | Low | Add simple endpoint, new utility function |
| **CS-3** | Multiple components, moderate complexity | Some | New feature with tests, refactor module |
| **CS-4** | Cross-cutting concerns, significant integration | Notable | Authentication system, major refactor |
| **CS-5** | System-wide impact, high uncertainty | Significant | Architecture change, new core abstraction |

**Usage in Plans:**
```markdown
## Tasks
- [ ] Add user endpoint (CS-2)
- [ ] Implement caching layer (CS-4)
- [ ] Update config constant (CS-1)
```

### Appendix C: Extension Points by Project Type

<!-- CONDITIONAL: project_type = web-app -->
**Web App Extensions:**
- Component library documentation
- State management patterns
- API client conventions
- Styling/theming approach
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = cli -->
**CLI Extensions:**
- Command structure and naming
- Flag conventions
- Output formatting (human vs machine)
- Configuration file handling
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = backend -->
**Backend Extensions:**
- API versioning strategy
- Database migration approach
- Authentication/authorization patterns
- Logging and monitoring conventions
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = library -->
**Library Extensions:**
- Public API design principles
- Versioning and changelog conventions
- Documentation generation
- Example maintenance
<!-- END CONDITIONAL -->

<!-- USER CONTENT START: extensions -->
<!-- Add project-specific extensions here -->
<!-- USER CONTENT END: extensions -->

---

<!-- SECTION: META -->
## Template Maintenance

This template follows progressive disclosure:
- **Lines 1-50:** Quick Start - essential info for immediate productivity
- **Lines 51-150:** Core Guidance - universal principles for all projects
- **Lines 151-250:** Documentation Requirements - keeping docs in sync
- **Lines 251-350:** Project-Specific - customizable architecture details
- **Lines 351-450:** Workflows - conditional by project type
- **Lines 451+:** Learning & Appendices - reference material

**Bootstrap:** Run `/plan-0-constitution` to customize this template for your project type.

**User Content:** Sections between `<!-- USER CONTENT START -->` and `<!-- USER CONTENT END -->` are preserved during template updates.

**Conditional Sections:** Sections marked with `<!-- CONDITIONAL: ... -->` are shown/hidden based on project configuration.
