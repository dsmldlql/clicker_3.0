import subprocess, os, time, shutil, threading, json, queue, re
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import cv2
import mss
from scripts.csv_logger import get_bot_csv_logger


def find_chrome_binary():
  """Поиск бинарника Chrome в Docker-образе."""
  candidates = [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/opt/google/chrome/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
  ]
  for path in candidates:
    if os.path.isfile(path) and os.access(path, os.X_OK):
      return path
  # Попытка найти через which
  try:
    result = subprocess.run(
      ["which", "google-chrome"], capture_output=True, text=True, timeout=2
    )
    if result.returncode == 0 and result.stdout.strip():
      return result.stdout.strip()
  except Exception:
    pass
  raise RuntimeError("Chrome binary not found. Install google-chrome or chromium.")


class VirtualBotEnv:
  def __init__(self, bot_id, bot_cfg):
    self.bot_id = bot_id
    self.project = bot_cfg.get('project', 'hypos_norm')
    self.subproject = bot_cfg.get('subproject', 'gen')
    self.site = bot_cfg.get('site', 'perplexity')
    self.model_name = bot_cfg.get('model', 'perplexity_grok')

    # В Docker DISPLAY устанавливается образом (:1)
    self.display = os.environ.get("DISPLAY", ":1")

    # Путь к профилю браузера. В Docker мапится через volume.
    # Если указан путь к мастер-профилю — используем его напрямую.
    master_path = bot_cfg.get('browser_master_profile', '')
    if master_path and master_path.lower() not in ('none', ''):
      self.profile_dir = os.path.expanduser(master_path)
    else:
      # Фоллбэк: профиль в /tmp
      self.profile_dir = f"/tmp/bot_{self.project}_{self.bot_id}_profile"

    self.roi = bot_cfg.get('roi', [0, 0, 960, 800])
    self.question_interval = bot_cfg.get('question_interval', 0.0)

    self.stop_event = threading.Event()
    self.action_queue = queue.Queue()

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
    # Базовая директория — директория bot_runner.py
    base_dir = bot_cfg.get('base_dir', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    self.dataset_path = os.path.join(base_dir, dataset_path)
    self.df_cols = bot_cfg.get('columns', ['uid', 'query', 'used'])
    self.questions, self.cur_global_idx = self._load_questions()

    # Возобновление с последнего верифицированного JSON
    last_verified_idx = self._get_last_verified_question_index()
    if last_verified_idx is not None and self.questions is not None:
      start_row, end_row = self.row_range
      next_idx = last_verified_idx + 1
      if next_idx <= end_row:
        self.cur_global_idx = next_idx
      else:
        self.stop_event.set()

    self.schedule_start_immediately = bot_cfg.get('schedule', {}).get('start_immediately', False)
    self.schedule_times = self._parse_schedule_times(bot_cfg.get('schedule', {}).get('start_times', []))
    self.next_scheduled_time = self._get_next_scheduled_time()

    self.prompt_text = None
    self.prompt_json = None
    self._load_prompts(base_dir, bot_cfg)

    self.width = self.roi[2]
    self.height = self.roi[3]

    self.proxy, self.proxy_auth = self._parse_proxy(bot_cfg.get('proxy'))
    self.proxy_login, self.proxy_password = self._extract_proxy_credentials(bot_cfg.get('proxy'))

    # CSV логгер
    self.log_dir = f"/home/logs/bot_{self.bot_id}"
    self.csv_logger = get_bot_csv_logger(self.bot_id, self.log_dir)

    self.chrome_path = find_chrome_binary()
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
      except Exception:
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
      site_config_path = bot_cfg.get('site_config_path')
      if not site_config_path or not os.path.exists(site_config_path):
        return
      with open(site_config_path, 'r', encoding='utf-8') as f:
        import yaml
        site_cfg = yaml.safe_load(f)
      prompts_config = site_cfg.get('prompts', {})
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
    except Exception as e:
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
    formatted = formatted + "\n\n" + formatted
    return formatted

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
    except Exception:
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
    except Exception:
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
    except Exception:
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
    answered_count = len(answered_indices)
    return answered_count >= total_questions

  def advance_question(self):
    if self.questions is not None:
      start_row, end_row = self.row_range
      self.cur_global_idx += 1
      if self.cur_global_idx > end_row:
        self.stop_event.set()
        return False
      # Лог QUESTION_ADVANCE
      uid = self.get_cur_question_uid()
      self.csv_logger.log("QUESTION_ADVANCE", global_index=self.cur_global_idx, question_uid=uid)
      return True

  def increment_question_count(self):
    self.total_question_count += 1
    if self.total_question_count > self.max_questions:
      self.stop_event.set()
      return False
    # Лог QUESTION в CSV — счётчик попыток увеличивается здесь
    uid = self.get_cur_question_uid()
    self.csv_logger.log("QUESTION", global_index=self.cur_global_idx, question_uid=uid)
    return True

  def check_question_limit(self):
    if self.total_question_count >= self.max_questions:
      self.stop_event.set()
      return False
    return True

  def start(self, url):
    """Запуск Chrome. В Docker X-сервер уже работает (Xvfb + LXDE из образа)."""
    # Лог START
    uid = self.get_cur_question_uid()
    self.csv_logger.log("START", global_index=self.cur_global_idx, question_uid=uid)

    # Убиваем старый Chrome этого бота
    try:
      result = subprocess.run(
        ["pgrep", "-f", f"chrome.*user-data-dir={self.profile_dir}"],
        capture_output=True, text=True, timeout=1
      )
      if result.stdout.strip():
        for pid in result.stdout.strip().split():
          subprocess.run(["kill", pid], capture_output=True)
        time.sleep(1)
    except Exception:
      pass

    # Очистка singleton-файлов профиля
    for lock in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
      lock_path = os.path.join(self.profile_dir, lock)
      if os.path.exists(lock_path):
        try:
          os.remove(lock_path)
        except Exception:
          pass

    env = os.environ.copy()
    env["DISPLAY"] = self.display

    chrome_cmd = [
      self.chrome_path,
      f"--user-data-dir={self.profile_dir}",
      f"--window-position=0,0",
      f"--window-size=960,800",
      f"--force-device-scale-factor=1",
      "--remote-debugging-port=9222",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--disable-dev-shm-usage",
      "--disable-blink-features=AutomationControlled",
      "--password-store=basic",
      "--disable-features=StoragePressure",
      "--window-workspace=0",
    ]

    if self.proxy:
      pure_proxy = self.proxy.split('://')[1].split('@')[1] if '://' in self.proxy else self.proxy.split('@')[1] if '@' in self.proxy else self.proxy
      chrome_cmd.append(f"--proxy-server={pure_proxy}")

    chrome_cmd.extend([
      url
    ])

    self.procs['browser'] = subprocess.Popen(chrome_cmd, env=env)
    threading.Thread(target=self._executor, daemon=True).start()

  def get_frame_umat(self):
    """Скриншот текущего экрана через mss (работает через DISPLAY)."""
    os.environ["DISPLAY"] = self.display
    with mss.mss() as sct:
      try:
        sct_img = sct.grab(sct.monitors[1])
        img_umat = cv2.UMat(np.array(sct_img))
        gray = cv2.cvtColor(img_umat, cv2.COLOR_BGRA2GRAY)
        gray = cv2.Canny(gray, 50, 150)
        time.sleep(0.2)
        return gray
      except Exception:
        return None

  def _executor(self):
    """Обработчик очереди действий (xdotool)."""
    env = {"DISPLAY": self.display}
    while not self.stop_event.is_set():
      try:
        t_type, val = self.action_queue.get(timeout=1)
        if t_type is None or val is None:
          continue

        if t_type == 'click':
          subprocess.run(
            ["xdotool", "mousemove", str(val[0]), str(val[1]), "click", "1"],
            env=env, capture_output=True, text=True
          )
        elif t_type == 'mousemove':
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
      except Exception:
        continue

  def clear_clipboard(self):
    """Очистка буфера обмена."""
    try:
      subprocess.run(
        ["xclip", "-selection", "clipboard", "-display", self.display, "/dev/null"],
        stderr=subprocess.DEVNULL,
        timeout=1
      )
    except Exception:
      pass

  def stop(self):
    """Остановка бота: завершение Chrome и очистка."""
    self.stop_event.set()

    # Лог STOP
    try:
      uid = self.get_cur_question_uid()
      self.csv_logger.log("STOP", global_index=self.cur_global_idx, question_uid=uid)
    except Exception:
      pass

    if 'browser' in self.procs and self.procs['browser']:
      try:
        self.procs['browser'].terminate()
        try:
          self.procs['browser'].wait(timeout=3)
        except subprocess.TimeoutExpired:
          self.procs['browser'].kill()
          self.procs['browser'].wait(timeout=1)
      except Exception:
        pass

    # Дополнительная зачистка — убиваем Chrome этого бота
    time.sleep(1)
    try:
      result = subprocess.run(
        ["pgrep", "-f", f"chrome.*user-data-dir={self.profile_dir}"],
        capture_output=True, text=True, timeout=1
      )
      if result.stdout.strip():
        for pid in result.stdout.strip().split():
          subprocess.run(["kill", "-9", pid], capture_output=True)
    except Exception:
      pass
