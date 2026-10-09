from app import cli, config, doctor
from app.logging_setup import RedactFilter
import logging


def test_doctor_reports_action_required_when_apps_missing():
    s = config.load_settings()
    s["style"] = "synthesia"
    s["paths"]["obs_app"] = "/nonexistent/OBS.app"
    text, ready = doctor.render(doctor.run_checks(s, config.ROOT), True)
    assert "PIANO STUDIO AI" in text and not ready and "ACTION REQUIRED" in text


def test_unimplemented_commands_do_not_pretend(capsys):
    assert cli.main(["stop"]) == 2
    assert "pas encore implémenté" in capsys.readouterr().out


def test_log_redacts_secrets():
    r = logging.LogRecord("p", logging.INFO, "", 0, "auth token=abc123 ok", (), None)
    RedactFilter().filter(r)
    assert "abc123" not in r.msg


def test_doctor_sketch_style_needs_no_app():
    s = config.load_settings()
    s["style"] = "sketch"
    s["paths"]["obs_app"] = "/nonexistent/OBS.app"
    s["paths"]["synthesia_app"] = "/nonexistent/Synthesia.app"
    assert all(st == doctor.OK for _, st, _ in doctor.run_checks(s, config.ROOT))
