# Admin Guide

Administrators control the bot's access lists and feature toggles at runtime using
Telegram commands — no config file edit or restart needed.

## Becoming an admin

Add your Telegram user ID to `config/config.yaml` under `admin.user_ids`:

```yaml
admin:
  user_ids:
    - 123456789
```

Restart the bot after editing this file.

## Admin commands reference

All commands below are only accepted from admin users.  Non-admin attempts receive
`⛔ У вас нет прав администратора.`

### Access management

| Command | Syntax | Description |
|---------|--------|-------------|
| `/admin_add_user` | `/admin_add_user <user_id>` | Allow a user in private chats |
| `/admin_remove_user` | `/admin_remove_user <user_id>` | Revoke private-chat access |
| `/admin_add_chat` | `/admin_add_chat <chat_id>` | Allow a group/supergroup |
| `/admin_remove_chat` | `/admin_remove_chat <chat_id>` | Revoke group access |
| `/admin_list` | `/admin_list` | Show current allowlists + feature statuses |

### Reaction control

| Command | Description |
|---------|-------------|
| `/admin_reactions_on` | Enable automatic message reactions |
| `/admin_reactions_off` | Disable automatic message reactions |
| `/admin_reactions_status` | Show current reactions configuration |

### Date-in-prompt control

| Command | Description |
|---------|-------------|
| `/admin_date_on` | Always inject the current date into the system prompt |
| `/admin_date_off` | Disable automatic date injection |
| `/admin_date_status` | Show current date-injection status |

## Getting chat IDs

Forward a message from the target group to
[@userinfobot](https://t.me/userinfobot) — it will return the numeric chat ID
(typically a large negative number like `-100123456789`).

## Reactions feature

Reactions require:
1. `reactions.enabled: true` in `config/config.yaml` (compile-time flag), **and**
2. runtime switch enabled via `/admin_reactions_on` (or `reactions_enabled: true` in
   `config/allowed_users.yaml`).

Both flags must be `true` for reactions to fire.  The probability of reacting to
any given message is controlled by `reactions.probability` (default: `0.3` = 30 %).

## Security notes

- Only admin IDs listed in `config.yaml` can run admin commands.
- The access list is persisted to `config/allowed_users.yaml` after every change.
- Restart has no effect on the allow list — it is reloaded at startup.
