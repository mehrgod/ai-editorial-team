# System Architecture

## 1. Overview

AI Editorial Team is an agentic AI application designed around a simple principle:

> Agents make decisions. Tools perform actions.

The system is intentionally divided into two types of components:

- **Agents**, which use LLM reasoning to make decisions.
- **MCP Tools**, which perform deterministic tasks such as retrieving news, generating images, publishing content, and storing data.

The application is orchestrated by LangGraph, exposed through a FastAPI application, and designed to run locally during development before being deployed to AWS.

---

## High-Level Workflow

Research Agents
        │
        ▼
Chief Editor Agent
        │
        ▼
Content Package
        │
        ▼
MCP Tools
        │
        ├── Image Generation
        ├── Publish to Instagram
        ├── Publish to X
        └── Storage & Logging

---

## 2. Design Principles

The following principles guide every architectural decision in this project.

### 2.1 Agents Reason

Agents are responsible for making decisions that require reasoning.

Examples include:

- Selecting the most important story
- Comparing candidate stories
- Deciding what content should be published

Agents should not directly interact with external services.

---

### 2.2 Tools Perform Actions

External operations are implemented as MCP tools.

Examples include:

- Searching news
- Generating images
- Publishing to social media
- Saving data
- Writing logs

Tools should not make business decisions.

---

### 2.3 LangGraph Orchestrates

LangGraph is responsible for coordinating the workflow.

It manages:

- execution order
- shared state
- retries
- conditional branching
- error handling

Business logic should remain inside agents, not inside the graph.

---

### 2.4 Components Have a Single Responsibility

Each component should have one clear responsibility.

For example:

- Research agents find stories.
- The Chief Editor selects the winner.
- Image generation creates images.
- Publishers publish.
- Storage saves data.

Avoid components that perform multiple unrelated tasks.

---

### 2.5 Everything Should Be Replaceable

The system should be designed so that individual components can be replaced without affecting the rest of the application.

Examples include:

- OpenAI → Amazon Bedrock
- RSS → News API
- Instagram → LinkedIn
- Local storage → Amazon S3