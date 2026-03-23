# Как работает запуск одного бота: Полное руководство

## Общая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    КОМАНДНАЯ СТРОКА                            │
│         python run_bot.py 0                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  run_bot.py - Скрипт запуска отдельного бота                   │
│  1. Принимает bot_index из аргументов командной строки         │
│  2. Загружает config_main.yaml и config_bots.yaml              │
│  3. Вызывает run_bot(bot_index, cfg_main, cfg_bots, base_dir)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ЗАГРУЗКА КОНФИГУРАЦИИ                                         │
│                                                                 │
│  config_main.yaml:                                             │
│  - global: общие настройки (bots_count, screen_max_*)          │
│  - prompts: пути к промптам для каждой модели                  │
│  - sites: URL и сценарии для каждого сайта (gpt, gemini...)    │
│                                                                 │
│  config_bots.yaml:                                             │
│  - bot_0, bot_1, ... : индивидуальные настройки каждого бота   │
│    • browser_master_profile: профиль браузера                  │
│    • dataset_path: путь к CSV с вопросами                      │
│    • row_range: диапазон строк в CSV [start, end]              │
│    • question_interval: задержка между вопросами               │
│    • max_questions: лимит вопросов                             │
│    • restart_delay: задержка перед перезапуском                │
│    • proxy: настройки прокси [ip, port, login, password]       │
│    • schedule: расписание запуска                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  VirtualBotEnv(bot_id, bot_cfg) - Инициализация бота           │
│                                                                 │
│  1. Извлечение параметров из bot_cfg:                          │
│     - project = "hypos_norm"                                   │
│     - subproject = "gen"                                       │
│     - site = "qwen"                                            │
│     - model_name = "qwen"                                      │
│     - scenario = "web_search_no_think"                         │
│                                                                 │
│  2. Вычисление DISPLAY: :100 + bot_id                          │
│     - bot_0 → DISPLAY=:100                                     │
│     - bot_1 → DISPLAY=:101                                     │
│     - bot_5 → DISPLAY=:105                                     │
│                                                                 │
│  3. Создание временного профиля:                               │
│     /tmp/bot_hypos_norm_0                                       │
│                                                                 │
│  4. Загрузка вопросов из CSV:                                  │
│     - Чтение datasets/sp_depers_final_with_hypnorm_used_marks.csv
│     - Фильтрация по row_range [990, 999] для bot_0             │
│     - Получение 10 вопросов (строки 990-999)                   │
│                                                                 │
│  5. Поиск последнего верифицированного JSON:                   │
│     - Сканирование answers/qwen/hypos_norm/gen/                │
│     - Поиск файлов по паттерну: {idx}_{uid}_qwen.json          │
│     - Если найден файл для idx=995 → старт с 996               │
│                                                                 │
│  6. Настройка прокси (если есть):                              │
│     - Создание Chrome расширения для авто-аутентификации       │
│     - Замена LOGIN_PLACEHOLDER и PASSWORD_PLACEHOLDER          │
│                                                                 │
│  7. Расписание запуска:                                        │
│     - Парсинг start_times: ["00:00", "06:00", "12:00"...]      │
│     - Вычисление следующего времени запуска                    │
│                                                                 │
│  8. Загрузка промптов:                                         │
│     - Чтение prompts/qwen/hypos_norm/gen/hn_gen_qwen_text_latest
│     - Чтение prompts/qwen/hypos_norm/gen/hn_gen_qwen_json_latest
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ПРОВЕРКА ПЕРЕД ЗАПУСКОМ                                        │
│                                                                 │
│  1. Проверка stop_event:                                       │
│     - Если все вопросы верифицированы → выход                  │
│                                                                 │
│  2. Проверка расписания:                                       │
│     - Если start_immediately=false                             │
│     - Ожидание в цикле: while not bot.should_start_now()       │
│                                                                 │
│  3. Старт браузера:                                            │
│     bot.start(cfg_main['sites'][site_name]['url'])             │
│     - Запуск Xvfb на DISPLAY=:100                              │
│     - Запуск Chrome с профилем и прокси                        │
│     - Переход на URL (напр. https://chat.qwen.com/)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FSM(bot_id, cfg_main, bot_cfg) - Конечный автомат             │
│                                                                 │
│  1. Загрузка сценария из config_main.yaml:                     │
│     cfg_main['sites']['qwen']['scenarios']['web_search_no_think']
│                                                                 │
│  2. Начальное состояние:                                       │
│     current_state = "start_question"                           │
│                                                                 │
│  3. Структура сценария:                                        │
│     states:                                                    │
│       start_question:                                          │
│         expect: templates/chromium/qwen/plus.png               │
│         action: click                                          │
│         condition: templates/chromium/qwen/more.png            │
│         next:                                                  │
│           success: options_menu_opened                         │
│           fail: start_question                                 │
│         timeout: 120.0                                         │
│                                                                 │
│       options_menu_opened:                                     │
│         expect: templates/chromium/qwen/more.png               │
│         action: mousemove                                      │
│         ...                                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ОСНОВНОЙ ЦИКЛ (run_bot.py)                                    │
│                                                                 │
│  while True:                                                   │
│                                                                 │
│    1. Проверка завершения:                                     │
│       if bot.stop_event.is_set():                              │
│         - Если все вопросы отвечены → break                    │
│         - Если restart_delay > 0 → перезапуск                  │
│                                                                 │
│    2. Получение кадра:                                         │
│       frame = bot.get_frame_umat()                             │
│       - Скриншот через mss с DISPLAY=:100                      │
│       - Обрезка по ROI [0, 0, 960, 800]                        │
│       - Преобразование в OpenCV UMat                           │
│                                                                 │
│    3. Выполнение шага FSM:                                     │
│       fsm.execute_step(bot, analyzer, frame)                   │
│                                                                 │
│       a) Проверка таймаута текущего состояния                  │
│                                                                 │
│       b) Поиск шаблона (expect):                               │
│          - analyzer.find_best_match(frame, templates, threshold)
│          - Сопоставление с templates/chromium/qwen/*.png       │
│          - Возврат координат (x, y) или None                   │
│                                                                 │
│       c) Выполнение действия (action):                         │
│          - click: клик по координатам                          │
│          - mousemove: движение мыши                            │
│          - click_paste_enter:                                   │
│            * Ctrl+A → Delete (очистка поля)                    │
│            * Вставка отформатированного промпта                │
│            * Enter                                             │
│          - click_copy_save_json_check:                         │
│            * Клик по кнопке Copy                               │
│            * Чтение из буфера через xclip                      │
│            * Верификация JSON                                  │
│                                                                 │
│       d) Проверка условия (condition):                         │
│          - templates: поиск визуального триггера               │
│          - json_valid: верификация JSON из буфера              │
│                                                                 │
│       e) Переход в следующее состояние:                        │
│          - success → next['success']                           │
│          - fail → next['fail']                                 │
│                                                                 │
│    4. Пауза: time.sleep(0.1)                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ВЕРИФИКАЦИЯ JSON (критичный этап)                             │
│                                                                 │
│  Когда FSM достигает состояния с condition.json_valid=true:    │
│                                                                 │
│  1. Чтение из буфера обмена:                                   │
│     xclip -selection clipboard -o -display :100                │
│                                                                 │
│  2. Сохранение во временный файл:                              │
│     /tmp/bot_0_response.json                                   │
│                                                                 │
│  3. Верификация через scripts/verification_saved_json.py:      │
│     - Проверка валидности JSON                                 │
│     - Проверка структуры (наличие ключей)                      │
│     - Проверка содержимого (список Norms)                      │
│                                                                 │
│  4. Если JSON валиден:                                         │
│     - Сохранение в answers/qwen/hypos_norm/gen/{idx}_{uid}_qwen.json
│     - Увеличение cur_global_idx                                │
│     - Переход к следующему вопросу                             │
│     - Проверка question_interval (пауза между вопросами)       │
│                                                                 │
│  5. Если JSON невалиден:                                       │
│     - Попытка восстановления через json_repair                 │
│     - Если не помогло → повторная попытка на следующем цикле   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  ЗАВЕРШЕНИЕ РАБОТЫ БОТА                                        │
│                                                                 │
│  Условия остановки:                                            │
│  1. Все вопросы в row_range верифицированы                     │
│  2. Достигнут лимит max_questions                              │
│  3. Пользователь нажал Ctrl+C                                  │
│                                                                 │
│  При остановке:                                                │
│  1. bot.stop():                                               │
│     - Остановка Chrome процесса                                │
│     - Остановка Xvfb процесса                                  │
│     - Очистка временного профиля /tmp/bot_*                    │
│                                                                 │
│  2. vnc_monitor.stop():                                       │
│     - Остановка потока обновления VNC                          │
│                                                                 │
│  3. Если restart_delay > 0:                                   │
│     - Вычисление next_restart_time = now + restart_delay       │
│     - Создание нового VirtualBotEnv                            │
│     - Запуск с шага "Старт браузера"                           │
└─────────────────────────────────────────────────────────────────┘
```

## Детальный пример: Запуск bot_0

### 1. Конфигурация из config_bots.yaml

```yaml
bot_0:
  project: hypos_norm
  subproject: gen
  site: qwen
  mode: web_search_no_think
  model: qwen
  scenario: web_search_no_think
  browser_master_profile: ~/karvinoir@gmail.com
  dataset_path: datasets/sp_depers_final_with_hypnorm_used_marks.csv
  columns: [uid, query, used]
  roi: [0, 0, 960, 800]
  cooldown: 1.0
  question_interval: 5.0        # ← 5 секунд между вопросами
  row_range: [990, 999]         # ← 10 вопросов (строки 990-999)
  max_questions: 100
  restart_delay: 0
  proxy: None
  schedule:
    start_immediately: true
```

### 2. Команда запуска

```bash
python run_bot.py 0
```

### 3. Что происходит пошагово

```
[00:00:00] run_bot.py: Загрузка конфигов
[00:00:00] run_bot.py: Вызов run_bot(0, cfg_main, cfg_bots, base_dir)

[00:00:00] VirtualBotEnv.__init__:
           - bot_id = 0
           - DISPLAY = :100
           - temp_profile = /tmp/bot_hypos_norm_0
           - Загрузка CSV: строки 990-999 (10 вопросов)
           - Поиск JSON: найдено 0 файлов → старт с idx=990
           - Загрузка промптов из prompts/qwen/hypos_norm/gen/

[00:00:01] Проверка расписания: start_immediately=true → запуск сразу

[00:00:01] bot.start("https://chat.qwen.com/"):
           - Запуск Xvfb на :100
           - Запуск Chrome с профилем ~/.config/google-chrome-bot_0
           - Переход на https://chat.qwen.com/

[00:00:04] FSM.__init__:
           - Загрузка сценария web_search_no_think
           - current_state = "start_question"

[00:00:04] VNC Monitor: Активирован

[00:00:04] ОСНОВНОЙ ЦИКЛ:

  ЦИКЛ 1:
    - frame = скриншот с :100, обрезка [0:960, 0:800]
    - fsm.execute_step():
      * current_state = "start_question"
      * expect: templates/chromium/qwen/plus.png
      * find_best_match() → найдено! (x=100, y=200)
      * action: click → клик по (100, 200)
      * condition: templates/chromium/qwen/more.png
      * find_best_match() → найдено!
      * next: success → "options_menu_opened"
      * current_state = "options_menu_opened"

  ЦИКЛ 2:
    - frame = новый скриншот
    - fsm.execute_step():
      * current_state = "options_menu_opened"
      * expect: templates/chromium/qwen/more.png
      * найдено!
      * action: mousemove → наведение на кнопку
      * condition: templates/chromium/qwen/web_search.png
      * найдено!
      * next: success → "select_web_search"

  ... (несколько циклов позже)

  ЦИКЛ N: Вопрос задан, ждём ответ
    - current_state = "answer_processing"
    - expect: templates/chromium/qwen/voice_mode.png
    - action: mousemove
    - condition: templates/chromium/qwen/more.png
    - timeout: 400.0 секунд

  ЦИКЛ N+1: Копирование ответа
    - current_state = "end_of_answer"
    - expect: templates/chromium/qwen/copy.png
    - action: click_copy_save_json_check
    - condition: json_valid = true
    
    → Чтение из буфера: xclip -o -display :100
    → Сохранение: /tmp/bot_0_response.json
    → Верификация: check_valid_json(content, bot_id=0)
    → JSON валиден! Найден 21 норма
    
    → Сохранение: answers/qwen/hypos_norm/gen/990_{uid}_qwen.json
    → cur_global_idx = 991
    → Проверка question_interval: 5.0 сек
    → Ожидание 5 секунд перед следующим вопросом

  ЦИКЛ N+2: Следующий вопрос
    - current_state = "start_question"
    - Вопрос #991 из CSV
    - Форматирование промпта с новым query
    - ... (повтор цикла)

[00:05:00] Все 10 вопросов (990-999) верифицированы
           - bot.stop_event.set()
           - bot.all_questions_answered() → true

[00:05:00] Проверка restart_delay: 0 → перезапуск не требуется

[00:05:00] bot.stop():
           - kill Chrome процесса
           - kill Xvfb процесса
           - rm -rf /tmp/bot_hypos_norm_0

[00:05:00] vnc_monitor.stop()

[00:05:00] [+] Bot 0 stopped
[00:05:00] Выход из run_bot.py
```

## Взаимодействие файлов

```
┌────────────────────┐
│ config_main.yaml   │──────────────┐
│ - sites            │              │
│ - prompts          │              │
└────────────────────┘              │
                                    ▼
                           ┌─────────────────┐
                           │ run_bot.py      │
                           │ - main()        │
                           │ - run_bot()     │
                           └─────────────────┘
                                    │
                                    │ передаёт
                                    ▼
┌────────────────────┐     ┌─────────────────┐
│ config_bots.yaml   │────▶│ VirtualBotEnv   │
│ - bot_0            │     │ - __init__()    │
│ - bot_1            │     │ - start()       │
└────────────────────┘     └─────────────────┘
                                    │
                                    │ создаёт
                                    ▼
                           ┌─────────────────┐
                           │ FSM             │
                           │ - __init__()    │
                           │ - execute_step()│
                           └─────────────────┘
```

## Ключевые классы и их роль

| Класс | Файл | Ответственность |
|-------|------|----------------|
| `VirtualBotEnv` | `scripts/env_bot.py` | Управление браузером, загрузка вопросов, скриншоты |
| `FSM` | `scripts/bot_logic.py` | Конечный автомат: состояния, действия, переходы |
| `GPUAnalyzer` | `scripts/gpu_analyzer.py` | Поиск шаблонов на скриншоте (template matching) |
| `VNCHealthMonitor` | `scripts/vnc_monitor.py` | Мониторинг здоровья Xvfb, авто-перезапуск |
| `BotLogger` | `scripts/bot_logger.py` | Логирование событий в CSV |
| `StateLogger` | `scripts/state_logger.py` | Детальное логирование состояний FSM |

## Примеры команд

```bash
# Запустить bot_0 (qwen, вопросы 990-999)
python run_bot.py 0

# Запустить bot_3 (qwen, вопросы 939-949)
python run_bot.py 3

# Запустить bot_6 (gpt, вопросы 1321-1449)
python run_bot.py 6

# Запустить bot_3_ (claude, вопросы 950-1199)
# Примечание: bot_3_ имеет индекс с подчёркиванием, 
# нужно временно переименовать в config_bots.yaml
python run_bot.py 3  # если переименовать bot_3_ → bot_3
```

## Отладка

### Логи бота

```bash
# Логи в реальном времени
tail -f logs/bot_0/*.log

# Последние 100 строк
tail -n 100 logs/bot_0/*.log
```

### Скриншоты

```bash
# Просмотр шаблонов
ls templates/chromium/qwen/

# Просмотр сохранённых JSON
ls answers/qwen/hypos_norm/gen/
```

### Проверка процессов

```bash
# Процессы Chrome
ps aux | grep chrome

# Процессы Xvfb
ps aux | grep Xvfb

# DISPLAY переменные
echo $DISPLAY  # должно быть :100 для bot_0
```

### Остановка бота

```bash
# Ctrl+C в терминале

# Или найти и kill процесс
ps aux | grep "run_bot.py 0"
kill <PID>
```
