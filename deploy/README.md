# Clicker 3.0 — Docker Deploy

Production-версия для запуска в Docker на базе `dorowu/ubuntu-desktop-lxde-vnc`.

**Архитектура:** один контейнер = один бот. Каждый контейнер — полноценный Ubuntu LXDE
десктоп с Chrome, VNC и noVNC.

## Структура

```
deploy/
├── bot_runner.py              # Entry point — загружает config_bot + config_site_{site}
├── Dockerfile                 # Образ: dorowu/ubuntu-desktop-lxde-vnc + deps
├── docker-compose.yml         # 6 ботов (bot_0 .. bot_5), каждый в своём контейнере
├── config_bot.yaml            # Шаблон конфига одного бота
├── config_bot_0.yaml          # Конфиг бота 0 (site: qwen и т.д.)
├── config_site_qwen.yaml      # Конфиг сайта: url + home/reset + scenarios + prompts
├── config_site_gpt.yaml       # Конфиг другого сайта (создать при необходимости)
├── requirements.txt           # Python зависимости
├── scripts/
│   ├── env_bot.py             # Chrome на DISPLAY контейнера (:1) + xdotool + mss
│   ├── bot_logic.py           # FSM — логика состояний
│   ├── gpu_analyzer.py        # OpenCV template matching
│   ├── state_logger.py        # FSM timeline логгер
│   └── csv_logger.py          # CSV логгер операций
├── templates/                 # Шаблоны PNG для поиска элементов
├── prompts/                   # Текстовые промпты
├── datasets/                  # CSV с вопросами
├── answers/                   # Выход: верифицированные JSON ответы
└── profiles/                  # Профили браузеров
```

## Быстрый старт

### 1. Подготовка

```bash
cd deploy
./setup_deploy.sh
```

Скрипт скопирует `config_main.yaml`, `templates/`, `prompts/`, `datasets/`
из dev-проекта и сгенерирует `config_bot_X.yaml` для каждого бота.

### 2. Настройка конфигов

Отредактируйте `config_bot_X.yaml` для каждого бота:

```yaml
bot:
  site: qwen                        # Определяет какой config_site_X.yaml загружать
  scenario: web_search_no_think     # Сценарий из config_site_qwen.yaml
  browser_master_profile: /home/profiles/bot_0  # Путь ВНУТРИ контейнера
  dataset_path: datasets/sp_after_2000_good.csv
  row_range: [2051, 2100]           # Какие вопросы обрабатывать
  max_questions: 150                 # Лимит вопросов
  question_interval: 5.0             # Пауза между вопросами (сек)
  restart_delay: 0                   # 0 = без перезапуска
  proxy: None                        # Или "login:pass@ip:port"
  schedule:
    start_immediately: true
    start_times: ["00:00", "06:00", "12:00", "18:00"]
```

**Конфиги сайтов** лежат в `deploy/` и подмаунчиваются в `/home/site_configs/`:
- `config_site_qwen.yaml` → `/home/site_configs/config_site_qwen.yaml`
- `config_site_gpt.yaml` → `/home/site_configs/config_site_gpt.yaml`

Каждый конфиг сайта содержит:
```yaml
site:
  name: qwen
  url: https://chat.qwen.ai/
  home:
    reset:
      sequence: [...]
  scenarios:
    web_search_no_think:
      start_state: start_question
      states: {...}

prompts:
  qwen:
    hypos_norm:
      gen:
        text: prompts/qwen/...
        json: prompts/qwen/...
```

Чтобы сменить сайт — измените `site:` в `config_bot_X.yaml` и подмаунтите нужный `config_site_*.yaml` в `docker-compose.yml`.

**Важно:** `browser_master_profile` должен указывать на директорию, которая
замаплена через volume в `docker-compose.yml`:
```yaml
volumes:
  - ./profiles/bot_0:/home/profiles/bot_0
```

Перед первым запуском поместите профиль Chrome в `profiles/bot_0/`.

### 3. Сборка

```bash
docker-compose build
```

### 4. Запуск

```bash
# Запуск одного бота
docker-compose up -d bot_0

# Запуск всех ботов
docker-compose up -d

# Запуск конкретных ботов
docker-compose up -d bot_0 bot_1 bot_2
```

### 5. Мониторинг

**noVNC (браузер):**
- Bot 0: http://localhost:6970
- Bot 1: http://localhost:6971
- Bot 2: http://localhost:6972
- ...

**VNC (клиент):**
- Bot 0: localhost:5970
- Bot 1: localhost:5971
- ...

**Логи:**
```bash
docker logs -f clicker_bot_0
docker exec -it clicker_bot_0 tail -f /var/log/supervisor/*.log
```

### 6. Остановка

```bash
docker-compose stop bot_0        # Остановить одного бота
docker-compose down              # Остановить всех
```

## Как это работает

### Образ

Базовый образ `dorowu/ubuntu-desktop-lxde-vnc:latest` предоставляет:
- **Xvfb** — виртуальный framebuffer на `:1`
- **LXDE** — лёгкий оконный менеджер
- **x11vnc** — VNC-сервер на порту 5900
- **noVNC** — веб-доступ через nginx на порту 80

Наш Dockerfile добавляет:
- `xdotool`, `xclip`, `procps` — системные утилиты
- Python 3 + зависимости
- Скрипты `bot_runner.py`, `scripts/`

### Запуск бота

1. `bot_runner.py` читает `config_bot.yaml` из `/home/config/`
2. Из конфига бота берёт `site: qwen` и загружает `config_site_qwen.yaml` из `/home/site_configs/`
3. Создаёт `VirtualBotEnv` — загрузка вопросов, промптов (из site-конфига)
4. Запускает Chrome через `subprocess.Popen` с `DISPLAY=:1`
5. Запускает FSM в главном цикле: скриншот → match template → action → transition

### Ключевые отличия от dev-версии

| Dev-версия | Docker-версия |
|------------|---------------|
| `$DISPLAY = :100+bot_id` (Xvfb на каждого бота) | `$DISPLAY = :1` (Xvfb из образа, один на контейнер) |
| Запускает Xvfb, fluxbox, x11vnc | Всё уже запущено в базовом образе |
| Один процесс управляет всеми ботами | Один контейнер = один бот |
| `/usr/bin/chromium` | `google-chrome` (поиск через `find_chrome_binary()`) |
| Копирует master_profile → temp_profile | Использует профиль напрямую из volume |

### Разрешение

В `docker-compose.yml` установлено `RESOLUTION=1366x768`.
ROI бота `[0, 0, 960, 800]` помещается в это разрешение.

Если меняете ROI — убедитесь, что он помещается в разрешение контейнера.

## Ответы

JSON-файлы сохраняются в `answers/{model}/{project}/{subproject}/` внутри контейнера.
Через volume `./answers:/home/answers` они доступны на хосте.

## Профили браузеров

Каждый бот использует свой профиль:
```
profiles/bot_0/  →  /home/profiles/bot_0  (в контейнере)
profiles/bot_1/  →  /home/profiles/bot_1
...
```

Перед первым запуском скопируйте туда готовый Chrome-профиль
(директорию с `Default/`, `Local State`, и т.д.).

## Troubleshooting

### Chrome не запускается
```bash
docker exec -it clicker_bot_0 bash
echo $DISPLAY           # Должно быть :1
which google-chrome     # Должно найти бинарник
google-chrome --version # Проверить версию
```

### Скриншот не работает
```bash
docker exec -it clicker_bot_0 bash
DISPLAY=:1 import -window root /tmp/test.png  # Проверка X11
```

### xdotool не кликает
```bash
docker exec -it clicker_bot_0 bash
DISPLAY=:1 xdotool getactivewindow  # Проверить активное окно
DISPLAY=:1 xdotool mousemove 100 100  # Проверить движение мыши
```

### Бот завис в одном состоянии
Подключитесь через noVNC (http://localhost:6970) и посмотрите что происходит на экране.
