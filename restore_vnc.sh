#!/bin/bash
# Скрипт аварийного восстановления VNC для бота

BOT_ID=$1

if [ -z "$BOT_ID" ]; then
    echo "Использование: $0 <bot_id>"
    echo "Пример: $0 1"
    exit 1
fi

DISPLAY_NUM=$((100 + BOT_ID))
VNC_PORT=$((5900 + BOT_ID))

echo "[*] Восстановление VNC для бота $BOT_ID (DISPLAY=:$DISPLAY_NUM, PORT=$VNC_PORT)"

# Шаг 1: Находим и убиваем все процессы x11vnc для этого дисплея
echo "[*] Остановка старых процессов x11vnc..."
pkill -9 -f "x11vnc.*-display.*:$DISPLAY_NUM" 2>/dev/null || true

# Шаг 2: Ждём освобождения порта
echo "[*] Ожидание освобождения порта $VNC_PORT..."
sleep 2

# Шаг 3: Проверяем, работает ли ещё Xvfb
echo "[*] Проверка Xvfb..."
if pgrep -f "Xvfb.*:$DISPLAY_NUM" > /dev/null; then
    echo "[+] Xvfb работает на :$DISPLAY_NUM"
else
    echo "[!] Xvfb не работает! Требуется полный перезапуск бота."
    echo "    Запустите: python3 run_bot.py $BOT_ID"
    exit 1
fi

# Шаг 4: Запускаем новый x11vnc
echo "[*] Запуск x11vnc..."
export DISPLAY=":$DISPLAY_NUM"

x11vnc -display ":$DISPLAY_NUM" \
       -rfbport "$VNC_PORT" \
       -nopw \
       -forever \
       -shared \
       -nowf \
       -noxdamage \
       -repeat \
       -q \
       > /tmp/bot_${BOT_ID}_x11vnc_restored.log 2>&1 &

X11VNC_PID=$!

# Шаг 5: Проверяем, что запустился
sleep 2

if ps -p $X11VNC_PID > /dev/null; then
    echo "[+] x11vnc запущен (PID=$X11VNC_PID)"
    
    # Проверяем порт
    if ss -tlnp | grep -q "$VNC_PORT"; then
        echo "[+] VNC порт $VNC_PORT слушается"
        echo ""
        echo "[+] Восстановление завершено!"
        echo "    Подключайтесь через Remmina: localhost:$VNC_PORT"
    else
        echo "[!] Порт не слушается. Проверьте лог: /tmp/bot_${BOT_ID}_x11vnc_restored.log"
        exit 1
    fi
else
    echo "[!] x11vnc не запустился. Проверьте лог: /tmp/bot_${BOT_ID}_x11vnc_restored.log"
    exit 1
fi
