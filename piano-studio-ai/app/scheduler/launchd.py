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


AGENT_LABEL = "com.pianostudio.agent"


def agent_label(instance: str = "") -> str:
    return AGENT_LABEL + (f".{instance}" if instance else "")


def build_agent_plist(root: Path, instance: str = "") -> bytes:
    """Lance l'interface (et donc le pilote automatique) à l'ouverture de session, la relance si elle plante."""
    return plistlib.dumps({
        "Label": agent_label(instance),
        "ProgramArguments": ["/bin/bash", str(root / "p.sh")] + (["--instance", instance] if instance else []) + ["ui", "--no-browser"],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": str(root / "logs" / f"agent{('.' + instance) if instance else ''}.out.log"),
        "StandardErrorPath": str(root / "logs" / f"agent{('.' + instance) if instance else ''}.err.log"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
    })


def install_agent(root, home=Path.home(), instance: str = "") -> Path:
    p = home / "Library" / "LaunchAgents" / f"{agent_label(instance)}.plist"
    p.parent.mkdir(parents=True, exist_ok=True)
    (Path(root) / "logs").mkdir(parents=True, exist_ok=True)
    p.write_bytes(build_agent_plist(Path(root), instance))
    return p
