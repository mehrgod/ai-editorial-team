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