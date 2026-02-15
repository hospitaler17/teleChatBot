# Quick Start: Deployment Setup

## Step 1: Generate SSH Keys
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy
```

## Step 2: Add Public Key to Server
```bash
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server.com
```

## Step 3: Configure GitHub Secrets
Go to: `Settings → Secrets and variables → Actions → New repository secret`

Add these secrets:
- `SSH_HOST` - Your server IP/domain
- `SSH_USERNAME` - SSH username
- `SSH_PRIVATE_KEY` - Content of `~/.ssh/github_deploy`
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `MISTRAL_API_KEY` - Your Mistral API key

## Step 4: Deploy
```bash
git checkout -b deploy
git merge main  # or make your changes
git push origin deploy
```

The GitHub Action will automatically deploy to your server!

## Check Status
- GitHub: Go to **Actions** tab → View "Deploy" workflow
- Server: `ssh user@server "cd /opt/teleChatBot && docker compose ps"`

For full documentation, see [DEPLOYMENT.md](../DEPLOYMENT.md)
