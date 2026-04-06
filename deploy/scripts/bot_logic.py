import time, json, subprocess, re, os
from typing import Tuple, Any, Dict
from scripts.csv_logger import get_bot_csv_logger
from scripts.state_logger import StateLogger


def check_valid_json(text: str, bot_id: int) -> Tuple[bool, Any]:
  """Минимальная верификация JSON через json_repair."""
  if not text:
    return False, None
  try:
    json.loads(text)
    data = json.loads(text)
    return True, data
  except Exception:
    try:
      from json_repair import repair_json
      repaired = repair_json(text)
      if repaired:
        data = json.loads(repaired)
        return True, data
    except Exception:
      pass
  return False, None


class FSM:
  def __init__(self, bot_id, site_cfg, bot_config):
    self.bot_id = bot_id
    self.site_cfg = site_cfg
    self.bot_config = bot_config

    site = bot_config['site']
    scenario_name = bot_config['scenario']
    # В site_cfg: site_cfg['site']['scenarios'][...] и site_cfg['site']['home']
    self.scenario = site_cfg['site']['scenarios'][scenario_name]
    self.site_config = site_cfg['site']
    self.current_state = self.scenario['start_state']
    self.expected_complete = False
    self.last_change = time.time()
    self.json_path = f"/tmp/bot_{bot_id}_response.json"
    self.question_interval = bot_config.get('question_interval', 0.0)

    # CSV логгер
    self.site = site
    self.scenario_name = scenario_name
    self.log_dir = f"/home/logs/bot_{bot_id}"
    self.csv_logger = get_bot_csv_logger(bot_id, self.log_dir)

    # State timeline логгер
    self.state_logger = StateLogger(bot_id, site, scenario_name, self.log_dir)

  def get_clipboard(self, display):
    try:
      cmd = ["xclip", "-selection", "clipboard", "-o", "-display", display]
      return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8').strip()
    except Exception:
      return ""

  def is_json_valid(self, text):
    if not text:
      return False
    try:
      start = text.find('{')
      end = text.rfind('}') + 1
      if start != -1 and end != 0:
        json.loads(text[start:end])
        return True
      return False
    except Exception:
      return False

  def verify_json_from_clipboard(self, display) -> Tuple[bool, Any]:
    try:
      cmd = ["xclip", "-selection", "clipboard", "-o", "-display", display]
      clipboard_content = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8').strip()
      if not clipboard_content:
        return False, None
      with open(self.json_path, 'w', encoding='utf-8') as f:
        f.write(clipboard_content)
      success, data = check_valid_json(clipboard_content, self.bot_id)
      if success:
        return True, data
      return False, None
    except Exception:
      return False, None

  def reset_scenario(self, bot):
    reset_config = self.site_config.get('home', {}).get('reset', {})
    sequence = reset_config.get('sequence', [])
    for step in sequence:
      step_type = step.get('type')
      if step_type == 'hotkey':
        keys = step.get('keys', [])
        bot.action_queue.put(('hotkey', keys))
        time.sleep(0.3)
      elif step_type == 'text':
        text = step.get('value', '')
        bot.action_queue.put(('type', text))
        wait_time = max(0.5, len(text) * 0.02)
        time.sleep(wait_time)
      elif step_type == 'key':
        key = step.get('key', '')
        bot.action_queue.put(('key', key))
        time.sleep(0.5)
      elif step_type == 'wait':
        seconds = step.get('seconds', 1.0)
        time.sleep(seconds)

    if hasattr(bot, 'action_queue'):
      bot.action_queue.join()
    time.sleep(2.0)
    self.current_state = self.scenario['start_state']
    self.last_change = time.time()

  def execute_step(self, bot, analyzer, frame):
    if self.current_state not in self.scenario.get('states', {}):
      self.current_state = self.scenario.get('start_state', 'start_question')
      self.last_change = time.time()
      self.expected_complete = False

    cur_state_config = self.scenario['states'][self.current_state]
    timeout = cur_state_config.get('timeout', 120)
    elapsed = time.time() - self.last_change

    if elapsed > timeout:
      fail_state = cur_state_config['next'].get('fail', self.scenario['start_state'])
      next_state = fail_state
      if next_state == 'start_question':
        self.reset_scenario(bot)
        return
      self.current_state = fail_state
      self.last_change = time.time()
      self.expected_complete = False
      if hasattr(self, '_paste_enter_executed'):
        del self._paste_enter_executed
      return

    if not self.expected_complete:
      use_click_region = cur_state_config.get('click_center')
      if use_click_region:
        import random
        cx, cy = cur_state_config['click_center']
        rx, ry = cur_state_config.get('click_radius', [20, 20])
        x = random.randint(cx - rx, cx + rx)
        y = random.randint(cy - ry, cy + ry)
        self.expected_complete = True
        self.last_change = time.time()
        if cur_state_config.get('condition', {}).get('json_valid'):
          bot.clear_clipboard()
        self._run_action(bot, cur_state_config['action'], (x, y))
      else:
        fresh_frame = bot.get_frame_umat()
        if fresh_frame is None:
          fresh_frame = frame
        expect_config = cur_state_config['expect']
        region = tuple(expect_config['region']) if 'region' in expect_config else None
        coords, _ = analyzer.find_best_match(
          fresh_frame,
          expect_config['templates'],
          expect_config['threshold'],
          region=region
        )
        if coords and not self.expected_complete:
          self.expected_complete = True
          self.last_change = time.time()
          if cur_state_config.get('condition', {}).get('json_valid'):
            bot.clear_clipboard()
          self._run_action(bot, cur_state_config['action'], coords)

    if self.expected_complete:
      action = cur_state_config.get('action', '')
      if action == 'click_paste_enter':
        time.sleep(2.0)
      else:
        time.sleep(0.3)

      success = False
      cond = cur_state_config.get('condition', {})

      if 'templates' in cond:
        cond_region = tuple(cond['region']) if 'region' in cond else None
        new_frame = bot.get_frame_umat()
        if new_frame is not None:
          hit, score = analyzer.find_best_match(
            new_frame,
            cond['templates'],
            cond.get('threshold', 0.8),
            region=cond_region
          )
          success = hit is not None
        else:
          success = False

      elif cond.get('json_valid'):
        success = False
        verified_data = None
        try:
          cmd = ["xclip", "-selection", "clipboard", "-o", "-display", bot.display]
          clipboard_content = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        except Exception:
          clipboard_content = ""

        if clipboard_content:
          success, verified_data = check_valid_json(clipboard_content, self.bot_id)

        uid = bot.get_cur_question_uid()
        global_idx = bot.cur_global_idx

        if success and verified_data:
          self.expected_complete = False
          bot.save_verified_json(verified_data)
          bot.clear_clipboard()

          # Лог JSON_VERIFIED + JSON_SAVED
          uid = bot.get_cur_question_uid()
          global_idx = bot.cur_global_idx
          self.csv_logger.log("JSON_VERIFIED", global_index=global_idx, question_uid=uid)
          self.csv_logger.log("JSON_SAVED", global_index=global_idx, question_uid=uid)

          advanced = bot.advance_question()
          if not advanced:
            return

          next_state_key = 'success'
          next_state = cur_state_config['next'].get(next_state_key, self.scenario['start_state'])

          if next_state == 'start_question':
            if self.question_interval > 0 and bot.last_question_start_time is not None:
              time_since_last_question = time.time() - bot.last_question_start_time
              if time_since_last_question < self.question_interval:
                bot.interval_resume_time = time.time() + (self.question_interval - time_since_last_question)
                bot.waiting_for_interval = True
                return
            bot.last_question_start_time = None
            self.reset_scenario(bot)
            return

          prev_state = self.current_state
          self.current_state = next_state
          self.last_change = time.time()
          self.expected_complete = False
          if hasattr(self, '_paste_enter_executed'):
            del self._paste_enter_executed
          return
        else:
          # Лог JSON_VERIFY_FAILED
          uid = bot.get_cur_question_uid()
          global_idx = bot.cur_global_idx
          self.csv_logger.log("JSON_VERIFY_FAILED", global_index=global_idx, question_uid=uid)

          if not bot.check_question_limit():
            return

          next_state_key = 'fail'
          next_state = cur_state_config['next'].get(next_state_key, self.scenario['start_state'])
          bot.clear_clipboard()

          if next_state == 'start_question':
            self.reset_scenario(bot)
            return

          prev_state = self.current_state
          self.current_state = next_state
          self.last_change = time.time()
          self.expected_complete = False
          if hasattr(self, '_paste_enter_executed'):
            del self._paste_enter_executed
          return
      else:
        success = True

      if self.expected_complete and time.time() - self.last_change > 2.0:
        next_state_key = 'success' if success else 'fail'
        next_state = cur_state_config['next'].get(next_state_key, self.scenario['start_state'])

        if next_state == 'start_question':
          if self.question_interval > 0 and bot.last_question_start_time is not None:
            time_since_last_question = time.time() - bot.last_question_start_time
            if time_since_last_question < self.question_interval:
              bot.interval_resume_time = time.time() + (self.question_interval - time_since_last_question)
              bot.waiting_for_interval = True
              return
          bot.last_question_start_time = None
          self.reset_scenario(bot)
        else:
          prev_state = self.current_state
          self.current_state = next_state
        self.last_change = time.time()
        self.expected_complete = False
        if hasattr(self, '_paste_enter_executed'):
          del self._paste_enter_executed

  def _run_action(self, bot, action, coords):
    x, y = int(coords[0]), int(coords[1])

    if action == "click":
      bot.action_queue.put(('click', (x, y)))
      time.sleep(0.5)
    elif action == "mousemove":
      bot.action_queue.put(('mousemove', (x, y)))
    elif action == "click_paste_enter":
      if hasattr(self, '_paste_enter_executed'):
        return
      prompt_text = bot.get_formatted_prompt()
      if prompt_text is None:
        return

      bot.clear_clipboard()
      time.sleep(0.2)
      try:
        cmd = ["xclip", "-selection", "clipboard", "-display", bot.display]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        proc.communicate(input=prompt_text.encode('utf-8'))
        proc.wait(timeout=2)
      except Exception:
        return

      bot.action_queue.put(('click', (x, y)))
      time.sleep(2.0)
      bot.action_queue.put(('hotkey', ['ctrl', 'v']))
      time.sleep(2.0)
      bot.action_queue.put(('key', 'Return'))
      time.sleep(1.0)
      bot.clear_clipboard()
      bot.increment_question_count()
      self._paste_enter_executed = True

    elif action == "click_paste_file_enter":
      if hasattr(self, '_paste_enter_executed'):
        return
      current_state_config = self.scenario['states'].get(self.current_state, {})
      file_path = current_state_config.get('file')
      if not file_path:
        return
      try:
        with open(file_path, 'r', encoding='utf-8') as f:
          file_content = f.read()
      except Exception:
        return

      bot.clear_clipboard()
      time.sleep(0.2)
      try:
        cmd = ["xclip", "-selection", "clipboard", "-display", bot.display]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        proc.communicate(input=file_content.encode('utf-8'))
        proc.wait(timeout=2)
      except Exception:
        return

      bot.action_queue.put(('click', (x, y)))
      time.sleep(1.0)
      bot.action_queue.put(('hotkey', ['ctrl', 'v']))
      time.sleep(1.0)
      bot.action_queue.put(('key', 'Return'))
      time.sleep(0.5)
      bot.clear_clipboard()
      bot.increment_question_count()
      self._paste_enter_executed = True

    elif action == "click_copy_save_json_check":
      self.copy_button_coords = (x, y)
      bot.action_queue.put(('click', (x, y)))
      time.sleep(0.5)
      bot.action_queue.put(('click', (x, y)))
      time.sleep(1.0)

    elif action == "click_ctrl_end":
      bot.action_queue.put(('click', (x, y)))
      time.sleep(0.3)
      bot.action_queue.put(('hotkey', ['ctrl', 'End']))
      time.sleep(0.3)

    elif action == "click_scroll_down":
      bot.action_queue.put(('click', (x, y)))
      time.sleep(0.3)
      bot.action_queue.put(('key', 'pagedown'))
      time.sleep(0.3)

    elif action == "scroll_up":
      bot.action_queue.put(('key', 'pageup'))
      time.sleep(0.3)
