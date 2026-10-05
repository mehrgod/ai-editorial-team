# AI Editorial Team

AI Editorial Team is a learning project that explores how an agentic editorial workflow can be built with Python, LangGraph, OpenAI-backed agents, and production-style infrastructure boundaries.

The project is not intended to be a packaged product, public service, or reusable tool for other teams. It is a personal learning implementation meant to exercise real engineering concerns: orchestration, clean boundaries, external API integration, image generation/rendering, cloud storage, publishing, and tests.

## What It Does

The application runs a command-line editorial workflow:

1. Fetch recent RSS stories from Finance, Artificial Intelligence, and Sports sources.
2. Ask a newsworthiness agent to filter for timely, on-domain stories.
3. Summarize RSS stories when feeds provide missing or placeholder summaries.
4. Rank the three domain candidates with a Chief Editor agent.
5. Generate an X post and Instagram captions.
6. Render local square social-card images.
7. Upload generated images to S3 and create presigned URLs.
8. Attempt to publish an Instagram carousel and an X post.
9. Print the editorial package and publication results in the terminal.

Instagram and X publishers are optional at startup. If their credentials are missing or invalid, the workflow still runs and reports failed publication results for those platforms. OpenAI and S3 configuration are required.

## Project Structure

```text
ai_editorial_team/
  application/        LangGraph workflow orchestration
  domain/             TypedDict models and protocol ports
  infrastructure/     RSS, OpenAI, image, S3, Instagram, and X adapters
  presentation/       CLI output
doc/                  Project documentation and historical milestone notes
scripts/              Local helper scripts
tests/                Unit tests with fakes/mocks around external services
main.py               CLI entrypoint
```

The implementation follows a clean architecture style: the application layer depends on domain ports, while infrastructure adapters handle concrete APIs.

## Requirements

- Python 3.10 or newer
- OpenAI API key
- AWS credentials with access to the configured S3 bucket
- Optional Instagram Graph API credentials
- Optional X API credentials and AWS Secrets Manager token storage

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Required for the workflow to start:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5
AWS_REGION=us-east-1
S3_BUCKET_NAME=
```

AWS credentials can come from environment variables, a local AWS profile, or the runtime environment:

```dotenv
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

Optional publishing configuration:

```dotenv
META_ACCESS_TOKEN=
INSTAGRAM_PROFESSIONAL_ACCOUNT_ID=
GRAPH_API_VERSION=v24.0

X_CLIENT_ID=
X_CLIENT_SECRET=
```

See [Operations](doc/Operations.md) for the full environment variable guide, X OAuth bootstrap flow, and common failure modes.

## Running Locally

Run the workflow from the repository root:

```bash
python main.py
```

The command prints ranked stories, generated captions, local image paths, S3 object keys, presigned image URLs, and publication status for Instagram and X.

Generated local images are written under:

```text
output/images/
```

## Testing

Run the unit test suite:

```bash
python -m unittest discover -s tests
```

The tests use fake or mocked adapters for external services. They cover the workflow, RSS selection, OpenAI client setup, image rendering/storage, Instagram publishing, and X publishing.

## Docker

Build the image:

```bash
docker build -t ai-editorial-team .
```

Run it with environment values supplied by your shell or deployment runtime:

```bash
docker run --env-file .env ai-editorial-team
```

## Documentation

- [Architecture](doc/Architecture.md): current system design and workflow.
- [Operations](doc/Operations.md): environment variables, publishing setup, and runtime notes.
- [Development](doc/Development.md): code organization, extension points, and testing guidance.
- [PRD](doc/PRD.md): historical starting requirements, not the current source of truth.

## Current Limitations

- The application is CLI-first. There is no web UI or API server.
- The workflow always expects the three configured domains.
- S3 storage is currently required even when social publishing is unavailable.
- AI image generation is disabled in the workflow; template-rendered images are used by default.
- The project is maintained as a learning exercise, so operational polish is intentionally limited.
