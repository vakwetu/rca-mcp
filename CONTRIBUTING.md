# Contributing to rca-api

This document explains how to use rca-api standalone and how to validate a change.

## Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) and [npm](https://www.npmjs.com/) for managing dependencies and running the project.

On Fedora, you can install them with:
```bash
sudo dnf install -y uv nodejs
```

### Kerberos ticket and SF_DOMAIN

The project requires a valid kerberos ticket to access the build logs from SF_DOMAIN.

### Gemini API Key

This project requires access to Gemini.

### Opik Integration

This project includes integration with [Opik](https://www.comet.com/docs/opik/) for tracing and observability of LLM interactions. Opik helps track and analyze the prompts and responses sent to language models during RCA analysis.

#### Local Opik Server

By default, the integration assumes a local Opik server is running. No additional configuration is required - traces will be automatically sent to the local Opik instance.
Setting up a local Opik server is super easy.  Just follow the instructions at [Local Deployment](https://www.comet.com/docs/opik/self-host/local_deployment/)

#### Cloud Opik Deployment

To use Opik Cloud or a custom Opik deployment, set the following environment variables:

```bash
export OPIK_API_KEY=your-opik-api-key
export OPIK_PROJECT_NAME=your-project-name  # Optional, defaults to "rca-mcp"
```

#### Disabling Opik Integration

To explicitly disable Opik integration, set the following environment variable:

```bash
export OPIK_DISABLED=true
```

If you don't set this variable, the application will automatically fall back to running without Opik integration if the Opik server is unavailable or if there are configuration issues.

## Usage

To install the project dependencies, run the following command in the root directory:
```bash
uv sync && npm install
```

### Command Line Interface

To use the command-line tool, run:
```ShellSession
$ export SF_DOMAIN=sf.example.com
$ export LLM_GEMINI_KEY=<api key from bitwarden>
$ uv run rcav2 --help
```

**Example:**
```ShellSession
$ uv run rcav2 $BUILD_URL
[RCA will be printed here]
```

### API

Build the frontend asset and serve the standalone API:

```bash
make serve
```

### Hot reload frontend

When working on the RcaComponent, run the API alone in a different terminal:

```bash
make backend-serve
```

And run the Vite development server with hot-reloading enabled:

```bash
make frontend-serve
```

## Tests

To validate your changes, run the continuous integration script:
```ShellSession
$ make ci
```
