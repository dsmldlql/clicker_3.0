import subprocess
import os
import time
import shutil
import threading
import json
import re
import numpy as np
import pandas as pd
import cv2
import mss
from queue import Queue
from datetime import datetime


class VNCRefreshThread(threading.Thread):
    """Thread for periodic VNC screen refresh."""
    def __init__(self, display, interval=2.0):
        super().__init__(daemon=True)
        self.display = display
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        while not self.stop_event.is_set():
            try:
                subprocess.run(
                    ["xdotool", "search", "--name", ".*"],
                    env=env, capture_output=True, timeout=1
                )
            except:
                pass
            time.sleep(self.interval)

    def stop(self):
        self.stop_event.set()


class VirtualBotEnv:
    def __init__(self, bot_id, bot_cfg, width=960, height=800):
        self.bot_id = bot_id
        self.project = bot_cfg.get('project', 'hypos_norm')
        self.subproject = bot_cfg.get('subproject', 'gen')
        self.site = bot_cfg.get('site', 'perplexity')
        self.mode = bot_cfg.get('mode', 'grok')
        self.model_name = bot_cfg.get('model', 'perplexity_grok')

        self.master_profile = os.path.expanduser(bot_cfg['browser_master_profile'])
        self.display = f":{100 + bot_id}"
        self.temp_profile = f"/tmp/bot_{self.project}_{self.bot_id}"

        self.roi = bot_cfg.get('roi', [0, 0, 960, 800])
        self.cooldown = bot_cfg.get('cooldown', 1.0)
        self.question_interval = bot_cfg.get('question_interval', 0.0)

        self.stop_event = threading.Event()
        self.action_queue = Queue()

        self.row_range = bot_cfg.get('row_range', [0, 1000000])
        self.max_questions = bot_cfg.get('max_questions', 100)
        restart_delay_val = bot_cfg.get('restart_delay', 0)
        self.restart_delay = int(restart_delay_val) if restart_delay_val not in (None, 'None', '') else 0

        self.last_start_time = None
        self.next_restart_time = None
        self.total_question_count = 0
        self.last_question_start_time = None
        self.waiting_for_interval = False
        self.interval_resume_time = None

        dataset_path = bot_cfg.get('dataset_path', 'datasets/sp_depers_final_with_hypnorm_used_marks.csv')
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.dataset_path = os.path.join(base_dir, dataset_path)
        self.df_cols = bot_cfg.get('columns', ['uid', 'query', 'used'])
        self.questions, self.cur_global_idx = self._load_questions()

        last_verified_idx = self._get_last_verified_question_index()
        if last_verified_idx is not None and self.questions is not None:
            start_row, end_row = self.row_range
            next_idx = last_verified_idx + 1
            if next_idx <= end_row:
                self.cur_global_idx = next_idx
            else:
                self.stop_event.set()

        self.schedule_start_immediately = bot_cfg.get('schedule', {}).get('start_immediately', False)
        self.schedule_times = self._parse_schedule_times(
            bot_cfg.get('schedule', {}).get('start_times', [])
        )
        self.next_scheduled_time = self._get_next_scheduled_time()

        self.prompt_text = None
        self.prompt_json = None
        self._load_prompts(base_dir, bot_cfg)

        self.width = self.roi[2]
        self.height = self.roi[3]
        self.size = f"{self.width}x{self.height}x24"

        self.proxy, self.proxy_auth = self._parse_proxy(bot_cfg.get('proxy'))
        self.proxy_login, self.proxy_password = self._extract_proxy_credentials(
            bot_cfg.get('proxy')
        )
        self.procs = {}

    def _parse_proxy(self, proxy_cfg):
        if proxy_cfg is None:
            return None, None
        if isinstance(proxy_cfg, str):
            if proxy_cfg.lower() in ('none', 'false', ''):
                return None, None
            if '@' in proxy_cfg:
                return f'http://{proxy_cfg}', None
            if ':' in proxy_cfg:
                return f'http://{proxy_cfg}', None
        if isinstance(proxy_cfg, list) and len(proxy_cfg) >= 2:
            ip, port = proxy_cfg[0], proxy_cfg[1]
            if len(proxy_cfg) >= 4:
                login, password = proxy_cfg[2], proxy_cfg[3]
                return f'http://{login}:{password}@{ip}:{port}', None
            return f'http://{ip}:{port}', None
        return None, None

    def _extract_proxy_credentials(self, proxy_cfg):
        if proxy_cfg is None:
            return None, None
        if isinstance(proxy_cfg, str) and '@' in proxy_cfg:
            auth_part = proxy_cfg.rsplit('@', 1)[0]
            if ':' in auth_part:
                login, password = auth_part.split(':', 1)
                return login, password
        if isinstance(proxy_cfg, list) and len(proxy_cfg) >= 4:
            return proxy_cfg[2], proxy_cfg[3]
        return None, None

    def _parse_schedule_times(self, time_strings):
        parsed = []
        for time_str in time_strings:
            try:
                time_str = time_str.strip()
                if ':' not in time_str:
                    continue
                parts = time_str.split(':')
                hour = int(parts[0])
                minute = int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    parsed.append((hour, minute))
            except:
                pass
        return parsed

    def _get_next_scheduled_time(self):
        if not self.schedule_times:
            return None
        now = datetime.now()
        next_time = None
        for hour, minute in self.schedule_times:
            scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled <= now:
                from datetime import timedelta
                scheduled += timedelta(days=1)
            if next_time is None or scheduled < next_time:
                next_time = scheduled
        return next_time

    def should_start_now(self):
        if self.schedule_start_immediately:
            self.schedule_start_immediately = False
            self.next_scheduled_time = self._get_next_scheduled_time()
            return True
        if not self.next_scheduled_time:
            return True
        now = datetime.now()
        time_diff = (self.next_scheduled_time - now).total_seconds()
        if 0 <= time_diff <= 60:
            self.next_scheduled_time = self._get_next_scheduled_time()
            return True
        return False

    def _load_prompts(self, base_dir, bot_cfg):
        try:
            cfg_main_path = os.path.join(base_dir, 'config_main.yaml')
            with open(cfg_main_path, 'r', encoding='utf-8') as f:
                import yaml
                cfg_main = yaml.safe_load(f)

            prompts_config = cfg_main.get('prompts', {})
            model_prompts = prompts_config.get(self.model_name, {})
            project_prompts = model_prompts.get(self.project, {})
            subproject_prompts = project_prompts.get(self.subproject, {})

            if not subproject_prompts:
                return

            text_path = subproject_prompts.get('text')
            if text_path:
                full_text_path = os.path.join(base_dir, text_path)
                if os.path.exists(full_text_path):
                    with open(full_text_path, 'r', encoding='utf-8') as f:
                        self.prompt_text = f.read()

            json_path = subproject_prompts.get('json')
            if json_path:
                full_json_path = os.path.join(base_dir, json_path)
                if os.path.exists(full_json_path):
                    with open(full_json_path, 'r', encoding='utf-8') as f:
                        self.prompt_json = f.read()
        except:
            pass

    def get_formatted_prompt(self):
        if self.prompt_text is None:
            return None
        question_row = self.get_cur_question()
        if question_row is None:
            return None
        situation = str(question_row.get('query', question_row.iloc[1] if len(question_row) > 1 else ''))
        json_template = self.prompt_json if self.prompt_json else '{}'
        formatted = self.prompt_text.replace('{situation}', situation).replace('{json}', json_template)
        return formatted + "\n\n" + formatted

    def _get_last_verified_question_index(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            answers_dir = os.path.join(base_dir, 'answers', self.model_name, self.project, self.subproject)
            if not os.path.exists(answers_dir):
                return None
            pattern = re.compile(r'^(\d+)_.*_' + re.escape(self.model_name) + r'\.json$')
            max_idx = None
            for filename in os.listdir(answers_dir):
                match = pattern.match(filename)
                if match:
                    idx = int(match.group(1))
                    start_row, end_row = self.row_range
                    if start_row <= idx <= end_row:
                        if max_idx is None or idx > max_idx:
                            max_idx = idx
            return max_idx
        except:
            return None

    def _load_questions(self):
        if not self.dataset_path or not os.path.exists(self.dataset_path):
            return None, None
        start_row, end_row = self.row_range
        try:
            pdf = pd.read_csv(
                self.dataset_path,
                usecols=self.df_cols,
                skiprows=range(1, start_row + 1),
                nrows=end_row - start_row + 1
            )
            pdf.index = pdf.index + start_row
            return pdf, start_row
        except:
            return None, None

    def get_cur_question(self):
        if self.questions is None:
            return None
        start_row, end_row = self.row_range
        if self.cur_global_idx < start_row or self.cur_global_idx > end_row:
            return None
        return self.questions.loc[self.cur_global_idx]

    def get_cur_question_uid(self):
        row = self.get_cur_question()
        if row is None:
            return None
        if 'uid' in row.index:
            return row['uid']
        return row.iloc[0]

    def save_verified_json(self, json_data: dict):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            save_dir = os.path.join(base_dir, 'answers', self.model_name, self.project, self.subproject)
            os.makedirs(save_dir, exist_ok=True)
            uid = self.get_cur_question_uid()
            if uid is None:
                return None
            global_idx = self.cur_global_idx
            filename = f"{global_idx}_{uid}_{self.model_name}.json"
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            return filepath
        except:
            return None

    def all_questions_answered(self):
        start_row, end_row = self.row_range
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        answers_dir = os.path.join(base_dir, 'answers', self.model_name, self.project, self.subproject)
        if not os.path.exists(answers_dir):
            return False
        pattern = re.compile(r'^(\d+)_.*_' + re.escape(self.model_name) + r'\.json$')
        answered_indices = set()
        for filename in os.listdir(answers_dir):
            match = pattern.match(filename)
            if match:
                idx = int(match.group(1))
                if start_row <= idx <= end_row:
                    answered_indices.add(idx)
        total_questions = end_row - start_row + 1
        return len(answered_indices) >= total_questions

    def advance_question(self):
        if self.questions is not None:
            start_row, end_row = self.row_range
            self.cur_global_idx += 1
            if self.cur_global_idx > end_row:
                self.stop_event.set()
                return False
            return True

    def increment_question_count(self):
        self.total_question_count += 1
        if self.total_question_count > self.max_questions:
            self.stop_event.set()
            return False
        return True

    def check_question_limit(self):
        if self.total_question_count >= self.max_questions:
            self.stop_event.set()
            return False
        return True

    def _clear_cache(self, profile_path):
        trash_dirs = [
            'Cache', 'Code Cache', 'GPUCache', 'ShaderCache',
            'GrShaderCache', 'Media Cache', 'WebSession'
        ]
        for root, dirs, files in os.walk(profile_path):
            for d in list(dirs):
                if d in trash_dirs:
                    try:
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    except:
                        pass

    def _prepare_profile(self):
        if os.path.exists(self.temp_profile):
            shutil.rmtree(self.temp_profile, ignore_errors=True)
        self._clear_cache(self.master_profile)
        shutil.copytree(self.master_profile, self.temp_profile)
        for lock in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
            lock_path = os.path.join(self.temp_profile, lock)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except:
                    pass

    def start(self, url):
        self._prepare_profile()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        try:
            result = subprocess.run(["pgrep", "-f", f"Xvfb {self.display}"], capture_output=True, text=True, timeout=1)
            if result.stdout.strip():
                old_pid = result.stdout.strip()
                subprocess.run(["kill", old_pid], capture_output=True)
                time.sleep(0.5)

            env = os.environ.copy()
            env["DISPLAY"] = self.display
            result = subprocess.run(["pgrep", "-f", "fluxbox"], capture_output=True, text=True, timeout=1)
            if result.stdout.strip():
                for pid in result.stdout.strip().split():
                    subprocess.run(["kill", pid], capture_output=True)
                time.sleep(0.5)

            vnc_port = 5900 + self.bot_id
            result = subprocess.run(["fuser", "-k", f"{vnc_port}/tcp"], capture_output=True, timeout=1)
            time.sleep(0.5)
        except:
            pass

        self.procs['xvfb'] = subprocess.Popen(
            ["Xvfb", self.display, "-screen", "0", self.size, "-ac"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        xvfb_started = False
        for _ in range(10):
            time.sleep(0.5)
            if self.procs['xvfb'].poll() is None:
                try:
                    result = subprocess.run(
                        ["xdpyinfo", "-display", self.display],
                        capture_output=True, timeout=1
                    )
                    if result.returncode == 0:
                        xvfb_started = True
                        break
                except:
                    pass
            else:
                break

        if not xvfb_started:
            return

        env = os.environ.copy()
        env["DISPLAY"] = self.display

        self.procs['wm'] = subprocess.Popen(
            ["fluxbox"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)

        vnc_port = 5900 + self.bot_id

        try:
            result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=1)
            if str(vnc_port) in result.stdout:
                subprocess.run(["fuser", "-k", f"{vnc_port}/tcp"], capture_output=True)
                time.sleep(1)
        except:
            pass

        max_attempts = 3
        for attempt in range(max_attempts):
            vnc_log = f"/tmp/bot_{self.bot_id}_x11vnc_attempt_{attempt}.log"
            self.procs['vnc'] = subprocess.Popen([
                "x11vnc",
                "-display", self.display,
                "-rfbport", str(vnc_port),
                "-nopw",
                "-forever",
                "-shared",
                "-nowf",
                "-noxdamage"
            ], stdout=open(vnc_log, 'w'), stderr=subprocess.STDOUT)

            time.sleep(2)
            if self.procs['vnc'].poll() is None:
                try:
                    result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=1)
                    if str(vnc_port) in result.stdout:
                        break
                except:
                    pass
                break
            else:
                if attempt < max_attempts - 1:
                    time.sleep(2)

        chrome_cmd = [
            "/usr/bin/chromium",
            f"--display={self.display}",
            f"--user-data-dir={self.temp_profile}",
            f"--window-position=0,0",
            f"--window-size=960,800",
            f"--force-device-scale-factor=1",
            "--remote-debugging-port=9222",
        ]

        if self.proxy:
            pure_proxy = self.proxy.split('://')[1].split('@')[1] if '://' in self.proxy else self.proxy.split('@')[1] if '@' in self.proxy else self.proxy
            chrome_cmd.append(f"--proxy-server={pure_proxy}")

        chrome_cmd.extend([
            "--no-sandbox",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--limit-fps=5",
            "--disable-blink-features=AutomationControlled",
            f"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            url
        ])

        self.procs['browser'] = subprocess.Popen(chrome_cmd, env=env)

        self.vnc_refresh = VNCRefreshThread(self.display, interval=2.0)
        self.vnc_refresh.start()

        self.last_start_time = datetime.now()
        if self.restart_delay > 0:
            from datetime import timedelta
            self.next_restart_time = self.last_start_time + timedelta(seconds=self.restart_delay)

        threading.Thread(target=self._executor, daemon=True).start()

    def get_frame_umat(self):
        os.environ["DISPLAY"] = self.display
        with mss.mss() as sct:
            try:
                sct_img = sct.grab(sct.monitors[1])
                img_umat = cv2.UMat(np.array(sct_img))
                gray = cv2.cvtColor(img_umat, cv2.COLOR_BGRA2GRAY)
                gray = cv2.Canny(gray, 50, 150)
                time.sleep(0.2)
                return gray
            except:
                return None

    def _executor(self):
        env = {"DISPLAY": self.display}
        action_count = 0
        last_display_check = time.time()

        while not self.stop_event.is_set():
            try:
                if time.time() - last_display_check > 30:
                    result = subprocess.run(
                        ["xdotool", "search", "--name", ".*"],
                        env=env, capture_output=True, text=True, timeout=2
                    )
                    if result.returncode != 0 and "Failed" in result.stderr:
                        pass
                    last_display_check = time.time()

                t_type, val = self.action_queue.get(timeout=1)
                action_count += 1

                if t_type is None or val is None:
                    continue

                if t_type == 'click':
                    if not isinstance(val, (list, tuple)) or len(val) != 2:
                        continue
                    subprocess.run(
                        ["xdotool", "mousemove", str(val[0]), str(val[1]), "click", "1"],
                        env=env, capture_output=True, text=True
                    )

                elif t_type == 'mousemove':
                    if not isinstance(val, (list, tuple)) or len(val) != 2:
                        continue
                    subprocess.run(
                        ["xdotool", "mousemove", str(val[0]), str(val[1])],
                        env=env, capture_output=True, text=True
                    )

                elif t_type == 'key':
                    key_name = 'Return' if val.lower() == 'enter' else val
                    subprocess.run(
                        ["xdotool", "key", "--clearmodifiers", key_name],
                        env=env, capture_output=True, text=True
                    )

                elif t_type == 'hotkey':
                    key_combo = "+".join(val)
                    subprocess.run(
                        ["xdotool", "key", "--clearmodifiers", key_combo],
                        env=env, capture_output=True, text=True
                    )

                elif t_type == 'type':
                    subprocess.run(
                        ["xdotool", "type", "--clearmodifiers", val],
                        env=env, capture_output=True, text=True
                    )

                self.action_queue.task_done()

            except queue.Empty:
                continue
            except:
                continue

    def clear_clipboard(self):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-display", self.display, "/dev/null"],
                stderr=subprocess.DEVNULL, timeout=1
            )
        except:
            pass

    def stop(self):
        self.stop_event.set()
        if hasattr(self, 'vnc_refresh'):
            self.vnc_refresh.stop()

        for proc_name, p in self.procs.items():
            if p:
                try:
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait(timeout=1)
                except:
                    pass

        time.sleep(1)
        try:
            result = subprocess.run(["pgrep", "-f", f"Xvfb {self.display}"], capture_output=True, text=True, timeout=1)
            if result.stdout.strip():
                for pid in result.stdout.strip().split():
                    subprocess.run(["kill", "-9", pid], capture_output=True)

            result = subprocess.run(["pgrep", "-f", "fluxbox"], capture_output=True, text=True, timeout=1)
            if result.stdout.strip():
                for pid in result.stdout.strip().split():
                    subprocess.run(["kill", "-9", pid], capture_output=True)

            vnc_port = 5900 + self.bot_id
            subprocess.run(["fuser", "-k", f"{vnc_port}/tcp"], capture_output=True, timeout=2)
        except:
            pass

        try:
            if os.path.exists(self.temp_profile):
                shutil.rmtree(self.temp_profile, ignore_errors=True)
        except:
            pass
