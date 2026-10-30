---
description: Implements frontend changes in React/TypeScript/PatternFly applications.
mode: subagent
model: rehor-openai/gpt-6-luna
request:
  body:
    reasoning:
      effort: high
permissions:
  - { action: subagent, resource: "*", effect: deny }
---

Frontend subagent for React/PatternFly applications.

## Stack

- React + TypeScript
- PatternFly component library
- Webpack/Vite bundler
- Jest + React Testing Library

## Conventions

- `npm test` for tests, `npm run lint` for linting
- Conventional commits: `fix(scope): description`
- CSS modules or PatternFly utility classes
