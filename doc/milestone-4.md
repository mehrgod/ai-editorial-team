# Milestone 4 – Content Generation Team

## Goal

Expand the editorial workflow by introducing specialized content generation agents.

After the Chief Editor selects the best story, multiple AI agents should work in parallel to create platform-specific content.

---

## Objectives

- Generate an Instagram caption.
- Generate an X (Twitter) post.
- Generate an image prompt.
- Execute content generation agents in parallel using LangGraph.
- Return a complete editorial package.

---

## Workflow

Research Agents
        ↓
Chief Editor
        ↓
Selected Story
        ↓
 ┌───────────────┬───────────────┬──────────────────┐
 ▼               ▼               ▼
Instagram     X Writer     Image Prompt Writer
Agent         Agent         Agent
 └───────────────┴───────────────┴──────────────────┘
                     ↓
             Editorial Package

---

## Deliverables

The workflow should return a single Editorial Package containing:

- Selected Story
- Instagram Caption
- X Post
- Image Prompt

---

## Architecture

Each content generator should be its own agent.

Examples:

- InstagramContentAgent
- XContentAgent
- ImagePromptAgent

Each agent should have one responsibility.

The application layer orchestrates them.

The infrastructure layer contains all OpenAI-specific code.

---

## Parallel Execution

The three content agents should execute concurrently using LangGraph.

The workflow should wait until all three complete before continuing.

---

## Scope

### In Scope

- Parallel LangGraph execution.
- Platform-specific prompts.
- Structured outputs.
- Editorial package object.

### Out of Scope

- Image generation.
- Publishing to social media.
- MCP.
- Human approval.

---

## Success Criteria

Given one selected story, the system produces:

- One Instagram caption.
- One X post.
- One image prompt.

The CLI prints the complete editorial package.

---

## Constraints

- Maintain Clean Architecture.
- Keep prompt engineering inside the infrastructure layer.
- Reuse the existing OpenAI client patterns where appropriate.