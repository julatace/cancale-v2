import logging
import re
from logging.handlers import RotatingFileHandler

_SECRET = re.compile(r"(token|secret|password|key)=\S+", re.I)


class RedactFilter(logging.Filter):
    def filter(self, record):
        record.msg = _SECRET.sub(r"\1=***", str(record.getMessage()))
        record.args = ()
        return True


def setup_logging(logs_dir, level="INFO"):
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("piano")
    root.setLevel(level)
    if root.handlers:
        return root
    fmt = logging.Formatter("[%(levelname)s] %(asctime)s %(message)s")
    for h in (RotatingFileHandler(logs_dir / "piano.log", maxBytes=2_000_000, backupCount=5),
              logging.StreamHandler()):
        h.setFormatter(fmt)
        h.addFilter(RedactFilter())
        root.addHandler(h)
    return root
