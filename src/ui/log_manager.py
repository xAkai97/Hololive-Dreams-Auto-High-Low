"""Log management, rotation, retention pruning, and session loading."""
import datetime
import re
import time
from pathlib import Path
import auto_bot
import localization


def load_saved_stats():
    c, fl = auto_bot.load_daily_data()
    data = auto_bot.load_config()
    ticket_cost = int(data.get("ticket_cost", 50))
    return c, fl, c - (fl * ticket_cost)


def is_trivial_log_content(text: str) -> bool:
    """Check if log text contains only startup/close/resume banners and trivial messages."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    trivial_prefixes = (
        "=== UI Session Started:",
        "=== UI Session Closed:",
        "=== UI Session Resumed:",
        "[Settings]",
    )
    for line in lines:
        if not any(line.startswith(p) for p in trivial_prefixes):
            return False
    return True


def clean_old_logs(max_days: int = 14, max_size_mb: int = 20, lang: str = "en") -> tuple[int, float]:
    """Remove archived logs in auto_bot.LOGS_DIR exceeding age (days) or total size (MB).

    Returns (deleted_count, freed_mb).
    """
    if not auto_bot.LOGS_DIR.exists():
        return 0, 0.0

    deleted_count = 0
    freed_bytes = 0
    now = time.time()

    # 0. Prune empty/trivial log files in logs directory
    for f in list(auto_bot.LOGS_DIR.glob("*.txt")):
        if f.is_file():
            try:
                if f.stat().st_size < 400:
                    c = f.read_text(encoding="utf-8", errors="replace")
                    if is_trivial_log_content(c):
                        sz = f.stat().st_size
                        f.unlink()
                        deleted_count += 1
                        freed_bytes += sz
            except Exception:
                pass

    log_files = [f for f in auto_bot.LOGS_DIR.glob("log_*.txt") if f.is_file()]

    # 1. Prune by Age (if max_days > 0)
    if max_days > 0:
        max_age_seconds = max_days * 86400
        surviving_files = []
        for f in log_files:
            try:
                age = now - f.stat().st_mtime
                if age > max_age_seconds:
                    size = f.stat().st_size
                    f.unlink()
                    deleted_count += 1
                    freed_bytes += size
                else:
                    surviving_files.append(f)
            except Exception:
                surviving_files.append(f)
        log_files = surviving_files

    # 2. Prune by Total Directory Size (if max_size_mb > 0)
    if max_size_mb > 0:
        max_bytes = max_size_mb * 1024 * 1024
        file_stats = []
        for f in log_files:
            try:
                st = f.stat()
                file_stats.append((st.st_mtime, st.st_size, f))
            except Exception:
                pass

        file_stats.sort(key=lambda x: x[0])  # oldest first
        total_size = sum(item[1] for item in file_stats)

        for mtime, size, f in file_stats:
            if total_size <= max_bytes:
                break
            try:
                f.unlink()
                deleted_count += 1
                freed_bytes += size
                total_size -= size
            except Exception:
                pass

    freed_mb = freed_bytes / (1024 * 1024)
    if deleted_count > 0:
        print(localization.tr("log_cleanup_done", lang, count=deleted_count, size_mb=freed_mb))

    return deleted_count, freed_mb


def rotate_previous_log(max_days: int = 14, max_size_mb: int = 20, lang: str = "en", force: bool = False):
    """Archive previous log.txt to logs/ if daily cap was reached or date rolled over past 4:00 PM EST."""
    try:
        log_file = auto_bot.APP_DIR / "log.txt"
        if log_file.exists() and log_file.stat().st_size > 0:
            content = log_file.read_text(encoding="utf-8", errors="replace")
            if is_trivial_log_content(content):
                try:
                    log_file.unlink()
                except Exception:
                    pass
            else:
                m = re.search(r"=== UI Session Started:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2}):(\d{2})", content)
                if m:
                    try:
                        session_dt = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}", "%Y-%m-%d %H:%M:%S").astimezone()
                        log_game_date = auto_bot.get_game_date(session_dt.astimezone(datetime.timezone.utc))
                    except Exception:
                        log_game_date = m.group(1)

                    current_date = auto_bot.get_game_date()
                    config = auto_bot.load_config()
                    coins = int(config.get("coins", 0))
                    target = int(config.get("target_limit", 20000))
                    is_same_day_in_progress = (log_game_date == current_date and coins < target)
                else:
                    log_game_date = None
                    is_same_day_in_progress = False

                if force or not is_same_day_in_progress:
                    auto_bot.LOGS_DIR.mkdir(parents=True, exist_ok=True)
                    mtime = log_file.stat().st_mtime
                    archive_date = log_game_date or time.strftime("%Y-%m-%d", time.localtime(mtime))
                    target_file = auto_bot.LOGS_DIR / f"log_{archive_date}.txt"

                    counter = 1
                    while target_file.exists():
                        target_file = auto_bot.LOGS_DIR / f"log_{archive_date}_{counter}.txt"
                        counter += 1

                    log_file.replace(target_file)

        debug_file = auto_bot.APP_DIR / "debug_log.txt"
        if debug_file.exists() and debug_file.stat().st_size > 0:
            debug_content = debug_file.read_text(encoding="utf-8", errors="replace")
            if is_trivial_log_content(debug_content):
                try:
                    debug_file.unlink()
                except Exception:
                    pass
            else:
                m = re.search(r"=== Hololive Dreams Debug Log \((.*?)\) ===", debug_content)
                if m:
                    try:
                        session_dt = datetime.datetime.strptime(m.group(1).strip(), "%Y-%m-%d %H:%M:%S").astimezone()
                        log_game_date = auto_bot.get_game_date(session_dt.astimezone(datetime.timezone.utc))
                    except Exception:
                        log_game_date = None
                else:
                    log_game_date = None

                current_date = auto_bot.get_game_date()
                config = auto_bot.load_config()
                coins = int(config.get("coins", 0))
                target = int(config.get("target_limit", 20000))
                is_same_day_in_progress = (log_game_date == current_date and coins < target) if log_game_date else False

                if force or not is_same_day_in_progress:
                    auto_bot.LOGS_DIR.mkdir(parents=True, exist_ok=True)
                    mtime = debug_file.stat().st_mtime
                    archive_date = log_game_date or time.strftime("%Y-%m-%d", time.localtime(mtime))
                    target_debug = auto_bot.LOGS_DIR / f"debug_log_{archive_date}.txt"
                    counter = 1
                    while target_debug.exists():
                        target_debug = auto_bot.LOGS_DIR / f"debug_log_{archive_date}_{counter}.txt"
                        counter += 1
                    debug_file.replace(target_debug)
    except Exception as e:
        print(f"[Warning] Failed to rotate log file: {e}")

    try:
        clean_old_logs(max_days=max_days, max_size_mb=max_size_mb, lang=lang)
    except Exception as e:
        print(f"[Warning] Failed to clean old logs: {e}")
