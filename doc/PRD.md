# Product Requirements Document (PRD)

## 1. Project Overview

### Project Name

AI Editorial Team

### Vision

Build an autonomous AI editorial system that researches multiple domains, selects the most valuable story of the day, generates platform-specific content and supporting images, and publishes automatically to social media.

The project is intended to demonstrate production-quality AI engineering using modern agentic AI concepts rather than simply automating social media posting.

---

## 2. Goals

The primary goals of this project are:

- Learn and demonstrate LangGraph
- Learn and demonstrate the Model Context Protocol (MCP)
- Build a production-style agentic AI system
- Demonstrate tool orchestration and agent collaboration
- Produce content automatically for social media
- Create a portfolio-quality open-source project

---

## 3. Non-Goals

The initial version of this project will NOT include:

- Human approval workflows
- Analytics dashboards
- User accounts
- Multi-user support
- Revenue generation
- A web frontend

---

## 4. Minimum Viable Product (MVP)

The MVP represents the smallest version of the system that demonstrates the complete agentic workflow.

Every day, the system will:

1. Research the latest news from three domains:
   - Finance
   - Artificial Intelligence
   - Sports

2. Each research agent will identify its best candidate story.

3. A Chief Editor agent will evaluate all candidates and select the single story that provides the most value for the audience.

4. The Chief Editor will generate:
   - Instagram caption
   - X (Twitter) post
   - Hashtags
   - Image generation prompt

5. An image generation tool will create a branded image.

6. Publishing tools will automatically publish the content to:
   - Instagram
   - X

7. The system will store execution logs and generated content for future reference.

---

## 5. System Components

The initial version of the system consists of the following components:

### Research Agents

There will be three independent research agents.

- Finance Research Agent
- AI Research Agent
- Sports Research Agent

Each research agent is responsible for:

- Finding recent news within its domain
- Selecting the single best candidate story
- Providing a short explanation of why the story is important
- Returning references to the original sources

Research agents do not generate social media content and do not publish content.

---

### Chief Editor Agent

The Chief Editor receives the candidate stories from all research agents.

Its responsibilities include:

- Comparing all candidate stories
- Selecting the best story of the day
- Explaining why it selected that story
- Generating platform-specific content
- Preparing the image generation prompt

The Chief Editor is the primary reasoning component of the system.

---

### MCP Tools

The system will use MCP tools for deterministic operations, including:

- News retrieval
- Image generation
- Social media publishing
- Storage
- Logging

These components are tools rather than agents because they perform actions instead of reasoning.

---

## 6. Success Criteria

Version 1.0 of the project will be considered successful when the system can complete the following workflow without human intervention:

1. Execute on a scheduled basis.
2. Retrieve current news from Finance, AI, and Sports.
3. Select one candidate story from each domain.
4. Choose the single best story using the Chief Editor agent.
5. Generate:
   - Instagram caption
   - X post
   - Hashtags
   - Image prompt
6. Generate a branded image.
7. Publish the content to Instagram and X.
8. Store execution logs and generated content.

---

## 7. Future Enhancements

The following features are intentionally excluded from Version 1.0 but are expected in future releases:

- Human approval (Human-in-the-Loop)
- LinkedIn publishing
- Newsletter generation
- Blog generation
- Additional research domains
- Analytics and engagement tracking
- Semantic memory and long-term context
- AWS deployment
- Observability and tracing
- A web-based dashboard

---

# 8. Development Phases

The project will be developed incrementally. Each phase should result in a working application.

## Phase 1 - MVP

Goal:

Demonstrate the complete agentic workflow locally.

The application should:

- Run from the command line
- Research Finance, AI, and Sports news
- Select one story from each domain
- Choose the best overall story
- Generate social media content
- Generate an image
- Save the generated output locally

This phase intentionally excludes production infrastructure.

---

## Phase 2 - Application

Transform the MVP into a production-style application.

Add:

- FastAPI
- Docker
- Configuration management
- Logging
- Better error handling
- Testing

---

## Phase 3 - Cloud Deployment

Deploy the application to AWS.

Potential additions include:

- EventBridge scheduling
- Amazon S3
- Amazon RDS
- Amazon ECS
- CloudWatch
- Secrets Manager

---

## Phase 4 - Advanced Features

Potential future improvements include:

- Human-in-the-loop approval
- Long-term memory
- Additional publishing platforms
- Analytics
- Dashboard
- Observability