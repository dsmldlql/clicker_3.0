#!/bin/bash
# Тест автоматического восстановления VNC для бота 3

BOT_ID=3
DISPLAY_NUM=$((100 + BOT_ID))
VNC_PORT=$((5900 + BOT_ID))

echo "=== Тест автоматического восстановления VNC для бота $BOT_ID ==="
echo ""

# Шаг 1: Запускаем бота
echo "[1] Запуск бота $BOT_ID..."
cd /home/dmitrii/Documents/projects/clicker_3.0
nohup .venv/bin/python3 run_bot.py $BOT_ID > /tmp/bot${BOT_ID}_test.log 2>&1 &
BOT_PID=$!
echo "    PID бота: $BOT_PID"
echo ""

# Шаг 2: Ждём запуска
echo "[2] Ожидание запуска (15 секунд)..."
sleep 15

# Проверка что бот работает
if ! ps -p $BOT_PID > /dev/null 2>&1; then
    echo "[!] Бот не запустился! Проверьте лог: /tmp/bot${BOT_ID}_test.log"
    exit 1
fi

# Проверка что VNC работает
if ! ss -tlnp | grep -q $VNC_PORT; then
    echo "[!] VNC порт $VNC_PORT не слушается!"
    tail -50 /tmp/bot${BOT_ID}_test.log
    exit 1
fi

echo "[+] Бот запущен, VNC работает на порту $VNC_PORT"
echo ""

# Шаг 3: Показываем статус VNC Monitor
echo "[3] Статус VNC Monitor:"
grep -E "VNC Monitor" /tmp/bot${BOT_ID}_test.log | tail -5
echo ""

# Шаг 4: Убиваем VNC
echo "[4] Симуляция падения VNC (убиваем x11vnc)..."
pkill -9 -f "x11vnc.*:$DISPLAY_NUM"
echo "    x11vnc убит"
echo ""

# Проверка что порт освободился
sleep 2
if ss -tlnp | grep -q $VNC_PORT; then
    echo "[!] Порт всё ещё слушается (странно)"
else
    echo "[+] Порт $VNC_PORT освобождён"
fi
echo ""

# Шаг 5: Ожидаем восстановления
echo "[5] Ожидание автоматического восстановления (до 20 секунд)..."
for i in {1..20}; do
    if ss -tlnp | grep -q $VNC_PORT; then
        echo "[+] VNC восстановлен через $((i * 1)) секунд!"
        break
    fi
    sleep 1
done

# Шаг 6: Проверка результата
echo ""
echo "[6] Результат:"
if ss -tlnp | grep -q $VNC_PORT; then
    echo "[+] VNC успешно восстановлён!"
    echo "    Подключиться: vncviewer localhost:$VNC_PORT"
else
    echo "[!] VNC не восстановился автоматически"
    echo "    Проверьте лог VNC Monitor:"
    tail -30 /tmp/bot${BOT_ID}_x11vnc_monitor.log
fi
echo ""

# Шаг 7: Показываем логи восстановления
echo "[7] Логи восстановления:"
grep -E "VNC Monitor|перезапуск|restart" /tmp/bot${BOT_ID}_test.log | tail -10
echo ""

# Шаг 8: Остановка бота
echo "[8] Остановка бота..."
kill $BOT_PID
sleep 3

echo ""
echo "=== Тест завершён ==="
