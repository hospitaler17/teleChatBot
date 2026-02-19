# CLI Mode

The bot includes an interactive command-line interface (CLI) that lets you chat with
the Mistral model directly in your terminal — no Telegram connection required.

## Enabling CLI mode

Set `cli_mode: true` in `config/config.yaml`:

```yaml
bot:
  cli_mode: true
```

Or run with the environment variable:

```bash
python -m src.main
```

The entry-point (`src/main.py`) automatically detects `cli_mode` and launches
`src.cli.cli_chat.CLIChat` instead of the Telegram bot.

## Available commands in the CLI

| Command | Description |
|---------|-------------|
| `/help` | Show all available CLI commands |
| `/clear` | Clear conversation history |
| `/history` | Show recent conversation history |
| `/model <name>` | Switch to a different Mistral model |
| `/admin_add_user <id>` | Add a user to the allowed list |
| `/admin_remove_user <id>` | Remove a user from the allowed list |
| `/admin_add_chat <id>` | Add a chat to the allowed list |
| `/admin_remove_chat <id>` | Remove a chat from the allowed list |
| `/admin_list` | Show current access configuration |
| `/admin_reactions_on` | Enable automatic reactions |
| `/admin_reactions_off` | Disable automatic reactions |
| `/exit` or `/quit` | Exit the CLI |

## Example session

```
You: Hello! What can you do?
Bot: I'm a helpful assistant powered by Mistral AI...

You: /model mistral-large-latest
Bot: ✅ Model switched to mistral-large-latest

You: /clear
Bot: ✅ Conversation history cleared.

You: /exit
```

## Streaming in CLI mode

Streaming is supported in CLI mode — responses are printed progressively to the
terminal as they arrive from the Mistral API.  Toggle via:

```yaml
bot:
  enable_streaming: true
```
