#!/bin/bash
# Тест question_interval для одиночного бота

BOT_ID=3
echo "=== Тест question_interval для бота $BOT_ID ==="
echo ""

# Запускаем бота
echo "[1] Запуск бота $BOT_ID..."
cd /home/dmitrii/Documents/projects/clicker_3.0
nohup .venv/bin/python3 run_bot.py $BOT_ID > /tmp/bot${BOT_ID}_interval_test.log 2>&1 &
BOT_PID=$!
echo "    PID: $BOT_PID"
echo ""

# Ждём 30 секунд
echo "[2] Ожидание работы бота (30 секунд)..."
sleep 30

# Проверяем логи
echo "[3] Проверка логов на наличие question_interval:"
echo ""
grep -E "Ожидание интервала|Интервал истёк|question_interval" /tmp/bot${BOT_ID}_interval_test.log | head -10

echo ""
echo "[4] Последние 20 строк лога:"
tail -20 /tmp/bot${BOT_ID}_interval_test.log

echo ""
echo "[5] Остановка бота..."
kill $BOT_PID 2>/dev/null
sleep 2

echo ""
echo "=== Тест завершён ==="
echo ""
echo "Полный лог: /tmp/bot${BOT_ID}_interval_test.log"
