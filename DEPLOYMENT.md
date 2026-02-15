# Развертывание на удаленном сервере

Этот проект настроен для автоматического развертывания на удаленном Linux-сервере через GitHub Actions при коммите в ветку `deploy`.

## Требования к серверу

- Linux-сервер с SSH доступом
- Docker и Docker Compose установлены
- Доступ на запись в директорию `/opt/`
- Открытый порт SSH (по умолчанию 22)

## Настройка GitHub Secrets

Для работы автоматического развертывания необходимо настроить следующие секреты в репозитории GitHub (Settings → Secrets and variables → Actions → New repository secret):

### Обязательные секреты для SSH подключения:

| Секрет | Описание |
|--------|----------|
| `SSH_HOST` | IP-адрес или домен сервера (например: `192.168.1.100` или `example.com`) |
| `SSH_USERNAME` | Имя пользователя для SSH (например: `root` или `deploy`) |
| `SSH_PRIVATE_KEY` | Приватный SSH ключ для подключения к серверу |
| `SSH_PORT` | (Опционально) Порт SSH, если отличается от 22 |

### Обязательные секреты для бота:

| Секрет | Описание |
|--------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота (получить у [@BotFather](https://t.me/BotFather)) |
| `MISTRAL_API_KEY` | API ключ Mistral AI (получить на [console.mistral.ai](https://console.mistral.ai/)) |

### Опциональные секреты:

| Секрет | Описание |
|--------|----------|
| `GOOGLE_API_KEY` | API ключ Google Custom Search (для улучшенного веб-поиска) |
| `GOOGLE_SEARCH_ENGINE_ID` | ID поискового движка Google |

## Настройка SSH ключей

### 1. Генерация SSH ключа (на вашем компьютере)

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy
```

Это создаст два файла:
- `~/.ssh/github_deploy` - приватный ключ (для GitHub Secrets)
- `~/.ssh/github_deploy.pub` - публичный ключ (для сервера)

### 2. Копирование публичного ключа на сервер

```bash
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server.com
```

Или вручную:
```bash
# На сервере
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "содержимое github_deploy.pub" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 3. Добавление приватного ключа в GitHub Secrets

Скопируйте содержимое приватного ключа:
```bash
cat ~/.ssh/github_deploy
```

И добавьте его в GitHub Secrets как `SSH_PRIVATE_KEY`.

## Процесс развертывания

При коммите в ветку `deploy` автоматически запускается следующий процесс:

1. **Подключение к серверу** - GitHub Actions подключается к серверу по SSH
2. **Обновление кода**:
   - Если проект не существует в `/opt/teleChatBot`, он клонируется
   - Если существует, выполняется обновление (`git fetch` + `git reset`)
3. **Управление конфигурацией**:
   - Создается файл `.env` из GitHub Secrets (если не существует)
   - Обновляются значения в существующем `.env`
   - Копируются примеры конфигурационных файлов (если нужно)
4. **Перезапуск Docker контейнера**:
   - Остановка текущего контейнера (`docker compose down`)
   - Пересборка образа (`docker compose build --no-cache`)
   - Запуск нового контейнера (`docker compose up -d`)

## Использование

### Первоначальное развертывание

1. Настройте все GitHub Secrets (см. выше)
2. Создайте и переключитесь на ветку `deploy`:
   ```bash
   git checkout -b deploy
   git push origin deploy
   ```

### Обновление развернутого проекта

Просто сделайте коммит в ветку `deploy`:
```bash
git checkout deploy
git merge main  # или сделайте необходимые изменения
git push origin deploy
```

GitHub Actions автоматически развернет обновления на сервер.

## Проверка статуса развертывания

1. Перейдите в раздел **Actions** в вашем репозитории GitHub
2. Найдите последний запуск workflow "Deploy"
3. Просмотрите логи для диагностики проблем

## Ручная проверка на сервере

Подключитесь к серверу и проверьте статус:

```bash
ssh user@your-server.com
cd /opt/teleChatBot
docker compose ps
docker compose logs -f bot
```

## Устранение проблем

### Ошибка подключения SSH

- Проверьте правильность `SSH_HOST`, `SSH_USERNAME`, `SSH_PORT`
- Убедитесь, что публичный ключ добавлен в `~/.ssh/authorized_keys` на сервере
- Проверьте права на файлы: `chmod 600 ~/.ssh/authorized_keys && chmod 700 ~/.ssh`

### Ошибка доступа к /opt/

Убедитесь, что пользователь имеет права на запись в `/opt/`:
```bash
sudo chown -R your-user:your-user /opt/teleChatBot
```

Или используйте `sudo` в скрипте развертывания (добавьте к пользователю sudo без пароля).

### Docker не запускается

- Проверьте, что Docker установлен: `docker --version`
- Проверьте, что пользователь добавлен в группу docker: `sudo usermod -aG docker your-user`
- Перезагрузитесь после добавления в группу

### Контейнер не запускается

Проверьте логи:
```bash
cd /opt/teleChatBot
docker compose logs -f
```

Проверьте правильность `.env` файла и конфигураций.

## Безопасность

- ⚠️ **Никогда не коммитьте файл `.env` или приватные ключи в репозиторий**
- ✅ Используйте GitHub Secrets для всех конфиденциальных данных
- ✅ Ограничьте SSH доступ только с необходимых IP (через firewall)
- ✅ Используйте SSH ключи вместо паролей
- ✅ Регулярно обновляйте SSH ключи
- ✅ Установите права `600` на `.env` файл

## Дополнительная информация

Для настройки бота см. основной [README.md](README.md).
