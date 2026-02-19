# teleChatBot

**teleChatBot** is a Telegram bot that bridges users to the [Mistral AI](https://mistral.ai/)
API. It supports private and group chats, streaming responses, automatic model selection,
web search augmentation, and sentiment-based message reactions.

```{toctree}
:maxdepth: 2
:caption: Contents

guides/installation
guides/configuration
guides/cli
guides/admin
api/index
architecture/components
```

## Quick start

1. Copy `config/config.example.yaml` → `config/config.yaml` and fill in your API keys.
2. Copy `config/allowed_users.example.yaml` → `config/allowed_users.yaml`.
3. Run: `python -m src.main`

See [Installation](guides/installation.md) for the full setup guide.

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
