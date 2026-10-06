# Lecture Bot

Telegram-бот расшифровывает голосовые сообщения, аудио, видео и кружки. Распознавание выполняется локально моделью Whisper. В интернет уходит только обмен с Telegram.

Язык определяется по записи. Пользователь его не выбирает.

## Что бот не делает

- Не отправляет аудио во внешний API распознавания.
- Не принимает webhook. Обновления забираются long polling.
- Не предоставляет веб-админку, плагины и учётные записи, кроме пользователя Telegram.

## Архитектура

```
Telegram
  handlers принимают файл и сразу отвечают, что он в очереди
    ↓
очередь, 2 воркера, не больше 10 задач
    ↓
ffmpeg: mono WAV, 16 кГц, PCM 16-bit
    ↓
Whisper small, CPU, int8
    ↓
PostgreSQL: пользователь, текст, длительность, оценка
    ↓
ответ в Telegram
```

Обработчик Telegram не ждёт распознавание. ffmpeg и Whisper работают в пуле потоков. Запись в базу и ответ в чат возвращаются в event loop. Поэтому длинная запись не блокирует `/stats` и другие сообщения.

Модель одна: `Systran/faster-whisper-small`, около 461 МБ. Каталог после загрузки: `models/faster-whisper-small`. Одновременные распознавания сериализуются блокировкой: модель на CPU одна.

Если очередь заполнена, бот сообщает об этом и не ставит файл в обработку.

## Требования

- Python 3.14
- ffmpeg в `PATH`
- Docker и Docker Compose — для запуска сервисов
- espeak-ng — только для теста распознавания, в работе бота не используется

Модель Whisper в git не входит. Её скачивает `scripts/download_models.sh`. Образ Docker копирует уже скачанную модель внутрь себя.

## Конфигурация

Скопируйте `.env.example` в `.env`. Файл `.env` в git не попадает и в образ не копируется.

Обязательная переменная: `TELEGRAM_BOT_TOKEN` от [@BotFather](https://t.me/BotFather). Без неё процесс не стартует.

| Переменная | По умолчанию | Эффект |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://lecture:lecture@localhost:5433/lecture_bot` | Подключение к PostgreSQL |
| `DATA_DIR` | `data` | Логи, кэш, временные файлы и дампы. Относительный путь считается от корня репозитория |
| `WHISPER_MODEL_PATH` | `models/faster-whisper-small` | Каталог модели |
| `MAX_FILE_SIZE` | `20971520` | Максимальный размер файла, байты (20 МБ) |
| `CACHE_ENABLED` | `true` | Повтор одинакового wav берётся из файлового кэша |
| `BACKUP_ENABLED` | `true` | При старте включается периодический SQL-дамп |
| `BACKUP_INTERVAL_HOURS` | `24` | Интервал между дампами, часы |

Внутри `docker compose` адрес базы перекрывается: `postgresql://lecture:lecture@postgres:5432/lecture_bot`. Порт `5433` на хосте нужен для локального запуска и тестов. Порт `5432` внутри сети Compose.

Запрос к PostgreSQL обрывается через 5 секунд (`statement_timeout`). Если соединение закрыто, следующий запрос открывает его заново.

Видео длиннее 10 минут отклоняется. Это константа в коде, не переменная окружения.

Ключи `ADMIN_PASSWORD`, `ADMIN_USER_ID`, `PLUGINS_ENABLED`, `CACHE_TTL_HOURS`, `FFMPEG_PATH` и `ESPEAK_PATH` в `.env.example` процесс не применяет. Срок жизни кэша задан в коде: 24 часа. Дампы старше 7 дней удаляются.

Пароль `lecture` в Compose предназначен для локальной машины. На публичном сервере его нужно сменить и в Compose, и в `DATABASE_URL`.

## Запуск в Docker

```bash
cp .env.example .env
bash scripts/download_models.sh
docker compose up -d --build
docker compose logs -f lecture-bot
```

Postgres 16 поднимается отдельным сервисом и должен стать healthy до старта бота. Схема применяется при старте бота из `bot/migrations`. Повторный запуск уже применённые файлы не выполняет. Версии лежат в таблице `schema_migrations`.

Остановка без удаления данных:

```bash
docker compose down
```

Удаление тома PostgreSQL:

```bash
docker compose down -v
```

Каталог `./data` Compose не удаляет. Там логи (`data/logs`), кэш (`data/cache`), временные файлы (`data/temp`) и SQL-дампы (`data/backups/backup_YYYYMMDD_HHMMSS.sql`).

## Локальный запуск

Нужен уже запущенный PostgreSQL. Для этого достаточно сервиса из Compose:

```bash
docker compose up -d postgres
python3 -m venv .venv
source .venv/bin/activate
pip install -r bot/requirements.txt
bash scripts/download_models.sh
python bot/main.py
```

`DATABASE_URL` в `.env` должен указывать на `localhost:5433`.

## Данные

Миграция `bot/migrations/001_initial.sql` создаёт три таблицы:

| Таблица | Содержимое |
| --- | --- |
| `users` | `telegram_id`, имя, время последней активности |
| `audio_requests` | файл, размер, длительность, распознанный текст; `user_id` ссылается на внутренний `users.id` |
| `feedback` | оценка `1` или `5` для запроса |

Колонка `users.language_code` остаётся в схеме со значением по умолчанию `ru`. Текущий бот язык пользователя не спрашивает и для распознавания её не читает.

## Команды и кнопки

| Команда | Действие |
| --- | --- |
| `/start` | Приветствие и клавиатура |
| `/help` | Как отправить запись |
| `/stats` | Число расшифровок, объём и суммарная длительность |
| `/settings` | Лимит размера, лимит видео, где выполняется распознавание |

Под полем ввода две кнопки: «Статистика» и «Помощь». Они остаются на экране.

После расшифровки под текстом две кнопки: «Хорошо» (оценка 5) и «Плохо» (оценка 1). Повторное нажатие снимает кнопки. Всплывающее подтверждение показывает, что оценка записана.

Принимаются голосовое сообщение, аудио, видео и кружок.

## Тесты

```bash
pip install pytest
pytest
```

`pytest.ini` добавляет `bot/` в `PYTHONPATH`. Нужен PostgreSQL и `DATABASE_URL`. Если базы нет, тесты базы пропускаются. Тест распознавания пропускается без модели Whisper или без espeak-ng.

Проверяются миграции и запросы к базе, обрыв соединения, конвертация ffmpeg, очередь, оформление текста, кнопки и короткая фраза на русском и английском.

## CI

Файл `.github/workflows/ci.yml`.

На push в `main` и на pull request запускаются тесты: Python 3.14, PostgreSQL 16, ffmpeg, espeak-ng, загрузка модели Whisper, `pytest`.

На push в `main` тот же workflow собирает образ и публикует его в GitHub Container Registry:

- `ghcr.io/skipyatkov/lecture_bot:latest`
- `ghcr.io/skipyatkov/lecture_bot:<sha>`

Образ содержит код и модель. Токен в него не входит. Пакет по умолчанию приватный: для `docker pull` нужен `docker login ghcr.io` с правом `read:packages`.

## Хостинг

GitHub публикует образ, но не держит процесс бота запущенным. Long polling и PostgreSQL должны работать на машине, которая не выключается.

На сервере с Docker:

```bash
docker login ghcr.io
docker pull ghcr.io/skipyatkov/lecture_bot:latest
```

Дальше тот же `docker compose`, что в репозитории: сервис `lecture-bot` можно запускать из собранного локально образа `lecture-bot:local` либо переопределить `image` на `ghcr.io/skipyatkov/lecture_bot:latest`. Переменные `TELEGRAM_BOT_TOKEN` и `DATABASE_URL` передаются при запуске, не запекаются в образ.

## Автор

**SKipyatkov**  
[GitHub](https://github.com/SKipyatkov) · [Telegram](https://t.me/kipyatoook)
