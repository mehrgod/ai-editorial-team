# System Architecture

AI Editorial Team is a CLI-first learning project for exploring agentic workflow design. It combines LangGraph orchestration, OpenAI-backed reasoning agents, RSS research, local image rendering, S3 storage, and optional social publishing.

The original design documents mention future pieces such as FastAPI and MCP tools. The current implementation is simpler and more direct: concrete Python adapters implement domain ports, and `main.py` wires those adapters into a LangGraph workflow.

## Runtime Flow

```text
main.py
  |
  v
CLI wiring and environment configuration
  |
  v
EditorialWorkflow LangGraph
  |
  +--> Finance RSS Research Agent
  +--> AI RSS Research Agent
  +--> Sports RSS Research Agent
          |
          v
      Chief Editor Agent
          |
          v
      X Content Agent
          |
          v
      Instagram Content Agent
          |
          v
      Image Prompt Agent
          |
          v
      Image Generator / Template Renderer
          |
          v
      S3 Image Storage
          |
          v
      Instagram Carousel Publisher
          |
          v
      X Publisher
```

The workflow returns an `EditorialPackage` containing ranked Instagram story content, generated X content, and publication results for both platforms.

## Layers

### Domain

Location: `ai_editorial_team/domain`

The domain layer defines the stable data contracts and ports:

- `Story`, `RankedStory`, `InstagramStoryContent`, `XContent`
- `GeneratedImage`, `StoredImage`, `PublicationRequest`, `PublicationResult`
- Protocols such as `ResearchAgent`, `ChiefEditor`, `ImageStorage`, and `SocialPublisher`

This layer has no dependency on OpenAI, AWS, Instagram, X, or LangGraph.

### Application

Location: `ai_editorial_team/application/workflow.py`

`EditorialWorkflow` owns the LangGraph state machine. It coordinates the domain ports and enforces workflow-level assumptions:

- Exactly three research stories are expected.
- Ranked stories must be ordered as ranks `1`, `2`, and `3`.
- Instagram carousel publishing requires three stored image URLs.
- X publishing requires three local image paths and generated post text no longer than 250 characters.

Publisher exceptions are caught inside workflow nodes and converted into failed `PublicationResult` objects so one publishing problem does not erase the rest of the editorial package.

### Infrastructure

Location: `ai_editorial_team/infrastructure`

Infrastructure modules implement the domain ports:

- `research/rss_agents.py`: RSS and Atom feed fetching, parsing, recency sorting, and LLM-assisted newsworthiness filtering.
- `openai/`: OpenAI SDK configuration and shared client creation.
- `content/`: OpenAI agents for summaries, newsworthiness, Instagram captions, X posts, and image prompts.
- `editor/`: Chief Editor ranking agent.
- `image_generation/`: OpenAI image generation and template image rendering.
- `image_storage/`: S3 upload and presigned URL generation.
- `publishing/`: Instagram Graph API carousel publishing and X media/post publishing.

### Presentation

Location: `ai_editorial_team/presentation/cli.py`

The CLI prints the ranked stories, generated content, image storage details, and publication results. There is no web server in the current implementation.

## Research

Each research agent is configured with one domain and a small set of RSS feeds:

- Finance: CBS News MoneyWatch, BBC News Business, CNA Business
- Artificial Intelligence: MIT News AI, Google AI Blog, Hugging Face Blog
- Sports: ESPN, BBC Sport, CBS Sports

The RSS adapter fetches all configured feeds, parses RSS or Atom entries, sorts articles by publication time, and asks the newsworthiness agent to assess a bounded number of recent candidates. If no article passes the newsworthiness and domain checks, the agent returns a pending placeholder story for that domain.

## Content Generation

OpenAI-backed agents are responsible for language tasks:

- Fill in missing story summaries.
- Decide whether RSS candidates are timely and on-domain.
- Rank the three candidate stories.
- Generate Instagram captions.
- Generate a concise X post.
- Generate an image prompt if AI image generation is re-enabled.

The application layer treats these as replaceable ports. A different model provider could be introduced by implementing the same protocols.

## Images

AI image generation is currently disabled by the `AI_IMAGE_GENERATION_ENABLED` flag in `workflow.py`. With the default setting, all ranked stories use `TemplateImageRenderer`, which creates square PNG social cards with Pillow and writes them to `output/images/`.

`OpenAIImageGenerator` still exists and can generate a `1024x1024` PNG from a prompt if the workflow flag is re-enabled.

## Storage

`S3ImageStorage` uploads each generated local image to the configured S3 bucket under the `images/` prefix and returns:

- the S3 object key
- a presigned URL that can be used by Instagram to read the image

S3 configuration is required because storage happens before the publishing nodes.

## Publishing

### Instagram

`InstagramPublisher` publishes a three-image carousel through the Instagram Graph API:

1. Create one carousel item container per image URL.
2. Poll each child container until it is ready.
3. Create a parent carousel container with the caption.
4. Poll the parent container until it is ready.
5. Publish the container.
6. Resolve the publication permalink.

Missing or invalid Instagram configuration creates an unavailable publisher during startup. The workflow still completes and reports Instagram publication as failed.

### X

`XPublisher` uploads three local images, creates a post with attached media IDs, and returns the X status URL.

The X factory reads current user tokens from AWS Secrets Manager, refreshes the access token with the configured X OAuth client, and writes refreshed tokens back to the same secret. Missing or invalid X configuration creates an unavailable publisher during startup.

## Error Handling

Startup errors from required infrastructure stop the CLI:

- missing OpenAI API key
- missing S3 configuration
- RSS feeds that cannot produce stories

Publishing errors are intentionally isolated. Instagram or X failures become failed publication results so the user can still inspect the generated editorial package.

## Design Principles

- Agents make editorial decisions.
- Adapters perform external side effects.
- The application layer orchestrates through ports.
- Domain models stay independent of vendors.
- Integrations should be replaceable without rewriting the workflow.
