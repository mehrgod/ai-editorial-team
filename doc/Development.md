# Development Guide

This guide explains how the code is organized and how to extend it. The project is intentionally scoped as a learning implementation, so development choices favor clarity and replaceable boundaries over a polished public API.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run tests:

```bash
python -m unittest discover -s tests
```

Run the application:

```bash
python main.py
```

## Main Entry Points

- `main.py`: validates Python version, builds concrete infrastructure adapters, creates the workflow, and runs the CLI.
- `ai_editorial_team/application/workflow.py`: defines the LangGraph state machine and workflow nodes.
- `ai_editorial_team/presentation/cli.py`: prints workflow output.

## Domain Contracts

Domain contracts live in `ai_editorial_team/domain`.

`models.py` contains shared data shapes such as:

- `Story`
- `RankedStory`
- `EditorialPackage`
- `InstagramStoryContent`
- `XContent`
- `GeneratedImage`
- `StoredImage`
- `PublicationRequest`
- `PublicationResult`

`ports.py` contains protocols for replaceable behavior:

- `ResearchAgent`
- `StorySummaryAgent`
- `StoryNewsworthinessAgent`
- `ChiefEditor`
- `InstagramContentAgent`
- `XContentAgent`
- `ImagePromptAgent`
- `ImageGenerator`
- `TemplateImageRenderer`
- `ImageStorage`
- `SocialPublisher`

When adding a new integration, prefer implementing one of these ports instead of changing the workflow directly.

## Workflow State

`EditorialWorkflow` uses `EditorialGraphState`, a LangGraph state object with these main values:

- `stories`
- `ranked_stories`
- `instagram_story_contents`
- `instagram_publication`
- `x_content`
- `x_publication`

Research nodes run from the start node and append their stories into the shared `stories` list. The remaining nodes operate in sequence because later steps need ranked stories, generated content, local images, stored image URLs, and publication inputs.

## Adding a Research Domain

The current workflow assumes exactly three domains: Finance, Artificial Intelligence, and Sports.

To add a fourth domain:

1. Add a new RSS factory in `infrastructure/research/rss_agents.py`.
2. Add a new research agent dependency to `EditorialWorkflow`.
3. Add a new LangGraph node and edge from `START` to that node.
4. Update rank validation rules that currently expect exactly three ranked stories.
5. Update Instagram and X publishing assumptions if the number of images/posts should change.
6. Add tests for ordering, validation, and publishing payloads.

The current publishing implementation expects exactly three images, so domain-count changes are a workflow-level change rather than a feed-only change.

## Replacing RSS Research

RSS research is isolated behind `ResearchAgent`. A News API, search API, or database-backed implementation can replace `RssResearchAgent` by returning a `Story` with:

- `domain`
- `headline`
- `summary`
- `reason`

Keep external API calls in infrastructure. The application layer should continue to depend only on the `ResearchAgent` protocol.

## Replacing OpenAI Agents

OpenAI-specific logic lives in:

- `infrastructure/openai`
- `infrastructure/content`
- `infrastructure/editor`
- `infrastructure/image_generation/openai_image_generator.py`

To use a different model provider, implement the relevant domain ports and change the wiring in `main.py`.

## Image Generation

The default workflow uses `TemplateImageRenderer` for all images because `AI_IMAGE_GENERATION_ENABLED` is set to `False` in `workflow.py`.

To re-enable AI image generation:

1. Set `AI_IMAGE_GENERATION_ENABLED = True`.
2. Make sure `OPENAI_IMAGE_MODEL` is configured if the default is not desired.
3. Verify the image prompt agent and image generator behavior with tests.

With the current condition, only the rank 1 story uses AI image generation when enabled. Lower-ranked stories continue to use the template renderer.

## Publishing

Publishing is isolated behind `SocialPublisher`.

Instagram publishing expects a `PublicationRequest` with:

- `caption`
- `image_urls`, exactly three externally reachable URLs

X publishing expects:

- `text`, no more than 250 characters
- `image_paths`, exactly three local image files

Publisher factories are wrapped by `_create_optional_publisher` in `main.py`. Configuration errors produce an `UnavailablePublisher`, allowing the workflow to complete without that platform.

## Testing Approach

Tests rely on fakes and mocks instead of real network calls.

Useful test areas:

- `test_editorial_ranking.py`: workflow orchestration and CLI output.
- `test_rss_research.py`: RSS candidate ordering and newsworthiness filtering.
- `test_openai_client.py`: OpenAI client configuration.
- `test_image_generation.py`: image byte extraction and file writing.
- `test_s3_image_storage.py`: S3 object keys, upload behavior, and presigned URL handling.
- `test_instagram_publishing.py`: carousel publishing flow and Graph API error mapping.
- `test_x_publishing.py`: media upload, post creation, token refresh, and Secrets Manager persistence.

When adding a new adapter, test it through its protocol boundary with fake clients where possible.

## Documentation Updates

Keep `README.md`, `doc/Architecture.md`, and `doc/Operations.md` aligned with code changes that affect:

- required environment variables
- workflow steps
- external services
- generated outputs
- publishing behavior
- deployment assumptions

The PRD is historical context from the beginning of the project. Update it only when you want to preserve product intent, not as the source of truth for current implementation details.
