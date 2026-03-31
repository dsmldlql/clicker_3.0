import time
import yaml
import os
from typing import Dict, List, Any
import cv2
from scripts.env_bot import VirtualBotEnv
from scripts.gpu_analyzer import GPUAnalyzer
from scripts.bot_logic import FSM
from scripts.vnc_monitor import VNCHealthMonitor


def load_config(path: str) -> Dict[str, Any]:
    """Load YAML config file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_main_path = os.path.join(base_dir, "config_main.yaml")
    cfg_bots_path = os.path.join(base_dir, "config_bots.yaml")

    cfg_main = load_config(cfg_main_path)
    cfg_bots = load_config(cfg_bots_path)

    bots_count = int(cfg_main.get("global", {}).get("bots_count", 0))

    analyzer = GPUAnalyzer()
    bots, logics = [], []
    bot_configs = []
    bot_stop_times = {}
    bot_scheduled = {}

    vnc_monitor = VNCHealthMonitor(bot_count=bots_count, check_interval=30.0)

    for i in range(bots_count):
        bot_key = f'bot_{i}'
        if bot_key not in cfg_bots:
            continue

        bot_cfg = cfg_bots[bot_key]
        bot_configs.append((i, bot_cfg))

        bot = VirtualBotEnv(i, bot_cfg)

        if bot.stop_event.is_set():
            bots.append(None)
            logics.append(None)
            continue

        has_schedule = bool(bot.next_scheduled_time)
        start_immediately = bot.schedule_start_immediately

        if has_schedule and not start_immediately:
            bot_scheduled[i] = True
            bots.append(bot)
            logics.append(None)
            continue

        site_name = bot_cfg['site']
        bot.start(cfg_main['sites'][site_name]['url'])
        bots.append(bot)
        logics.append(FSM(i, cfg_main, bot_cfg))

        time.sleep(3.0)

    vnc_monitor.start()

    try:
        while True:
            current_time = time.time()

            # Check Xvfb failures and restart bots
            for bot_idx in range(bots_count):
                bot = bots[bot_idx] if bot_idx < len(bots) else None
                if bot is None:
                    continue
                if vnc_monitor.is_xvfb_failed(bot_idx):
                    bot.stop()
                    time.sleep(2)
                    vnc_monitor.clear_xvfb_failed(bot_idx)

                    bot_cfg = bot_configs[bot_idx][1]
                    new_bot = VirtualBotEnv(bot_idx, bot_cfg)

                    if new_bot.all_questions_answered():
                        new_bot.stop()
                        bots[bot_idx] = None
                        logics[bot_idx] = None
                        continue

                    site_name = bot_cfg['site']
                    new_bot.start(cfg_main['sites'][site_name]['url'])
                    bots[bot_idx] = new_bot
                    logics[bot_idx] = FSM(bot_idx, cfg_main, bot_cfg)

                    if bot_idx in bot_stop_times:
                        del bot_stop_times[bot_idx]

            # Check scheduled bot launches
            for bot_idx, bot in enumerate(bots):
                if bot is None:
                    continue
                if bot_idx in bot_scheduled and bot_scheduled[bot_idx]:
                    if bot.should_start_now():
                        site_name = cfg_bots[f'bot_{bot_idx}']['site']
                        bot.start(cfg_main['sites'][site_name]['url'])
                        logics[bot_idx] = FSM(bot_idx, cfg_main, cfg_bots[f'bot_{bot_idx}'])
                        bot_scheduled[bot_idx] = False

            # Handle stopped bots (restart or complete)
            for bot_idx, (bot, fsm) in enumerate(zip(bots, logics)):
                if bot is None:
                    continue

                if bot.stop_event.is_set():
                    bot_cfg = bot_configs[bot_idx][1]
                    restart_delay = bot_cfg.get('restart_delay', 0)

                    if bot.all_questions_answered():
                        bot.stop()
                        time.sleep(1)
                        bots[bot_idx] = None
                        logics[bot_idx] = None
                        continue

                    if restart_delay <= 0:
                        continue

                    if bot.next_restart_time and current_time >= bot.next_restart_time.timestamp():
                        bot.stop()
                        time.sleep(2)

                        new_bot = VirtualBotEnv(bot_idx, bot_cfg)

                        if new_bot.all_questions_answered():
                            new_bot.stop()
                            time.sleep(1)
                            bots[bot_idx] = None
                            logics[bot_idx] = None
                            continue

                        site_name = bot_cfg['site']
                        new_bot.start(cfg_main['sites'][site_name]['url'])
                        bots[bot_idx] = new_bot
                        logics[bot_idx] = FSM(bot_idx, cfg_main, bot_cfg)

                        if bot_idx in bot_stop_times:
                            del bot_stop_times[bot_idx]

            # Check periodic restart for ACTIVE bots
            for bot_idx, (bot, fsm) in enumerate(zip(bots, logics)):
                if bot is None or bot.stop_event.is_set():
                    continue

                bot_cfg = bot_configs[bot_idx][1]
                restart_delay_val = bot_cfg.get('restart_delay', 0)
                restart_delay = int(restart_delay_val) if restart_delay_val not in (None, 'None', '') else 0

                if restart_delay > 0 and bot.next_restart_time and current_time >= bot.next_restart_time.timestamp():
                    bot.stop()
                    time.sleep(2)

                    new_bot = VirtualBotEnv(bot_idx, bot_cfg)

                    if new_bot.all_questions_answered():
                        new_bot.stop()
                        time.sleep(1)
                        bots[bot_idx] = None
                        logics[bot_idx] = None
                        continue

                    site_name = bot_cfg['site']
                    new_bot.start(cfg_main['sites'][site_name]['url'])
                    bots[bot_idx] = new_bot
                    logics[bot_idx] = FSM(bot_idx, cfg_main, bot_cfg)

                    if bot_idx in bot_stop_times:
                        del bot_stop_times[bot_idx]

            # Check bots waiting for question interval
            for bot_idx, (bot, fsm) in enumerate(zip(bots, logics)):
                if bot is None or fsm is None or bot.stop_event.is_set():
                    continue

                if hasattr(bot, 'waiting_for_interval') and bot.waiting_for_interval:
                    if hasattr(bot, 'interval_resume_time') and current_time >= bot.interval_resume_time:
                        bot.waiting_for_interval = False
                        bot.interval_resume_time = None
                        fsm.reset_scenario(bot)
                        if hasattr(bot, 'action_queue'):
                            bot.action_queue.join()

            # Filter active bots
            active_pairs = [(bot, fsm) for bot, fsm in zip(bots, logics)
                            if bot is not None and fsm is not None
                            and not bot.stop_event.is_set()
                            and not (hasattr(bot, 'waiting_for_interval') and bot.waiting_for_interval)]

            # Check if all bots are done
            all_bots_done = all(b is None for b in bots)
            if all_bots_done:
                for b in bots:
                    if b:
                        try:
                            b.stop()
                        except:
                            pass
                break

            if not active_pairs:
                time.sleep(1.0)
                continue

            # Process active pairs
            for bot, fsm in active_pairs:
                frame = bot.get_frame_umat()
                if frame is not None:
                    fsm.execute_step(bot, analyzer, frame)

            time.sleep(0.1)

    except KeyboardInterrupt:
        vnc_monitor.stop()
        for b in bots:
            if b:
                b.stop()


if __name__ == "__main__":
    main()
