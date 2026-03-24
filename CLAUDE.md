# FinHive

## Key Input
`/input/REQUIREMENTS.md`: The high-level human defined requirements for the Product.

### Input Structure:
```
[Title]
[Overview]
[Requirements]
[Prototype - Phase estimates]
[Usage Scope]
```
`Title` = `[Title]` from input file

## Core Project Information
- **Goal**: Leverage Claude Skills to simulate Multi-Agent Coordination over parallel orchestration workflows to generate deterministic outputs.
- **Idea**: Compare run outputs as skills enhance.
- **Git Branch**: `development`

## Core Principles
1. **Security First**: Never hardcode API keys. Use `.env` files.
2. **Type Safety**: Always use TypeScript definitions. Avoid `any`.
3. **Small units of work**: Parse requirements into small units of work which can be assigned to specific skill experts. Focus on action items rather comprehension.
4. **Test before Commits**: Make atomic changes with testing and clear commit messages.
5. **Iterative**: Explore -> Plan -> Code. Do not implement complex features immediately.
6. **Modular**: Code design should be modular and unit-tested.

## Available agents
- `./claude/agents/architect.md`
- `./claude/agents/build-error-resolver.md`
- `./claude/agents/code-reviewer.md`
- `./claude/agents/doc-updater.md`
- `./claude/agents/loop-operator.md` = The starter agent for orchestrating child agents and skills.
- `./claude/agents/planner.md`
- `./claude/agents/python-reviewer.md`
- `./claude/agents/refactor-cleaner.md`
- `./claude/agents/security-reviewer.md`
- `./claude/agents/tdd-guide.md`

## Skills
- `./claude/skills/backend-dev-agent/SKILL.md`: Backend Developer skills
- `./claude/skills/backend-qa-agent/SKILL.md`: Backend Quality Assurance skills
- `./claude/skills/bsa-agent/SKILL.md`: Business System Analyst skills
- `./claude/skills/dev-lead-agent/SKILL.md`: Developer Lead skills
- `./claude/skills/dm-agent/SKILL.md`: Data Modeller skills
- `./claude/skills/frontend-dev-agent/SKILL.md`: Frontend Developer skills
- `./claude/skills/frontend-qa-agent/SKILL.md`: Frontend Quality Assurance skills
- `./claude/skills/pm-agent/SKILL.md`: Product Manager skills
- `./claude/skills/po-agent/SKILL.md`: Product Owner skills
- `./claude/skills/sa-agent/SKILL.md`: Solution Architect skills
- `./claude/skills/sre-agent/SKILL.md`: Site Reliability Engineer skills
- `./claude/skills/qa-lead-agent/SKILL.md`: Quality Assurance Lead skills
- `./claude/skills/uat-agent/SKILL.md`: User Acceptance Tester skills
- `./claude/skills/agentic-engineering/SKILL.md`: Agentic Engineering skills
- `./claude/skills/ai-first-engineering/SKILL.md`: AI first engineering skills
- `./claude/skills/backend-patterns/SKILL.md`: Backend patterns skills
- `./claude/skills/coding-standards/SKILL.md`: Coding Standards skills
- `./claude/skills/deployment-patterns/SKILL.md`: Deployment Pattern skills
- `./claude/skills/frontend-patterns/SKILL.md`: Frontend Patterns skills
- `./claude/skills/python-patterns/SKILL.md`: Python Patterns
- `./claude/skills/python-testing/SKILL.md`: Python Testing skills
- `./claude/skills/tdd-workflow/SKILL.md`: Test Driven Development workflow


## Architecture

The project is organized into several core components:

- **agents/** - Specialized subagents for delegation (planner, code-reviewer, tdd-guide, etc.)
- **skills/** - Workflow definitions and domain knowledge (coding standards, patterns, testing)
- **commands/** - Slash commands invoked by users (/tdd, /plan, /e2e, etc.)
- **hooks/** - Trigger-based automations (session persistence, pre/post-tool hooks)
- **rules/** - Always-follow guidelines (security, coding style, testing requirements)
- **scripts/** - Cross-platform Node.js utilities for hooks and setup
- **tests/** - Test suite for scripts and utilities

## Key Commands

- `/tdd` - Test-driven development workflow
- `/plan` - Implementation planning
- `/code-review` - Quality review
- `/build-fix` - Fix build errors
- `/learn` - Extract patterns from sessions
- `/skill-create` - Generate skills from git history

## Development Notes

- Package manager detection: npm, pnpm, yarn, bun (configurable via `CLAUDE_PACKAGE_MANAGER` env var or project config)
- Cross-platform: Windows, macOS, Linux support via Node.js scripts
- Agent format: Markdown with YAML frontmatter (name, description, tools, model)
- Skill format: Markdown with clear sections for when to use, how it works, examples
- Hook format: JSON with matcher conditions and command/notification hooks

## Contributing

Follow the formats in CONTRIBUTING.md:
- Agents: Markdown with frontmatter (name, description, tools, model)
- Skills: Clear sections (When to Use, How It Works, Examples)
- Commands: Markdown with description frontmatter
- Hooks: JSON with matcher and hooks array

File naming: lowercase with hyphens (e.g., `python-reviewer.md`, `tdd-workflow.md`)


## File Structure
- `/input/*`: Inputs for reaching a deterministic output.
- `/output/*`: Outputs stored here.
- `/output/<Title>/<run_order>/*`: Audit report outputs stored for each run on the input for `[Title]` as per `/input/REQUIREMENTS.md`.
- `/output/<Title>/<run_order>/skill_outputs/*`: The outputs generated by skill experts.
- `./claude/tools/*`: Reference snippets and documentations.
- `/src/<Title>/*`: Core codebase for the requirement (should populate only when in Implement Stage).
- `/src/main.py`: The main agent loop basic.

## Development Commands
- **Dev**: `python`

## Coding Conventions:
- Use PEP8 for python styling

## Constraints
- Do not modify any code in `./claude/skills/tools/*`
- Do not make unnecessary assumptions, whenever in doubt always mark the decision as [REVIEW REQUIRED] 
- Do not leverage previous run's output into the context.
