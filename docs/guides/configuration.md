# Configuration

The bot is configured through two files and environment variables.

## Environment variables / `.env`

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token from @BotFather |
| `MISTRAL_API_KEY` | ✅ | Mistral AI API key |
| `GOOGLE_API_KEY` | ❌ | Google Custom Search API key |
| `GOOGLE_SEARCH_ENGINE_ID` | ❌ | Google Custom Search Engine ID |

Create a `.env` file in the project root:

```ini
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
MISTRAL_API_KEY=your_mistral_key
```

---

## `config/config.yaml`

Copy the example file and edit:

```bash
cp config/config.example.yaml config/config.yaml
```

### `mistral` section

```yaml
mistral:
  model: mistral-small-latest      # Default model (overridden by ModelSelector)
  max_tokens: 1024
  temperature: 0.7
  system_prompt: "You are a helpful assistant."
  enable_web_search: false          # Augment answers with search results
  conversation_history_size: 10     # Number of message pairs kept in context
  always_append_date: false         # Always inject today's date into system prompt
```

### `bot` section

```yaml
bot:
  username: "YourBotUsername"       # Without the @ sign
  language: ru
  max_message_length: 4096
  enable_streaming: true
  streaming_threshold: 100          # Chars accumulated before first edit
  streaming_update_interval: 1.0   # Seconds between edits (respect rate limits)
```

### `admin` section

```yaml
admin:
  user_ids:
    - 123456789   # Your Telegram user ID
```

### `reactions` section

```yaml
reactions:
  enabled: false
  model: mistral-small-latest
  probability: 0.3           # 30 % of qualifying messages get a reaction
  min_words: 5
  moods:
    positive: "👍"
    negative: "👎"
    neutral: "🤔"
    funny: "😄"
    sad: "😢"
    angry: "😠"
    excited: "🎉"
    thoughtful: "💭"
```

---

## `config/allowed_users.yaml`

Managed at runtime via admin commands, but can be pre-filled manually:

```yaml
allowed_user_ids:
  - 111111111
  - 222222222
allowed_chat_ids:
  - -100123456789
reactions_enabled: true
always_append_date_enabled: true
```

---

## Finding your Telegram ID

Send `/start` to [@userinfobot](https://t.me/userinfobot) on Telegram — it will reply
with your numeric user ID.
