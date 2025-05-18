from pathlib import Path
from aider.io import InputOutput
from aider.history import ChatSummary


class Memory:
    def __init__(self, path, summarizer=None, io=None):
        self.path = Path(path)
        self.io = io or InputOutput()
        self.summarizer = summarizer
        self.content = self.load() or ""

    def load(self):
        if self.path.exists():
            return self.io.read_text(self.path) or ""
        return ""

    def save(self, text):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.io.write_text(self.path, text)
        self.content = text

    def append(self, text):
        if not text.endswith("\n"):
            text += "\n"
        self.save(self.content + text)

    def summarize(self):
        if not self.summarizer or not self.content.strip():
            return self.content
        messages = [dict(role="user", content=self.content)]
        try:
            summary_msgs = self.summarizer.summarize_all(messages)
        except Exception:
            return self.content
        summary = summary_msgs[0]["content"] if summary_msgs else self.content
        self.save(summary)
        return summary
