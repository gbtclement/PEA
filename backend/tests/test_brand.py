from pathlib import Path

from app.core.brand import APP_NAME

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_app_name():
    assert APP_NAME == "Cotalyx"


def test_old_name_is_gone_from_code_and_mails():
    hits = [str(p) for p in APP_DIR.rglob("*") if p.is_file() and p.suffix in {".py", ".html", ".txt"}
            and "PEA Radar" in p.read_text(encoding="utf-8")]
    assert hits == []
