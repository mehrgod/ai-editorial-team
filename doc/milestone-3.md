# Milestone 3 – LLM-Powered Chief Editor

## Goal

Replace the deterministic Chief Editor with an LLM-powered Chief Editor while preserving the existing application architecture.

The Chief Editor should evaluate the candidate stories proposed by the research agents and select the single best story for publication.

---

## Objectives

- Introduce an LLM-based Chief Editor.
- Keep the Research Agents unchanged.
- Preserve the existing LangGraph workflow.
- Continue returning exactly one selected story.
- Keep the domain independent of any LLM provider.

---

## Scope

### In Scope

- LLM-powered story evaluation.
- Prompt engineering for editorial decision making.
- Infrastructure adapter for the LLM.
- Configuration through environment variables.
- Structured output from the LLM.

### Out of Scope

- Image generation.
- Social media publishing.
- MCP.
- Memory.
- Multi-agent debate.
- Human approval.

---

## Architecture

The application layer should continue calling the `ChiefEditor` interface.

The implementation will change from:

DeterministicChiefEditor

to

LLMChiefEditor

The domain and workflow should not require modification.

---

## Success Criteria

The application should:

1. Collect one candidate story from each research agent.
2. Send those stories to the LLM.
3. Receive one selected story.
4. Return that story to the workflow.
5. Produce the same CLI output format as before.

---

## Constraints

- Maintain Clean Architecture.
- Keep provider-specific code in the infrastructure layer.
- Do not expose provider APIs to the domain.
- Support replacing the LLM provider in the future.

---

## Deliverables

- LLM Chief Editor implementation.
- Prompt template.
- Configuration through environment variables.
- Updated documentation.