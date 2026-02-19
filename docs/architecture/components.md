# Architecture

## System Overview

The bot is structured as three thin layers wired together at startup:

| Layer | Package | Responsibility |
|-------|---------|---------------|
| **Config** | `src/config/` | Load secrets from `.env`, settings from YAML |
| **API** | `src/api/` | Mistral AI client, model selector, web search, conversation memory, reactions |
| **Bot / CLI** | `src/bot/`, `src/cli/` | Telegram dispatcher, access control, message/command/admin handlers |

---

## Component diagram

```{plantuml} overview.puml
```

---

## Request processing flow

```{plantuml} request_flow.puml
```

---

## Class diagram

```{plantuml} class_diagram.puml
```

---

## Key design decisions

### Dynamic model selection (`ModelSelector`)
Rather than hard-coding a single model, every request is analysed for signals — code
content, complexity indicators, image attachments, context size — and routed to the most
cost-effective Mistral model (`codestral-latest`, `pixtral-12b-latest`,
`mistral-large-latest`, etc.).

### Streaming with back-pressure (`MessageHandler._handle_streaming_response`)
Progressive responses are sent as Telegram message edits. An **update-interval throttle**
(configurable, default 1 s) prevents hitting Telegram's per-chat rate limit while still
giving a real-time feel.  Multi-part messages (> 4096 chars) are split and sent
with a `(часть N/M)` prefix.

### Conversation memory (`ConversationMemory`)
History is keyed by *context id* — `user_id` in private chats, `chat_id` in groups.
A sliding window (`conversation_history_size`, default 10 pairs) is kept to stay within
model context limits.

### Access control (`AccessFilter`)
Two-level model: *allowed users* (private chats) and *allowed chats* (groups).
Admin commands can modify both lists at runtime without restarting the bot.
