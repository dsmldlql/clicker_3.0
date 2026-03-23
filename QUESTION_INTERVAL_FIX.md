# question_interval для одиночных ботов — Исправление

## ✅ Что было исправлено

Раньше `question_interval` **не работал** при запуске ботов через `run_bot.py` (одиночный запуск).

**Причина:** В `run_bot.py` не было обработки флага `waiting_for_interval`.

## 📝 Внесённые изменения

### 1. `run_bot.py`

Добавлена обработка `waiting_for_interval` в основной цикл:

```python
# Проверка ожидания интервала между вопросами
if hasattr(bot, 'waiting_for_interval') and bot.waiting_for_interval:
    if hasattr(bot, 'interval_resume_time') and current_time >= bot.interval_resume_time:
        # Интервал истёк, возобновляем работу
        bot.waiting_for_interval = False
        bot.interval_resume_time = None
        bot.last_question_start_time = None
        # Вызываем reset_scenario для перехода к следующему вопросу
        fsm.reset_scenario(bot)
        time.sleep(2)
    else:
        # Всё ещё ждём интервал
        time.sleep(0.5)
        continue
```

### 2. `scripts/bot_logic.py`

Исправлена логика установки флага `waiting_for_interval`:

**До:**
```python
# Устанавливаем флаг ожидания
bot.waiting_for_interval = True
# Сбрасываем таймер интервала
bot.last_question_start_time = None  # ← Проблема!
# Обновляем состояние, но не вызываем reset_scenario ещё
self.current_state = next_state
```

**После:**
```python
# Устанавливаем флаг ожидания
bot.waiting_for_interval = True
# НЕ сбрасываем last_question_start_time — он нужен для проверки
# НЕ обновляем состояние — оно обновится после reset_scenario
# Выходим без выполнения reset_scenario — он будет вызван после истечения интервала
return
```

## 🔄 Как работает теперь

### Полный цикл работы question_interval

```
1. Бот начинает задавать вопрос #1
   └─> last_question_start_time = 12:00:00
   └─> FSM: ask_empty → click_paste_enter

2. Бот получает ответ, верифицирует JSON
   └─> FSM: end_of_answer → start_question

3. Проверка интервала в bot_logic.py
   └─> time_since_last_question = 30 сек
   └─> question_interval = 60 сек
   └─> 30 < 60 → Интервал не прошёл!
   └─> interval_resume_time = 12:00:30 (текущее время + 30 сек)
   └─> waiting_for_interval = True
   └─> return (без reset_scenario)

4. run_bot.py: Основной цикл
   └─> waiting_for_interval = True
   └─> current_time = 12:00:15 (прошло 15 сек)
   └─> 12:00:15 < 12:00:30 → Всё ещё ждём
   └─> time.sleep(0.5)
   └─> continue

5. run_bot.py: Основной цикл (через 15 сек)
   └─> current_time = 12:00:30
   └─> 12:00:30 >= 12:00:30 → Интервал истёк!
   └─> waiting_for_interval = False
   └─> fsm.reset_scenario(bot)  # ← Вызов reset!
   └─> Ctrl+L → URL → Enter → Загрузка страницы

6. Бот готов к вопросу #2
   └─> FSM: start_question → expect: plus.png
```

## 📊 Временная шкала

**Конфиг:** `question_interval: 60.0`

```
Время    Событие
────────────────────────────────────────────────────────────
12:00:00 Бот начинает задавать вопрос #1
         └─> last_question_start_time = 12:00:00

12:00:25 Бот получает ответ на вопрос #1
         └─> Прошло 25 секунд
         └─> 25 < 60 → Интервал не прошёл!
         └─> interval_resume_time = 12:01:00 (ещё 35 сек ждать)
         └─> waiting_for_interval = True

12:00:30 run_bot.py: Проверка интервала
         └─> current_time = 12:00:30
         └─> 12:00:30 < 12:01:00 → Ждём ещё

12:00:45 run_bot.py: Проверка интервала
         └─> current_time = 12:00:45
         └─> 12:00:45 < 12:01:00 → Ждём ещё

12:01:00 run_bot.py: Проверка интервала
         └─> current_time = 12:01:00
         └─> 12:01:00 >= 12:01:00 → Интервал истёк!
         └─> fsm.reset_scenario(bot)
         └─> Бот начинает задавать вопрос #2
```

## 🧪 Тестирование

### Запуск теста

```bash
./test_question_interval.sh
```

### Что искать в логах

```bash
# Сообщения об ожидании интервала
grep "Ожидание интервала" /tmp/bot3_interval_test.log

# Пример вывода:
# [*] [Бот 3] Ожидание интервала между вопросами: 4.2с (интервал: 5.0с)
# [*] [Бот 3] Ожидание интервала между вопросами: 3.8с (интервал: 5.0с)

# Сообщения о возобновлении работы
grep "Интервал истёк" /tmp/bot3_interval_test.log

# Пример вывода:
# [+] [Бот 3] Интервал истёк, возобновляем работу
```

## 🔧 Настройка

### Изменение интервала

В `config_bots.yaml`:

```yaml
bot_3:
  project: hypos_norm
  site: qwen
  question_interval: 5.0  # ← Измените на нужное значение
  row_range: [939, 949]
```

### Рекомендуемые значения

| Модель | question_interval |
|--------|-------------------|
| Qwen | 5-10 сек |
| GPT | 45-60 сек |
| Claude | 120-150 сек |
| Gemini Thinking | 180-220 сек |

## 📈 Мониторинг

### Проверка работы

```bash
# Запустите бота
./run_bot_3.sh

# Наблюдайте за логами
tail -f /tmp/bot3_test.log | grep -E "Ожидание интервала|Интервал истёк"
```

### Ожидаемый вывод

```
[*] [Бот 3] Ожидание интервала между вопросами: 4.2с (интервал: 5.0с)
[+] [Бот 3] Интервал истёк, возобновляем работу
[*] [Бот 3] Переход в start_question - выполняем reset браузера
[*] [Бот 3] Ожидание интервала между вопросами: 3.8с (интервал: 5.0с)
[+] [Бот 3] Интервал истёк, возобновляем работу
```

## ⚠️ Важные замечания

### 1. Интервал отсчитывается от начала вопроса

```
Вопрос #1:  12:00:00 ──────> 12:00:30 (получен ответ)
                          ↓
                          Прошло 30 секунд

Если question_interval = 20:
  30 > 20 → Интервал прошёл автоматически!
  → Бот сразу начинает вопрос #2 (без ожидания)
```

### 2. question_interval = 0

```yaml
question_interval: 0  # или отсутствует
```

**Что происходит:**
- Проверка интервала пропускается
- Бот работает на максимальной скорости

### 3. Работа в main.py и run_bot.py

Теперь `question_interval` работает **одинаково** в обоих режимах:

- `main.py` — запуск всех ботов сразу
- `run_bot.py` — одиночный запуск бота

## 🐛 Отладка

### Бот не ждёт интервал

**Проверьте:**
```bash
grep "Ожидание интервала" /tmp/bot3_test.log
```

**Если нет сообщений:**
- Проверьте что `question_interval > 0` в конфиге
- Проверьте что `last_question_start_time` устанавливается

### Бот ждёт слишком долго

**Уменьшите интервал:**
```yaml
question_interval: 30.0  # Было 60.0
```

### Бот не ждёт вообще

**Проверьте логи:**
```bash
grep "last_question_start_time" /tmp/bot3_test.log
```

**Если не устанавливается:**
- Проверьте что действие `click_paste_enter` выполняется
- Проверьте что `bot.last_question_start_time = time.time()` вызывается

## 📚 Связанные файлы

- `run_bot.py` — основной цикл с обработкой интервала
- `scripts/bot_logic.py` — логика установки `waiting_for_interval`
- `scripts/env_bot.py` — инициализация `question_interval`
- `QUESTION_INTERVAL_EXPLAINED.md` — подробное объяснение
