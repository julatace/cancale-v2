import plistlib
import sys
from pathlib import Path

LABEL = "com.pianostudio.run"


def build_plist(times: list[str], root: Path, python=sys.executable) -> bytes:
    cal = [{"Hour": int(t.split(":")[0]), "Minute": int(t.split(":")[1])} for t in times]
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [python, "-m", "app.cli", "run"],
        "WorkingDirectory": str(root),
        "StartCalendarInterval": cal,
        "StandardOutPath": str(root / "logs" / "launchd.out.log"),
        "StandardErrorPath": str(root / "logs" / "launchd.err.log"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
    })


def install(times, root, home=Path.home()) -> Path:
    p = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(build_plist(times, root))
    return p
