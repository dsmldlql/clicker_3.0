#!/usr/bin/env python3
"""
bot_runner.py — Single-bot entry point for Docker.
Один контейнер = один бот. Читает конфиг бота и динамически
загружает config_site_{site}.yaml с url, сценариями и промптами.
"""

import time, yaml, os, sys
from typing import Dict, Any
from scripts.env_bot import VirtualBotEnv
from scripts.gpu_analyzer import GPUAnalyzer
from scripts.bot_logic import FSM


def load_yaml(path: str) -> Dict[str, Any]:
  with open(path, "r", encoding="utf-8") as f:
    return yaml.safe_load(f)


def find_base_dir():
  """Определяет базовую директорию проекта.
  В Docker: /home/ (там templates/, prompts/, datasets/, answers/)
  """
  candidates = [
    "/home",                          # Docker
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # рядом с scripts/
    os.getcwd(),
  ]
  for candidate in candidates:
    if os.path.isdir(os.path.join(candidate, "templates")):
      return candidate
  # Фоллбэк: родительская директория от текущего файла
  return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_config_dir():
  """Ищем директорию с конфигами: ./config_bot.yaml или /home/config/config_bot.yaml"""
  # 1. /home/config (стандартный путь в Docker-контейнере)
  for ext in ("yaml", "yml"):
    p = f"/home/config/config_bot.{ext}"
    if os.path.exists(p):
      return "/home/config"
  # 2. Текущая рабочая директория
  for ext in ("yaml", "yml"):
    p = os.path.join(os.getcwd(), f"config_bot.{ext}")
    if os.path.exists(p):
      return os.getcwd()
  # 3. Директория скрипта
  script_dir = os.path.dirname(os.path.abspath(__file__))
  for ext in ("yaml", "yml"):
    p = os.path.join(script_dir, f"config_bot.{ext}")
    if os.path.exists(p):
      return script_dir
  # 4. Родительская директория
  parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  for ext in ("yaml", "yml"):
    p = os.path.join(parent, f"config_bot.{ext}")
    if os.path.exists(p):
      return parent
  raise FileNotFoundError(
    "config_bot.yaml/yml not found. "
    "Place it in: /home/config/, current dir, script dir, or project root."
  )


def find_site_config(site_name: str):
  """Ищем конфиг сайта: config_site_{site}.yaml или /home/site_configs/config_site_{site}.yaml"""
  filename = f"config_site_{site_name}"
  candidates = [
    ("/home/site_configs", ""),              # Docker — отдельная директория
    ("/home/config", ""),                     # Docker — рядом с config_bot
    (os.getcwd(), ""),                        # Текущая директория
    (os.path.dirname(os.path.abspath(__file__)), ""),  # Директория скрипта
    (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ""),  # Родительская
  ]
  for search_dir, _ in candidates:
    for ext in ("yaml", "yml"):
      p = os.path.join(search_dir, f"{filename}.{ext}")
      if os.path.exists(p):
        return p
  raise FileNotFoundError(
    f"{filename}.yaml/yml not found. "
    f"Place it in: /home/site_configs/, /home/config/, current dir, or project root."
  )


def main():
  config_dir = find_config_dir()
  base_dir = find_base_dir()
  print(f"[*] Config directory: {config_dir}")
  print(f"[*] Base directory: {base_dir}")

  # Пути к конфигам
  for ext in ("yaml", "yml"):
    bot_cfg_path = os.path.join(config_dir, f"config_bot.{ext}")
    if os.path.exists(bot_cfg_path):
      break
  else:
    print("Error: config_bot.yaml/yml not found")
    sys.exit(1)

  try:
    cfg_bots = load_yaml(bot_cfg_path)
  except Exception as e:
    print(f"Error loading bot config: {e}")
    sys.exit(1)

  # В config_bot.yaml один бот под ключом "bot" или "bot_0"
  if 'bot' in cfg_bots:
    bot_cfg = cfg_bots['bot']
  elif 'bot_0' in cfg_bots:
    bot_cfg = cfg_bots['bot_0']
  else:
    bot_cfg = list(cfg_bots.values())[0]

  site_name = bot_cfg.get('site', 'qwen')

  # Динамически загружаем конфиг сайта
  try:
    site_config_path = find_site_config(site_name)
    site_cfg = load_yaml(site_config_path)
    print(f"[*] Site config loaded: {site_config_path}")
  except FileNotFoundError as e:
    print(f"Error: {e}")
    sys.exit(1)

  bot_id = 0

  # Устанавливаем base_dir для разрешения относительных путей (templates, prompts, datasets)
  bot_cfg['base_dir'] = base_dir
  bot_cfg['site_config_path'] = site_config_path

  print(f"[*] Bot config: site={site_name} / scenario={bot_cfg.get('scenario')}")
  print(f"[*] DISPLAY: {os.environ.get('DISPLAY', ':1')}")
  print(f"[*] Questions: {bot_cfg.get('row_range')}")
  print(f"[*] Max questions: {bot_cfg.get('max_questions', 100)}")

  analyzer = GPUAnalyzer(base_dir=base_dir)

  bot = VirtualBotEnv(bot_id, bot_cfg)

  if bot.stop_event.is_set():
    print("[+] All questions already answered. Exiting.")
    sys.exit(0)

  # Если есть расписание и не start_immediately — ждём
  if bot.next_scheduled_time and not bot.schedule_start_immediately:
    print(f"[*] Waiting for scheduled start at {bot.next_scheduled_time.strftime('%H:%M:%S')}")
    while not bot.should_start_now():
      time.sleep(5)

  # Запускаем браузер
  site_url = site_cfg['site']['url']
  bot.start(site_url)
  print(f"[*] Browser started, waiting for page load...")
  time.sleep(5)

  # Создаём FSM
  fsm = FSM(bot_id, site_cfg, bot_cfg)

  # Главный цикл
  print(f"[*] Main loop started")
  bot_stop_time = None
  bot_restart_pending = False

  try:
    while True:
      current_time = time.time()

      # Проверка перезапуска бота
      if bot.stop_event.is_set():
        if bot.all_questions_answered():
          print("[+] All questions answered. Stopping.")
          bot.stop()
          break

        restart_delay = bot_cfg.get('restart_delay', 0)
        if restart_delay <= 0:
          print("[+] Bot stopped, no restart configured.")
          break

        if bot.next_restart_time and current_time >= bot.next_restart_time.timestamp():
          print(f"[*] Restarting bot (delay={restart_delay}s passed)...")
          bot.stop()
          time.sleep(2)

          new_bot = VirtualBotEnv(bot_id, bot_cfg)
          if new_bot.all_questions_answered():
            print("[+] All questions answered. No restart needed.")
            new_bot.stop()
            break

          new_bot.start(site_url)
          bot = new_bot
          fsm = FSM(bot_id, cfg_main, bot_cfg)
          bot_stop_time = None
          print("[+] Bot restarted")
        elif bot.next_restart_time and not bot_restart_pending:
          bot_restart_pending = True
          restart_in = int(bot.next_restart_time.timestamp() - current_time)
          print(f"[*] Bot stopped. Restart in {restart_in}s")

      # Проверка интервала между вопросами
      if hasattr(bot, 'waiting_for_interval') and bot.waiting_for_interval:
        if hasattr(bot, 'interval_resume_time') and current_time >= bot.interval_resume_time:
          print("[+] Question interval elapsed, resuming...")
          bot.waiting_for_interval = False
          bot.interval_resume_time = None
          fsm.reset_scenario(bot)
          if hasattr(bot, 'action_queue'):
            bot.action_queue.join()
        else:
          # Ждём, не обрабатываем кадры
          time.sleep(0.5)
          continue

      # Обработка кадра
      frame = bot.get_frame_umat()
      if frame is not None:
        fsm.execute_step(bot, analyzer, frame)

      time.sleep(0.1)

  except KeyboardInterrupt:
    print("\n[*] Shutting down...")
    bot.stop()

  print("[+] Bot runner stopped.")


if __name__ == "__main__":
  main()
