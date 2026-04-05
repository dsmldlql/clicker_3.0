#!/bin/bash
# Копирует config_main.yaml, шаблоны, промпты и датасеты
# из dev-проекта в deploy-директорию для Docker-сборки

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

echo "[*] Подготовка deploy-директории для Docker..."

# config_main.yaml — общие настройки, промпты, сценарии
echo "[*] Копирование config_main.yaml..."
if [ -f "$PROJECT_DIR/config_main.yaml" ]; then
  cp "$PROJECT_DIR/config_main.yaml" "$DEPLOY_DIR/"
  echo "    OK"
else
  echo "    [!] config_main.yaml не найден в $PROJECT_DIR"
fi

# Шаблоны для GPU matching
echo "[*] Копирование шаблонов..."
if [ -d "$PROJECT_DIR/templates" ]; then
  mkdir -p "$DEPLOY_DIR/templates"
  rsync -a --exclude='*.png.bak' "$PROJECT_DIR/templates/" "$DEPLOY_DIR/templates/"
  count=$(find "$DEPLOY_DIR/templates" -name '*.png' | wc -l)
  echo "    OK: $count файлов"
else
  echo "    [!] Директория templates не найдена"
fi

# Промпты
echo "[*] Копирование промптов..."
if [ -d "$PROJECT_DIR/prompts" ]; then
  mkdir -p "$DEPLOY_DIR/prompts"
  rsync -a "$PROJECT_DIR/prompts/" "$DEPLOY_DIR/prompts/"
  count=$(find "$DEPLOY_DIR/prompts" -type f | wc -l)
  echo "    OK: $count файлов"
else
  echo "    [!] Директория prompts не найдена"
fi

# Датасеты
echo "[*] Копирование датасетов..."
if [ -d "$PROJECT_DIR/datasets" ]; then
  mkdir -p "$DEPLOY_DIR/datasets"
  rsync -a "$PROJECT_DIR/datasets/" "$DEPLOY_DIR/datasets/"
  count=$(find "$DEPLOY_DIR/datasets" -type f | wc -l)
  echo "    OK: $count файлов"
else
  echo "    [!] Директория datasets не найдена"
fi

# Копируем config_bots.yaml как reference (не используется в Docker напрямую)
if [ -f "$PROJECT_DIR/config_bots.yaml" ]; then
  echo "[*] Копирование config_bots.yaml (reference)..."
  cp "$PROJECT_DIR/config_bots.yaml" "$DEPLOY_DIR/config_bots_reference.yaml"
fi

# Создаём пустые директории для ответов и профилей
mkdir -p "$DEPLOY_DIR/answers"
mkdir -p "$DEPLOY_DIR/profiles/bot_0"
mkdir -p "$DEPLOY_DIR/profiles/bot_1"
mkdir -p "$DEPLOY_DIR/profiles/bot_2"
mkdir -p "$DEPLOY_DIR/profiles/bot_3"
mkdir -p "$DEPLOY_DIR/profiles/bot_4"
mkdir -p "$DEPLOY_DIR/profiles/bot_5"

# Генерируем конфиги для каждого бота из config_bots.yaml
if [ -f "$PROJECT_DIR/config_bots.yaml" ]; then
  echo "[*] Генерация config_bot_X.yaml из config_bots.yaml..."
  python3 -c "
import yaml, os, sys

src = '$PROJECT_DIR/config_bots.yaml'
out_dir = '$DEPLOY_DIR'

with open(src, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

for key, val in cfg.items():
    bot_num = key.replace('bot_', '')
    out_path = os.path.join(out_dir, f'config_bot_{bot_num}.yaml')
    with open(out_path, 'w', encoding='utf-8') as f:
        yaml.dump({key: val}, f, allow_unicode=True, default_flow_style=False)
    print(f'    Создан {os.path.basename(out_path)}')
" 2>/dev/null || echo "    [!] Не удалось сгенерировать конфиги (нет python3 или pyyaml)"
fi

echo ""
echo "[+] Deploy готов! Структура:"
echo ""
echo "  deploy/"
echo "  ├── bot_runner.py          # Entry point (один бот)"
echo "  ├── Dockerfile             # Образ на базе dorowu/ubuntu-desktop-lxde-vnc"
echo "  ├── docker-compose.yml     # Мульти-бот (6 контейнеров)"
echo "  ├── config_bot.yaml        # Шаблон конфига бота"
echo "  ├── config_bot_*.yaml      # Конфиги для каждого бота"
echo "  ├── config_main.yaml       # Общие настройки + сценарии"
echo "  ├── requirements.txt       # Python зависимости"
echo "  ├── scripts/               # Код (env_bot, bot_logic, gpu_analyzer)"
echo "  ├── templates/             # Шаблоны для GPU matching"
echo "  ├── prompts/               # Промпты"
echo "  ├── datasets/              # Датасеты с вопросами"
echo "  ├── answers/               # Результаты (JSON)"
echo "  └── profiles/              # Профили браузеров"
echo ""
echo "Следующие шаги:"
echo "  1. Отредактируйте config_bot_X.yaml для каждого бота"
echo "     (особенно browser_master_profile, row_range, proxy)"
echo "  2. docker-compose build"
echo "  3. docker-compose up -d bot_0  # или --scale bot_0=1"
echo "  4. VNC: localhost:5970, noVNC: http://localhost:6970"
