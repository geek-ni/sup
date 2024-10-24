import os
from datetime import datetime


class Logger:
    def __init__(self, log_dir="Logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.current_log_file = self._create_new_log_file()

    def _create_new_log_file(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.log_dir, f"log_{timestamp}.txt")
        with open(file_path, "w") as f:
            intro = self._get_intro()
            f.write(intro)
        return open(file_path, "a")

    def _get_intro(self):
        with open("intro.txt", "r") as intro_file:
            intro = intro_file.read()
        creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        intro = intro.replace(
            "[@] Creation date: ", f"[@] Creation date: {creation_date}\n\n"
        )
        return intro

    def log(self, message, source="SYSTEM"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{source}] {message}\n"
        self.current_log_file.write(log_entry)
        self.current_log_file.flush()

    def get_current_log_content(self):
        with open(self.current_log_file.name, "r") as f:
            return f.read()

    def get_all_log_files(self):
        return [
            f
            for f in os.listdir(self.log_dir)
            if f.startswith("log_") and f.endswith(".txt")
        ]


logger = Logger()
