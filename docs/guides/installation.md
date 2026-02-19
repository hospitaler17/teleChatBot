# Installation

## Requirements

- Python 3.11+
- A [Telegram Bot Token](https://core.telegram.org/bots#botfather)
- A [Mistral AI API key](https://console.mistral.ai/)
- *(Optional)* Google Custom Search API key + Engine ID for web-search augmentation

---

## Local installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/teleChatBot.git
cd teleChatBot

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 3. Install runtime dependencies
pip install -r requirements.txt
```

---

## Docker

```bash
# Build
docker build -t telechatbot .

# Run (pass env vars with --env-file)
docker run --env-file .env telechatbot
```

Or with Docker Compose:

```bash
docker compose up -d
```

The `docker-compose.yml` mounts `./config` into the container so you can edit YAML
files without rebuilding the image.

---

## Development extras

Install test and lint tools:

```bash
pip install -r requirements-dev.txt
```

Build the documentation locally:

```bash
pip install -r docs/requirements.txt
sphinx-build -b html docs docs/_build/html
# then open docs/_build/html/index.html
```
