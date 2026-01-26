# Claude Code Project Template

A universal template for projects using [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Anthropic's CLI for AI-assisted software development.

## What's Included

```
claude-template/
├── CLAUDE.md              # Project instructions template for Claude Code
├── README.md              # This file
└── .claude/
    └── commands/          # /plan command suite for structured development
        └── README.md      # Comprehensive command documentation
```

## Quick Start

### 1. Copy Template to Your Project

```bash
# Copy CLAUDE.md and .claude/ directory to your project
cp CLAUDE.md /path/to/your-project/
cp -r .claude /path/to/your-project/
```

### 2. Customize CLAUDE.md

Open `CLAUDE.md` and update these sections:

#### Front-Matter Configuration

```yaml
---
version: "1.0.0"
project_type: "web-app"           # web-app | cli | backend | library | monorepo
testing_philosophy: "tad"          # tdd | tad | bdd | lightweight | manual | hybrid
bootstrap_source: null
last_updated: "2025-01-26"
---
```

#### Quick Start Section (Lines 1-50)

Replace placeholders with your project specifics:

| Placeholder | Replace With | Example |
|-------------|--------------|---------|
| `[PROJECT_NAME]` | Your project name | My Web App |
| `[INSTALL_CMD]` | Install command | `npm install` |
| `[DEV_CMD]` | Development command | `npm run dev` |
| `[TEST_CMD]` | Test command | `npm test` |
| `[BUILD_CMD]` | Build command | `npm run build` |
| `[LINT_CMD]` | Lint command | `npm run lint` |

#### User Content Sections

Look for `<!-- USER CONTENT START: name -->` markers. These sections are for your project-specific content and are preserved during template updates:

- **overview**: Project description and purpose
- **status**: Current development focus and recent changes
- **code_style_additions**: Project-specific style rules
- **testing_specifics**: Testing guidance for your stack
- **architecture**: System design, directory structure, tech stack
- **workflows**: CI/CD and deployment conventions
- **learnings**: Discoveries and insights from development
- **tech_debt**: Known issues and remediation plans
- **extensions**: Project-type-specific additions

### 3. Initialize Project Constitution (Optional)

For full /plan workflow support, run the constitution setup:

```bash
/plan-0-constitution
```

This creates `docs/project-rules/` with:
- `constitution.md` - Core project principles
- `rules.md` - Enforceable standards
- `idioms.md` - Patterns and conventions
- `architecture.md` - System boundaries

## Using the /plan Commands

The template includes a comprehensive command suite for structured, phase-by-phase development.

**Full documentation**: See [.claude/commands/README.md](.claude/commands/README.md)

### Core Workflow

```bash
# 1. Create feature specification
/plan-1b-specify "Add user authentication with OAuth2"

# 2. Clarify requirements (testing strategy, ambiguities)
/plan-2-clarify

# 3. Generate implementation plan
/plan-3-architect

# 4. Generate tasks for a phase
/plan-5-phase-tasks-and-brief --phase "Phase 1: Setup"

# 5. Implement the phase
/plan-6-implement-phase --phase "Phase 1: Setup"

# 6. Review implementation
/plan-7-code-review --phase "Phase 1: Setup"
```

### Available Commands

| Command | Purpose |
|---------|---------|
| `/plan-0-constitution` | Initialize project governance (once per project) |
| `/plan-1a-explore` | Research existing codebase |
| `/plan-1b-specify` | Create feature specification |
| `/plan-2-clarify` | Resolve ambiguities |
| `/plan-3-architect` | Generate implementation plan |
| `/plan-4-complete-the-plan` | Validate plan readiness |
| `/plan-5-phase-tasks-and-brief` | Generate phase tasks |
| `/plan-6-implement-phase` | Execute implementation |
| `/plan-7-code-review` | Review implementation |
| `/didyouknow` | Build shared understanding |

## CLAUDE.md Structure

The template uses **progressive disclosure** - most important information first:

| Section | Lines | Purpose |
|---------|-------|---------|
| Quick Start | 1-50 | Essential commands and current status |
| Core Guidance | 51-150 | Universal code style and practices |
| Documentation | 151-270 | Exit criteria, README sync, ADRs |
| Project-Specific | 271-350 | Architecture (customize this) |
| Workflows | 351-400 | UI testing, CI/CD (conditional) |
| Learning | 401-450 | Discoveries and tech debt |
| Appendices | 451+ | Reference material |

### Conditional Sections

Some sections activate based on `project_type`:

- **Manual UI Testing**: Shows for `web-app` and `mobile` projects
- **Extension Points**: Different guidance per project type

### Machine-Parseable Markers

The template uses markers for tooling integration:

```markdown
<!-- SECTION: NAME -->                    # Section boundaries
<!-- REQUIRED / OPTIONAL -->              # Section requirements
<!-- CONDITIONAL: project_type = X -->    # Conditional display
<!-- USER CONTENT START: name -->         # Protected user content
<!-- USER CONTENT END: name -->           # End of protected content
```

## Customization Guide

### For Web Applications

1. Set `project_type: "web-app"` in front-matter
2. Manual UI Testing section will be visible
3. Add component library details in architecture
4. Document state management patterns

### For CLI Tools

1. Set `project_type: "cli"` in front-matter
2. Document command structure in architecture
3. Add flag conventions and output formatting rules

### For Backend Services

1. Set `project_type: "backend"` in front-matter
2. Document API versioning strategy
3. Add database migration approach
4. Define logging and monitoring conventions

### For Libraries

1. Set `project_type: "library"` in front-matter
2. Document public API design principles
3. Add versioning and changelog conventions
4. Define example maintenance strategy

## Testing Philosophy Options

Choose your approach in front-matter and `/plan-2-clarify`:

| Philosophy | Best For |
|------------|----------|
| `tdd` | Features with clear specs, high reliability needs |
| `tad` | Exploratory development, discovering requirements |
| `bdd` | User-facing features, behavior-focused testing |
| `lightweight` | Simple utilities, well-understood domains |
| `manual` | UI-heavy features, rapid prototyping |
| `hybrid` | Mixed approaches per component complexity |

## Learning Capture

The template includes a structured learning section. After completing work, document discoveries:

```markdown
### [YYYY-MM-DD] - Topic Title

**Context:** What were you working on?

**Discovery:** What did you learn?

**Impact:** How does this affect future work?

**References:** Related files, PRs, ADRs

**Tags:** #gotcha | #pattern | #antipattern | #performance
```

The `/plan-6-implement-phase` command prompts for reflection after each phase.

## Requirements

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Git repository (recommended for full workflow support)

## License

This template is provided as-is for use with Claude Code projects.
