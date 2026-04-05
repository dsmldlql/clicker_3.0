"""
CSV логирование операций бота для Docker-деплоя.
Pipe-delimited CSV.
"""

import csv
import os
import threading
from datetime import datetime
from typing import Optional


class BotCSVLogger:
    """
    Per-bot CSV логгер.
    Файл: logs/bot_{N}/log_{N}_{YYYYMMDD}.csv
    Колонки: timestamp|event_type|attempt_number|global_index|question_uid
    """

    COLUMNS = ['timestamp', 'event_type', 'attempt_number', 'global_index', 'question_uid']

    def __init__(self, bot_id: int, log_dir: str):
        self.bot_id = bot_id
        self.log_dir = log_dir
        self.csv_lock = threading.Lock()
        self.current_attempt = 0

        os.makedirs(log_dir, exist_ok=True)
        self.csv_log_file = os.path.join(log_dir, f"log_{bot_id}_{datetime.now().strftime('%Y%m%d')}.csv")
        self._init_csv()

    def _init_csv(self):
        try:
            if not os.path.exists(self.csv_log_file) or os.path.getsize(self.csv_log_file) == 0:
                with self.csv_lock:
                    with open(self.csv_log_file, 'w', encoding='utf-8') as f:
                        writer = csv.writer(f, delimiter='|', lineterminator='\n')
                        writer.writerow(self.COLUMNS)
        except Exception as e:
            print(f"[!] [Бот {self.bot_id}] Ошибка инициализации CSV: {e}")

    def log(self, event_type: str, global_index: Optional[int] = None,
            question_uid: Optional[str] = None):
        """
        Логирует событие в CSV бота.
        Для QUESTION автоматически инкрементирует attempt_number.
        """
        if event_type == "QUESTION":
            self.current_attempt += 1
        attempt_num = self.current_attempt if event_type == "QUESTION" else None

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.csv_lock:
                with open(self.csv_log_file, 'a', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter='|', lineterminator='\n')
                    writer.writerow([
                        timestamp,
                        event_type,
                        attempt_num if attempt_num is not None else "",
                        global_index if global_index is not None else "",
                        question_uid if question_uid is not None else ""
                    ])
        except Exception as e:
            print(f"[!] [Бот {self.bot_id}] Ошибка записи CSV: {e}")


def get_bot_csv_logger(bot_id: int, log_dir: str) -> BotCSVLogger:
    return BotCSVLogger(bot_id, log_dir)
