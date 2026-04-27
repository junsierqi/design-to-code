# design-to-code

A Codex skill for implementing frontend UI from visual design sources such as screenshots, mockups, wireframes, HTML prototypes, and Figma references.

It guides agents through design analysis, dependency auditing, mock generation, implementation, Playwright-based verification, screenshots, traceability, and acceptance-ready reporting. The skill is useful when the visual reference is the source of truth and the result should be working UI rather than a static review.

## Use When

- A user asks to implement a UI from a screenshot, mockup, wireframe, HTML prototype, or Figma link.
- The design references backend APIs or data that may not exist yet.
- The work needs responsive behavior, interaction testing, and screenshots.
- The final output should include an implementation report and visual acceptance evidence.

## What's Included

- `skills/design-to-code/SKILL.md` - agent workflow instructions
- `skills/design-to-code/agents/openai.yaml` - Codex/OpenAI UI metadata

## Requirements

- A frontend project to modify
- Node/package tooling appropriate to the target project
- Playwright when runtime UI verification is required

## Install

Copy or symlink `skills/design-to-code/` into your Codex skills directory, commonly:

```bash
$HOME/.codex/skills/design-to-code
```
