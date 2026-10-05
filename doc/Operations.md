# Operations

This project is operated as a local or containerized learning workflow. It is not designed as a multi-user service, hosted product, or reusable automation platform for other teams.

## Runtime Requirements

Required:

- Python 3.10 or newer
- OpenAI API key
- AWS credentials
- S3 bucket name and region
- Network access to RSS feeds, OpenAI, S3, and any enabled publishing APIs

Optional:

- Instagram professional account and Meta access token
- X OAuth client credentials
- AWS Secrets Manager secret containing X user tokens
- LangSmith tracing configuration

## Environment Variables

The application loads environment values with `python-dotenv`, so local development can use a `.env` file.

### OpenAI

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5
OPENAI_IMAGE_MODEL=gpt-image-1
```

`OPENAI_API_KEY` is required. `OPENAI_MODEL` defaults to `gpt-5.5` when unset.

`OPENAI_IMAGE_MODEL` is only used if AI image generation is re-enabled in `ai_editorial_team/application/workflow.py`. The default workflow uses template-rendered images instead.

### AWS and S3

```dotenv
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET_NAME=
```

`AWS_REGION` and `S3_BUCKET_NAME` are required by the S3 image storage adapter. AWS credentials can be supplied through environment variables, an AWS profile, ECS task role, or another standard boto3 credential source.

The configured identity needs permission to:

- upload objects to the bucket
- read uploaded objects through presigned `GetObject` URLs

Generated objects are written under the `images/` prefix.

### Instagram

```dotenv
META_ACCESS_TOKEN=
INSTAGRAM_PROFESSIONAL_ACCOUNT_ID=
GRAPH_API_VERSION=v24.0
```

Instagram publishing is optional. If `META_ACCESS_TOKEN` or `INSTAGRAM_PROFESSIONAL_ACCOUNT_ID` is missing, startup creates an unavailable Instagram publisher and the workflow reports a failed Instagram publication instead of exiting.

When configured, the publisher expects:

- a professional Instagram account
- a Meta access token with permission to create and publish media
- S3 presigned image URLs that are reachable by Meta's servers

The publisher creates exactly three carousel item containers and one parent carousel container.

### X

```dotenv
X_CLIENT_ID=
X_CLIENT_SECRET=
X_ACCESS_TOKEN=
X_REFRESH_TOKEN=
```

`X_CLIENT_ID` and `X_CLIENT_SECRET` are read from the environment. Current user access and refresh tokens are read from AWS Secrets Manager in production code, not directly from `.env`.

The default secret name is:

```text
ai-editorial-team/prod
```

That secret must be a JSON object containing:

```json
{
  "X_ACCESS_TOKEN": "current-access-token",
  "X_REFRESH_TOKEN": "current-refresh-token"
}
```

Additional keys in the same secret are preserved when refreshed X tokens are written back.

## X OAuth Bootstrap

Use the helper script to get an initial access token and refresh token:

```bash
python scripts/x_oauth_helper.py
```

The helper:

1. Reads `X_CLIENT_ID` and `X_CLIENT_SECRET`.
2. Prints an authorization URL.
3. Waits for a callback at `http://127.0.0.1:8000/callback`.
4. Exchanges the authorization code for tokens.
5. Prints the access token, refresh token, and expiration.

Store the printed tokens in the configured AWS Secrets Manager secret. The runtime publisher refreshes them before posting and persists the refreshed values.

## LangSmith

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=ai-editorial-team-dev
LANGSMITH_WORKSPACE_ID=
LANGSMITH_API_KEY=
```

The OpenAI client is wrapped with LangSmith support. At process shutdown, `main.py` waits for LangChain tracers to flush.

## Running the Workflow

From the repository root:

```bash
python main.py
```

Expected output includes:

- ranked stories
- generated Instagram captions
- image prompt values
- local generated image paths
- S3 object keys
- S3 presigned image URLs
- Instagram publication result
- generated X post
- X publication result

## Generated Files

Local images are written to:

```text
output/images/
```

The repository does not rely on these images being committed.

## Common Failure Modes

Missing `OPENAI_API_KEY`:

The application exits before the workflow starts.

Missing `AWS_REGION` or `S3_BUCKET_NAME`:

The application exits before the workflow starts because S3 storage is required.

RSS feed failures:

If a domain cannot produce any articles across its configured feeds, the workflow exits with an RSS error.

Missing Instagram credentials:

The workflow continues and reports Instagram publication as failed.

Missing X credentials or Secrets Manager tokens:

The workflow continues and reports X publication as failed.

Expired Instagram access token:

The Instagram publisher reports an authentication failure. Refresh the Meta token and update `.env` or the deployment secret source.

X refresh token failure:

Check that the Secrets Manager secret contains the latest refresh token and that the X OAuth client credentials match the app that issued it.

Instagram cannot fetch images:

Check that the S3 presigned URLs have not expired and are reachable from outside the local network.

## Deployment Notes

The repository includes:

- `Dockerfile`
- `task-definition.json`

The Docker image runs `python main.py`. Deployment environments must supply the same required environment values as local development, plus AWS permissions for S3 and Secrets Manager when X publishing is enabled.
