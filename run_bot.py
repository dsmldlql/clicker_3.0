import sys
import time
import yaml
import os
from typing import Dict, Any
import cv2
from scripts.env_bot import VirtualBotEnv
from scripts.gpu_analyzer import GPUAnalyzer
from scripts.bot_logic import FSM
from scripts.vnc_monitor import VNCHealthMonitor
from datetime import datetime


def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_bot(bot_index: int, cfg_main: Dict, cfg_bots: Dict, base_dir: str):
    """Launch a single bot by index."""
    bot_key = f'bot_{bot_index}'
    
    if bot_key not in cfg_bots:
        print(f"[!] Bot {bot_index} not found in config_bots.yaml")
        return
    
    bot_cfg = cfg_bots[bot_key]
    print(f"[*] Launching bot {bot_index} ({bot_key})...")
    
    # Initialize environment
    bot = VirtualBotEnv(bot_index, bot_cfg)
    
    # Check if all questions are already verified
    if bot.stop_event.is_set():
        print(f"[+] Bot {bot_index}: all questions verified. Bot not started.")
        return
    
    # Check schedule
    has_schedule = bool(bot.next_scheduled_time)
    start_immediately = bot.schedule_start_immediately
    
    if has_schedule and not start_immediately:
        print(f"[*] Bot {bot_index} waiting for scheduled start at {bot.next_scheduled_time.strftime('%H:%M:%S')}")
        # Wait until scheduled time
        while not bot.should_start_now():
            time.sleep(5)
        print(f"[*] Scheduled time reached for bot {bot_index}")
    
    # Start bot
    site_name = bot_cfg['site']
    bot.start(cfg_main['sites'][site_name]['url'])

    # Initialize FSM
    fsm = FSM(bot_index, cfg_main, bot_cfg)

    # Initialize VNC monitor (single bot mode)
    # Передаём bot_offset чтобы VNC Monitor проверял правильный дисплей
    vnc_monitor = VNCHealthMonitor(
        bot_count=bot_index + 1,
        check_interval=10.0,
        bot_offset=bot_index
    )
    vnc_monitor.start()
    print(f"[+] VNC Monitor: Activated (monitoring bot {bot_index} on :{100 + bot_index})")

    analyzer = GPUAnalyzer()
    
    try:
        while True:
            current_time = time.time()

            # Проверка ожидания интервала между вопросами
            # Обрабатываем waiting_for_interval для поддержки question_interval
            if hasattr(bot, 'waiting_for_interval') and bot.waiting_for_interval:
                if hasattr(bot, 'interval_resume_time') and current_time >= bot.interval_resume_time:
                    # Интервал истёк, возобновляем работу
                    print(f"[+] [Бот {bot_index}] Интервал истёк, возобновляем работу")
                    bot.waiting_for_interval = False
                    bot.interval_resume_time = None
                    bot.last_question_start_time = None
                    # Вызываем reset_scenario для перехода к следующему вопросу
                    fsm.reset_scenario(bot)
                    # Ждём завершения reset
                    time.sleep(2)
                else:
                    # Всё ещё ждём интервал
                    time.sleep(0.5)
                    continue

            # Check if bot completed all questions
            if bot.stop_event.is_set():
                # Check if restart is needed
                restart_delay = bot_cfg.get('restart_delay', 0)

                if bot.all_questions_answered():
                    print(f"[+] Bot {bot_index} completed all questions. Exiting.")
                    break

                if restart_delay and restart_delay not in (0, 'None', ''):
                    if bot.next_restart_time and current_time >= bot.next_restart_time.timestamp():
                        print(f"[*] Restarting bot {bot_index}...")
                        bot.stop()
                        time.sleep(2)

                        # Create new bot instance
                        bot = VirtualBotEnv(bot_index, bot_cfg)

                        if bot.all_questions_answered():
                            print(f"[+] Bot {bot_index}: all questions verified after restart.")
                            bot.stop()
                            break

                        site_name = bot_cfg['site']
                        bot.start(cfg_main['sites'][site_name]['url'])
                        fsm = FSM(bot_index, cfg_main, bot_cfg)
                        print(f"[+] Bot {bot_index} restarted")
                    else:
                        time.sleep(1)
                        continue
                else:
                    break

            # Get frame and execute step
            frame = bot.get_frame_umat()
            if frame is not None:
                fsm.execute_step(bot, analyzer, frame)

            time.sleep(2.0)  # Уменьшено с 1.0 до 0.5 для более быстрой реакции
    
    except KeyboardInterrupt:
        print(f"\n[*] Bot {bot_index}: Shutting down...")
    
    finally:
        vnc_monitor.stop()
        bot.stop()
        print(f"[+] Bot {bot_index} stopped")


def main():
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python3 run_bot.py <bot_index> [config_main.yaml] [config_bots.yaml]")
        print("  bot_index: Index of the bot to launch (e.g., 0, 1, 2, ...)")
        print("  config_main.yaml: Path to main config (default: config_main.yaml)")
        print("  config_bots.yaml: Path to bots config (default: config_bots.yaml)")
        print("\nExamples:")
        print("  .venv/bin/python3 run_bot.py 0")
        print("  .venv/bin/python3 run_bot.py 3 config_main.yaml config_bots.yaml")
        print("\nOr use shell scripts:")
        print("  ./run_bot_3.sh")
        sys.exit(1)
    
    bot_index = int(sys.argv[1])
    cfg_main_path = sys.argv[2] if len(sys.argv) > 2 else "config_main.yaml"
    cfg_bots_path = sys.argv[3] if len(sys.argv) > 3 else "config_bots.yaml"
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_main_path = os.path.join(base_dir, cfg_main_path) if not os.path.isabs(cfg_main_path) else cfg_main_path
    cfg_bots_path = os.path.join(base_dir, cfg_bots_path) if not os.path.isabs(cfg_bots_path) else cfg_bots_path
    
    try:
        cfg_main = load_config(cfg_main_path)
        cfg_bots = load_config(cfg_bots_path)
    except Exception as e:
        print(f"[!] Failed to load config: {e}")
        sys.exit(1)
    
    run_bot(bot_index, cfg_main, cfg_bots, base_dir)


if __name__ == "__main__":
    main()
