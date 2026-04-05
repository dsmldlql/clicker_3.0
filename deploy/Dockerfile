FROM dorowu/ubuntu-desktop-lxde-vnc:latest

# Устанавливаем необходимые пакеты и обновляем Chrome до последней версии
RUN apt-get update --allow-releaseinfo-change || true && \
    apt-get install -y --allow-unauthenticated \
      xdotool \
      xclip \
      procps \
      python3 \
      python3-pip \
      wget && \
    # Скачиваем и устанавливаем последнюю версию Google Chrome
    wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i /tmp/google-chrome.deb || apt-get install -f -y --allow-unauthenticated && \
    rm -f /tmp/google-chrome.deb && \
    pip3 install --no-cache-dir \
      numpy \
      opencv-python \
      mss \
      pandas \
      PyYAML \
      json_repair && \
    rm -rf /var/lib/apt/lists/*

# Копируем код
COPY scripts/ /home/scripts/
COPY bot_runner.py /home/scripts/
COPY config_bot.yaml /home/config/

# Создаём директорию для конфига сайта (подмаунчивается через volume)
RUN mkdir -p /home/site_configs

# Создаём директории для ответов и временных файлов
RUN mkdir -p /home/answers /home/datasets /home/prompts /home/templates

WORKDIR /home/scripts

# ENTRYPOINT запускает бота
# DISPLAY наследуется от базового образа (:1)
CMD ["python3", "/home/scripts/bot_runner.py"]
