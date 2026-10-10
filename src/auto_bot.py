import numpy as np
import cv2
import time
import os
import json
import re
import sys
import threading
import datetime
from typing import Optional
from pathlib import Path
import ddddocr

from recognizer import CardRecognizer
from poker_core import calculate_best, JOKER_ID, card_text, CATEGORY_NAMES, _evaluate_category5
from settlement import SettlementReader, SettlementManager, is_valid_settlement_amount
from reward_vision import read_challenge_number, read_result_number
from challenge_reward import ChallengeRewardReader
from strategies import get_strategy, apply_strategy_modifiers, strategy_kwargs_from_config, STRATEGY_REGISTRY
import localization
from localization import tr, set_lang, get_strategy_labels
from window_control import capture_game_window, safe_click

try:
    # Windows source-mode runs otherwise inherit a legacy console encoding and
    # crash on the existing multilingual/emoji status messages.
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Directly initialize OCR engine globally
ocr = ddddocr.DdddOcr(show_ad=False)

bot_running = False
# ================= Global Configuration & Constants =================
TARGET_LIMIT = 20000

def _resolve_app_dir() -> Path:
    """Resolve the directory used for writable user data (config, logs, debug).

    In portable mode (standard installation), files are saved directly in the
    application directory. If that location is write-protected (e.g. Program Files
    or read-only volume), it automatically falls back to %APPDATA%/HololiveDreamsAuto.
    """
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    try:
        test_file = base / f".write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        return base
    except (OSError, PermissionError):
        appdata = os.getenv("APPDATA")
        if appdata:
            fallback = Path(appdata) / "HololiveDreamsAuto"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        return base


INSTALL_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
APP_DIR = _resolve_app_dir()
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", INSTALL_DIR)).resolve()
TEMPLATE_DIR = RESOURCE_DIR / "templates"
BACKGROUNDS_DIR = APP_DIR / "backgrounds"
DEBUG_DIR = APP_DIR / "debug"
LOGS_DIR = APP_DIR / "logs"
DEBUG_LOG_FILE = APP_DIR / "debug_log.txt"
DATA_FILE = APP_DIR / "config.json"

_CONFIG_LOCK = threading.RLock()
_config_cache: dict = {}
_config_mtime: float = -1.0
_debug_logging_enabled: Optional[bool] = None


def get_game_date(dt_utc: Optional[datetime.datetime] = None) -> str:
    """Calculate the game day string (YYYY-MM-DD), resetting daily at 16:00 US Eastern Time (4:00 PM EST/EDT)."""
    if dt_utc is None:
        dt_utc = datetime.datetime.now(datetime.timezone.utc)
    elif dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)

    year = dt_utc.year
    march_1 = datetime.datetime(year, 3, 1, tzinfo=datetime.timezone.utc)
    dst_start = datetime.datetime(year, 3, 1 + (6 - march_1.weekday()) % 7 + 7, 7, 0, tzinfo=datetime.timezone.utc)
    nov_1 = datetime.datetime(year, 11, 1, tzinfo=datetime.timezone.utc)
    dst_end = datetime.datetime(year, 11, 1 + (6 - nov_1.weekday()) % 7, 6, 0, tzinfo=datetime.timezone.utc)

    tz_eastern = datetime.timezone(datetime.timedelta(hours=-4 if dst_start <= dt_utc < dst_end else -5))
    eastern_dt = dt_utc.astimezone(tz_eastern)

    if eastern_dt.hour < 16:
        game_dt = eastern_dt - datetime.timedelta(days=1)
    else:
        game_dt = eastern_dt

    return game_dt.strftime("%Y-%m-%d")


def log_debug(msg: str):
    """Write timestamped message to debug_log.txt if debug_logging is enabled."""
    global _debug_logging_enabled
    if _debug_logging_enabled is False:
        return
    try:
        if _debug_logging_enabled is None:
            config = load_config()
            _debug_logging_enabled = bool(config.get("debug_logging", False))
            if not _debug_logging_enabled:
                return
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def resource_path(*parts):
    return str(RESOURCE_DIR.joinpath(*parts))

# === Dynamic Bounding Box Parameters ===
# Large search area covering middle screen to prevent missing detections
HIGH_LOW_SEARCH_ZONE = (42, 358, 1256, 451)

# Yellow bonus payout OCR detection zone
REWARD_ZONE = (606, 389, 870, 253)

# Blue settlement text OCR detection zone
RESULT_REWARD_ZONE = (990, 290, 600, 150)


# === Card Value Mapping ===
ROBUST_RANK_MAP = {
    "2": 2, "TWO": 2,
    "3": 3, "THREE": 3,
    "4": 4, "FOUR": 4,
    "5": 5, "FIVE": 5,
    "6": 6, "SIX": 6,
    "7": 7, "SEVEN": 7,
    "8": 8, "EIGHT": 8,
    "9": 9, "NINE": 9,
    "10": 10, "TEN": 10,
    "11": 11, "J": 11, "JACK": 11,
    "12": 12, "Q": 12, "QUEEN": 12,
    "13": 13, "K": 13, "KING": 13,
    "14": 14, "A": 14, "ACE": 14, "1": 14
}


def get_card_point_value(card) -> Optional[int]:
    if getattr(card, "card_id", None) == JOKER_ID:
        return 0

    raw = str(getattr(card, "rank", card)).upper().strip()
    if "." in raw:
        raw = raw.split(".")[-1]

    if raw in ROBUST_RANK_MAP:
        return ROBUST_RANK_MAP[raw]

    print(f"[Warning] Recognizer output unparseable rank: '{raw}', ID: {getattr(card, 'card_id', None)}")
    return None


ICON_TEMPLATES = {
    "START_BET": [
        resource_path("templates", "icons", "en", "start_en.png"),
        resource_path("templates", "icons", "ja", "start_ja.png"),
        resource_path("templates", "icons", "zh", "start_zh.png"),
        resource_path("templates", "icons", "tw", "start_tw.png"),
    ],
    "HOLD_CARDS": [
        resource_path("templates", "icons", "tpl_replace.png"),
        resource_path("templates", "icons", "en", "full_en.png"),
        resource_path("templates", "icons", "ja", "full_ja.png"),
        resource_path("templates", "icons", "zh", "full_zh.png"),
        resource_path("templates", "icons", "tw", "full_tw.png"),
    ],
    "TAP_TO_PROCEED": [
        resource_path("templates", "icons", "en", "proceed_en.png"),
        resource_path("templates", "icons", "ja", "proceed_ja.png"),
        resource_path("templates", "icons", "zh", "proceed_zh.png"),
        resource_path("templates", "icons", "tw", "proceed_tw.png"),
    ],
    "HIGH_LOW": [resource_path("templates", "icons", "tpl_high.png")],
    "RESULT": [
        resource_path("templates", "icons", "en", "result_en.png"),
        resource_path("templates", "icons", "ja", "result_ja.png"),
        resource_path("templates", "icons", "zh", "result_zh.png"),
        resource_path("templates", "icons", "tw", "result_tw.png"),
    ],
    "FAIL": [
        resource_path("templates", "icons", "en", "fail_en.png"),
        resource_path("templates", "icons", "en", "toobad_en.png"),
        resource_path("templates", "icons", "ja", "fail_ja.png"),
        resource_path("templates", "icons", "ja", "toobad_ja.png"),
        resource_path("templates", "icons", "zh", "fail_zh.png"),
        resource_path("templates", "icons", "zh", "toobad_zh.png"),
        resource_path("templates", "icons", "tw", "fail_tw.png"),
        resource_path("templates", "icons", "tw", "toobad_tw.png"),
    ],
    "ASK_CHALLENGE": [
        resource_path("templates", "icons", "en", "chance_en.png"),
        resource_path("templates", "icons", "en", "success_en.png"),
        resource_path("templates", "icons", "ja", "chance_ja.png"),
        resource_path("templates", "icons", "ja", "success_ja.png"),
        resource_path("templates", "icons", "zh", "chance_zh.png"),
        resource_path("templates", "icons", "zh", "success_zh.png"),
        resource_path("templates", "icons", "tw", "chance_tw.png"),
        resource_path("templates", "icons", "tw", "success_tw.png"),
    ],
}

_LANG_TEMPLATES: dict[str, list[tuple[str, str]]] = {"en": [], "ja": [], "zh": [], "tw": [], "other": []}
for _state, _tpl_paths in ICON_TEMPLATES.items():
    for _tpl_path in _tpl_paths:
        _p_str = str(_tpl_path)
        _matched = False
        for _lk in ("en", "ja", "zh", "tw"):
            if f"_{_lk}." in _p_str or f"/{_lk}/" in _p_str or f"\\{_lk}\\" in _p_str:
                _LANG_TEMPLATES[_lk].append((_state, _tpl_path))
                _matched = True
                break
        if not _matched:
            _LANG_TEMPLATES["other"].append((_state, _tpl_path))

TPL_REPLACE = resource_path("templates", "icons", "tpl_replace.png")
OK_AS_IS_TEMPLATES = [
    resource_path("templates", "icons", "en", "full_en.png"),
    resource_path("templates", "icons", "ja", "full_ja.png"),
    resource_path("templates", "icons", "zh", "full_zh.png"),
    resource_path("templates", "icons", "tw", "full_tw.png"),
]
TPL_HIGH = resource_path("templates", "icons", "tpl_high.png")
TPL_LOW = resource_path("templates", "icons", "tpl_low.png")
TPL_CONFIRM_DOUBLE = resource_path("templates", "icons", "tpl_check.png")
TPL_CASHOUT = resource_path("templates", "icons", "tpl_cross.png")
TPL_CARD_LOCK = resource_path("templates", "icons", "tpl_card_lock.png")


# ================= 1. Core Algorithm: High-Low Counter =================
class HighLowCounter:
    """Tracks remaining deck composition and computes exact winning odds for High/Low."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.deck = {i: 4 for i in range(2, 15)}
        self._counts = [0, 0, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
        self.total_cards = 52

    def remove_cards(self, cards_list):
        for card_val in cards_list:
            if 2 <= card_val <= 14 and self._counts[card_val] > 0:
                self._counts[card_val] -= 1
                self.deck[card_val] -= 1
                self.total_cards -= 1

    def get_best_choice_and_rate(self, current_card: int) -> tuple[str, float]:
        if self.total_cards <= 0:
            return "high", 0.5

        c = self._counts
        high_count = sum(c[current_card + 1:])
        low_count = sum(c[2:current_card])

        decision_cards = high_count + low_count
        if decision_cards <= 0:
            return "high", 0.5

        high_rate = high_count / decision_cards
        low_rate = low_count / decision_cards

        if high_rate >= low_rate:
            return "high", high_rate
        else:
            return "low", low_rate


# ================= 2. Vision Recognition & Control =================
# Window detection, capture, and safe_click are imported from window_control.


_TEMPLATE_CACHE: dict[str, np.ndarray | None] = {}


def get_template(path: str | os.PathLike) -> np.ndarray | None:
    p = os.fspath(path)
    if p in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[p]
    if not os.path.exists(p):
        _TEMPLATE_CACHE[p] = None
        return None
    try:
        data = np.frombuffer(Path(p).read_bytes(), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    except Exception:
        img = None
    _TEMPLATE_CACHE[p] = img
    return img


def preload_templates() -> int:
    """Pre-load all OpenCV icon templates into memory cache for zero disk I/O during game loop."""
    count = 0
    for state, tpl_paths in ICON_TEMPLATES.items():
        for p in tpl_paths:
            if get_template(p) is not None:
                count += 1
    for p in (TPL_REPLACE, TPL_HIGH, TPL_LOW, TPL_CONFIRM_DOUBLE, TPL_CASHOUT, TPL_CARD_LOCK, *OK_AS_IS_TEMPLATES):
        if get_template(p) is not None:
            count += 1
    return count


def find_and_click_icon(screen_bgr, tpl_path, win_left, win_top, threshold=0.80):
    tpl_path = os.fspath(tpl_path)
    tpl_img = get_template(tpl_path)
    if tpl_img is None:
        if not os.path.exists(tpl_path):
            print(tr('icon_not_found', path=tpl_path))
        return False

    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    if tpl_img.shape[0] > screen_gray.shape[0] or tpl_img.shape[1] > screen_gray.shape[1]:
        return False
    res = cv2.matchTemplate(screen_gray, tpl_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        h, w = tpl_img.shape
        log_debug(tr('click_trigger', name=os.path.basename(tpl_path), score=max_val, threshold=threshold))
        safe_click(max_loc[0] + w // 2, max_loc[1] + h // 2, win_left, win_top)
        return True
    else:
        return False


def is_success_prompt(screen_bgr):
    gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    for path in ICON_TEMPLATES['ASK_CHALLENGE']:
        if 'success_' not in os.path.basename(path):
            continue
        template = get_template(path)
        if template is not None and template.shape[0] <= gray.shape[0] and template.shape[1] <= gray.shape[1]:
            score = cv2.minMaxLoc(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED))[1]
            if score >= .85:
                return True
    return False


STATE_TRANSITIONS: dict[str, str] = {
    "START_BET": "HOLD_CARDS",
    "HOLD_CARDS": "TAP_TO_PROCEED",
    "TAP_TO_PROCEED": "ASK_CHALLENGE",
    "ASK_CHALLENGE": "HIGH_LOW",
    "HIGH_LOW": "ASK_CHALLENGE",
    "FAIL": "START_BET",
    "RESULT": "START_BET",
}


def detect_game_state(
    screen_bgr,
    lang: str | None = None,
    expected_state: str | None = None,
) -> str:
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    THRESHOLD = 0.85
    active_lang = lang or localization.get_lang()
    active_templates = _LANG_TEMPLATES.get(active_lang, [])

    # 1. Predictive fast path: if an expected next state is given, check its template first
    if expected_state:
        for state, tpl_path in active_templates:
            if state != expected_state:
                continue
            tpl_img = get_template(tpl_path)
            if tpl_img is None or tpl_img.shape[0] > screen_gray.shape[0] or tpl_img.shape[1] > screen_gray.shape[1]:
                continue
            res = cv2.matchTemplate(screen_gray, tpl_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val >= THRESHOLD:
                return state

    # 2. Primary path: try remaining templates matching active language
    for state, tpl_path in active_templates:
        if expected_state and state == expected_state:
            continue
        tpl_img = get_template(tpl_path)
        if tpl_img is None or tpl_img.shape[0] > screen_gray.shape[0] or tpl_img.shape[1] > screen_gray.shape[1]:
            continue
        res = cv2.matchTemplate(screen_gray, tpl_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= THRESHOLD:
            return state

    # 3. Fallback path: search remaining languages if not matched
    for lk, tpl_list in _LANG_TEMPLATES.items():
        if lk == active_lang:
            continue
        for state, tpl_path in tpl_list:
            tpl_img = get_template(tpl_path)
            if tpl_img is None or tpl_img.shape[0] > screen_gray.shape[0] or tpl_img.shape[1] > screen_gray.shape[1]:
                continue
            res = cv2.matchTemplate(screen_gray, tpl_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val >= THRESHOLD:
                return state

    return "UNKNOWN"


def find_all_card_rects(img, search_zone):
    sx, sy, sw, sh = search_zone
    roi = img[sy:sy + sh, sx:sx + sw]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Extract all pure white regions (utilize purple-black face-down cards to ignore them)
    white_mask = cv2.inRange(hsv, (0, 0, 180), (180, 60, 255))

    contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Size filter: only keep card-sized blocks
        if w > 100 and h > 150:
            rects.append((sx + x, sy + y, w, h))
    return rects


def get_currently_held_indices(
    rects: list[tuple[int, int, int, int]],
    screen_height: int = 1080,
    img: Optional[np.ndarray] = None,
) -> set[int]:
    """Detect which cards in rects are currently in the held position.

    Combines:
    1. Lock icon detection (language-independent 🔒) at the bottom of each card slot.
       Uses proportional scaling and multi-scale template matching across all display resolutions.
    2. Card vertical displacement: selected/held cards shift DOWNWARD by ~30-40px.
    """
    if len(rects) != 5:
        return set()

    screen_h = img.shape[0] if (img is not None and img.size > 0) else screen_height

    # Pass 1: Visual Lock Icon Detection (if frame is provided)
    if img is not None and img.size > 0:
        h_img, w_img = img.shape[:2]
        lock_tpl = get_template(TPL_CARD_LOCK)
        held_by_badge = set()
        lock_scores: dict[int, float] = {}

        for idx, (x, y, bw, bh) in enumerate(rects):
            y0 = max(0, y + int(0.65 * bh))
            y1 = min(h_img, y + bh + int(0.20 * bh))
            x0 = max(0, x)
            x1 = min(w_img, x + bw)
            roi = img[y0:y1, x0:x1]
            if roi.size == 0:
                continue

            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            # Multi-scale lock icon match (~11% of card width across 720p/1080p/1440p/4K)
            best_score = 0.0
            if lock_tpl is not None:
                tw_base = max(10, round(bw * 0.11))
                for delta in (-1, 0, 1):
                    tw = tw_base + delta
                    th = max(10, round(tw * (lock_tpl.shape[0] / max(1, lock_tpl.shape[1]))))
                    if th <= roi_gray.shape[0] and tw <= roi_gray.shape[1]:
                        scaled_tpl = cv2.resize(
                            lock_tpl,
                            (tw, th),
                            interpolation=cv2.INTER_AREA if tw < lock_tpl.shape[1] else cv2.INTER_LINEAR,
                        )
                        lock_res = cv2.matchTemplate(roi_gray, scaled_tpl, cv2.TM_CCOEFF_NORMED)
                        score = float(cv2.minMaxLoc(lock_res)[1])
                        if score > best_score:
                            best_score = score

            lock_scores[idx] = best_score
            if best_score >= 0.80:
                held_by_badge.add(idx)

        scores_str = ", ".join(f"slot {i}: {lock_scores.get(i, 0.0):.2f}" for i in range(len(rects)))
        if held_by_badge:
            log_debug(f"[Poker Hold Vision] Lock icon detected on slots {sorted(held_by_badge)} ({scores_str})")
            return held_by_badge
        else:
            log_debug(f"[Poker Hold Vision] No lock icons detected ({scores_str}). Checking card vertical displacement...")

    # Pass 2: Vertical Y displacement (held cards shifted downward)
    y_vals = [r[1] for r in rects]
    min_y = min(y_vals)
    max_y = max(y_vals)

    min_gap = max(8, round(0.015 * screen_h))
    if max_y - min_y >= min_gap:
        split_threshold = min_y + (max_y - min_y) // 2
        detected = {i for i, y in enumerate(y_vals) if y > split_threshold}
        log_debug(f"[Poker Hold Vision] Shift fallback: detected slots {sorted(detected)} by downward displacement (gap: {max_y - min_y}px)")
        return detected

    # When all 5 cards are at the same height:
    # Baseline (unheld) y is typically ~0.316 * height.
    # Shifted down (held) y is typically ~0.344 * height.
    held_down_threshold = round(0.330 * screen_h)
    if min_y > held_down_threshold:
        log_debug(f"[Poker Hold Vision] Shift fallback: all 5 cards shifted downward past threshold (y={min_y} > {held_down_threshold})")
        return {0, 1, 2, 3, 4}

    log_debug("[Poker Hold Vision] Shift fallback: all cards at upper baseline, none held")
    return set()


# ---------------------------------------------------------
# OCR Engine 1: extract yellow digits on light purple background
# ---------------------------------------------------------
def read_challenge_payout(img, search_zone):
    return read_challenge_number(img, search_zone, ocr)


# ---------------------------------------------------------
# OCR Engine 2: pure white background light blue text (RESULT settlement screen Coins)
# ---------------------------------------------------------
_SETTLEMENT_TRANS = str.maketrans({
    'O': '0', 'o': '0', 'Q': '0', 'q': '0', 'D': '0',
    'I': '1', 'i': '1', 'L': '1', 'l': '1',
    'Z': '2', 'z': '2', 'S': '5', 's': '5',
    'B': '8', 'b': '8'
})


def read_settlement_payout(img, search_zone, expected=None):
    sx, sy, sw, sh = search_zone
    if sw == 0 or sh == 0:
        return 0

    # Primary pass: isolate cyan digits via HSV color segmentation
    try:
        cyan_amount = read_result_number(img, search_zone, ocr)
        if cyan_amount > 0:
            if expected is not None and expected > 0:
                if cyan_amount == expected or str(expected) in str(cyan_amount):
                    return expected
            if is_valid_settlement_amount(cyan_amount):
                return cyan_amount
    except Exception:
        pass

    # Fallback pass: grayscale OCR extraction
    roi = img[sy:sy + sh, sx:sx + sw]
    roi = cv2.resize(roi, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    ok, img_bytes = cv2.imencode('.png', gray)
    if not ok or img_bytes is None:
        return 0
    text = ocr.classification(img_bytes.tobytes())

    text = re.sub(r'(?i)coins?|earned', '', text)
    text = text.translate(_SETTLEMENT_TRANS)
    digits = ''.join(filter(str.isdigit, text))

    # Priority 1: If expected cashout is known, check if it's contained in the OCR digits
    # (e.g. '1600' inside '160015' due to noise or trailing characters)
    if expected is not None and expected > 0:
        exp_str = str(expected)
        if exp_str in digits:
            return expected

    # Priority 2: Parse raw digits and validate against Hololive Dreams game rules
    try:
        val = int(digits) if digits else 0
        if is_valid_settlement_amount(val):
            return val
        return 0
    except ValueError:
        return 0


CONFIG_CATEGORIES = {
    # Daily Progress & Accounting
    "accounting": [
        "date", "coins", "fails", "rounds", "pending_cashout", "pending_cashout_date",
    ],
    # General & Application Settings
    "general": [
        "language", "hotkey", "target_limit", "ticket_cost", "debug_logging",
    ],
    # UI Appearance & Layout
    "display": [
        "theme_mode", "background_index", "field_box_opacity", "show_log",
        "modifiers_expanded", "mod_cat_cards_expanded", "mod_cat_bail_expanded", "mod_cat_prog_expanded",
    ],
    # Log Management
    "log": [
        "log_retention_days", "log_max_size_mb",
    ],
    # Strategy & Parameters
    "strategy": [
        "strategy_key", "strategy_index",
        "param_cushion_target", "param_sprint_target", "param_min_win_rate", "param_max_doubles", "param_drop_seven_eight",
    ],
    # Strategy Modifiers
    "modifiers": [
        "mod_fast_build", "mod_free_roll", "mod_sprint_floor", "mod_mega_sprint",
    ],
    # Defensive Bailouts
    "defensive_bailouts": [
        "mod_drop_6789", "mod_drop_78", "mod_drop_8",
    ],
    # Card Overrides
    "card_overrides": [
        "opportunistic_double_mode",
        "opp_a2", "opp_3k", "opp_4q", "opp_5j", "opp_610", "opp_79", "opp_8",
    ],
    # Settlement & Recovery
    "settlement": [
        "settlement_recovery_mode", "settlement_ocr_timeout",
    ],
}

CONFIG_KEY_ORDER = [k for keys in CONFIG_CATEGORIES.values() for k in keys]


def _flatten_config_dict(data: dict) -> dict:
    """Flatten categorized nested config dicts to flat key-value pairs for code consumers."""
    flat = {}
    for k, v in data.items():
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                flat[sub_k] = sub_v
        else:
            flat[k] = v
    return flat


def _categorize_config_dict(cfg: dict) -> dict:
    """Return dict with keys structured into clear, readable categories."""
    flat = _flatten_config_dict(cfg)
    categorized = {}
    assigned_keys = set()
    for cat_name, keys in CONFIG_CATEGORIES.items():
        section = {}
        for k in keys:
            if k in flat:
                section[k] = flat[k]
                assigned_keys.add(k)
        if section:
            categorized[cat_name] = section
    extras = {k: v for k, v in flat.items() if k not in assigned_keys}
    if extras:
        categorized["custom"] = extras
    return categorized


def _order_config_dict(cfg: dict) -> dict:
    """Return categorized nested config dictionary for readability."""
    return _categorize_config_dict(cfg)


def _write_config(updater_fn):
    global _config_cache, _config_mtime, _debug_logging_enabled
    with _CONFIG_LOCK:
        current = _load_config_unlocked()
        updater_fn(current)
        ordered_data = _order_config_dict(current)
        tmp_name = f"{DATA_FILE.stem}_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.tmp"
        temporary = DATA_FILE.parent / tmp_name
        try:
            temporary.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('w', encoding='utf-8') as f:
                json.dump(ordered_data, f, ensure_ascii=False, indent=2)
            os.replace(temporary, DATA_FILE)
            _config_cache = _flatten_config_dict(ordered_data)
            try:
                _config_mtime = DATA_FILE.stat().st_mtime
            except Exception:
                _config_mtime = time.time()
            _debug_logging_enabled = bool(_config_cache.get("debug_logging", False))
        except Exception:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
            raise


def save_pending_cashout(cash: int):
    def update(cfg):
        cfg["pending_cashout"] = cash
        cfg["pending_cashout_date"] = get_game_date()
    _write_config(update)


def clear_pending_cashout():
    def update(cfg):
        cfg.pop("pending_cashout", None)
        cfg.pop("pending_cashout_date", None)
    _write_config(update)


def load_pending_cashout() -> int | None:
    data = load_config()
    if data.get("pending_cashout_date") == get_game_date():
        val = data.get("pending_cashout")
        if isinstance(val, int) and is_valid_settlement_amount(val):
            return val
    return None



# ================= 3. Data & Main Loop =================
_config_file: Optional[Path] = None


def _load_config_unlocked() -> dict:
    global _config_cache, _config_mtime, _config_file, _debug_logging_enabled
    if DATA_FILE.exists():
        try:
            mtime = DATA_FILE.stat().st_mtime
            if DATA_FILE == _config_file and mtime == _config_mtime and _config_cache:
                return dict(_config_cache)
            with DATA_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    flat_data = _flatten_config_dict(data)
                    _config_cache = flat_data
                    _config_file = DATA_FILE
                    _config_mtime = mtime
                    _debug_logging_enabled = bool(flat_data.get("debug_logging", False))
                    return dict(_config_cache)
        except Exception:
            pass
    elif _config_file != DATA_FILE:
        return {}
    return dict(_config_cache) if _config_cache else {}


def load_config() -> dict:
    with _CONFIG_LOCK:
        return _load_config_unlocked()


def load_daily_rounds() -> int:
    data = load_config()
    if data.get("date") == get_game_date():
        try:
            return max(0, int(data.get("rounds", 0)))
        except (ValueError, TypeError):
            return 0
    return 0


def load_daily_data():
    data = load_config()
    if data.get("date") == get_game_date():
        try:
            coins = max(0, int(data.get("coins", 0)))
            fails = max(0, int(data.get("fails", 0)))
            return coins, fails
        except (ValueError, TypeError):
            return 0, 0
    return 0, 0


def save_daily_data(coins, fails, rounds: Optional[int] = None, **settings):
    def update(cfg):
        cfg.pop("phased_stage", None)
        cfg.update({
            "coins": coins,
            "fails": fails,
            "date": get_game_date(),
        })
        if rounds is not None:
            cfg["rounds"] = max(0, int(rounds))
        elif "rounds" not in cfg:
            cfg["rounds"] = 0
        if settings:
            cfg.update(settings)
    _write_config(update)


class BotSessionState:
    """Encapsulates runtime state, counters, and session trackers for auto_play_loop."""

    def __init__(
        self,
        mode: str,
        strat_name: str,
        target_limit: int,
        cushion_val: int,
        ticket_cost: int,
        daily_coins: int,
        daily_fails: int,
        round_count: int,
        net_profit: int,
        strategy: Any,
        counter: HighLowCounter,
        card_rec: CardRecognizer,
        reward_reader: ChallengeRewardReader,
        settlement_mgr: Optional[SettlementManager],
        on_stats_update: Optional[Callable],
        on_prompt_settlement: Optional[Callable],
    ):
        self.mode = mode
        self.strat_name = strat_name
        self.target_limit = target_limit
        self.cushion_val = cushion_val
        self.ticket_cost = ticket_cost
        self.daily_coins = daily_coins
        self.daily_fails = daily_fails
        self.round_count = round_count
        self.net_profit = net_profit
        self.strategy = strategy
        self.counter = counter
        self.card_rec = card_rec
        self.reward_reader = reward_reader
        self.settlement_mgr = settlement_mgr
        self.on_stats_update = on_stats_update
        self.on_prompt_settlement = on_prompt_settlement

        self.current_game_date = get_game_date()
        self.step_count = 0
        self.in_round = False
        self.poker_deal_solved = False
        self.solved_hand_ids: list[int] = []
        self.target_held_indices: set[int] = set()
        self.has_logged_final_hand = False
        self.has_done_initial_hold = False
        self.last_replace_click_time = 0.0
        self.upcoming_card_val: Optional[int] = None
        self.current_card_already_removed = False
        self.has_recorded_fail = False
        self.has_confirmed_success = False
        self.unknown_frames_count = 0
        self.debug_mode: bool = False
        self.last_state: Optional[str] = None
        self._config: dict = load_config()
        try:
            self._config_mtime: float = CONFIG_FILE.stat().st_mtime
        except Exception:
            self._config_mtime = 0.0

    def get_config(self) -> dict:
        try:
            mtime = CONFIG_FILE.stat().st_mtime
            if mtime != self._config_mtime:
                self._config = load_config()
                self._config_mtime = mtime
        except Exception:
            pass
        return self._config

    def save_data_wrapper(self, coins: int, fails: int):
        save_daily_data(coins, fails, rounds=self.round_count)

    def try_log_final_poker_hand(self, frame: Optional[np.ndarray]) -> bool:
        if self.has_logged_final_hand or frame is None or frame.size == 0:
            return False
        post_cards, _ = self.card_rec.recognize(frame)
        if len(post_cards) == 5 and all(getattr(c, "rank_score", 1.0) >= 0.60 for c in post_cards):
            post_ids = [c.card_id for c in post_cards]
            if self.solved_hand_ids and len(self.target_held_indices) < 5 and post_ids == self.solved_hand_ids:
                return False
            final_labels = [card_text(c.card_id) for c in post_cards]
            final_str = " ".join(final_labels)
            final_cat = _evaluate_category5(*(c.card_id for c in post_cards))
            final_cat_key = f"poker_cat_{final_cat}"
            final_cat_name = tr(final_cat_key) if final_cat_key in localization.TRANSLATIONS.get(localization.get_lang(), {}) else CATEGORY_NAMES[final_cat]
            print(f"  " + tr('poker_hand_final', cards=final_str, category=final_cat_name))
            log_debug(f"[Poker Draw Final] Hand: {final_cat_name} | Cards: [{final_str}]")
            self.has_logged_final_hand = True
            return True
        return False

    def request_cashout(self, frame: np.ndarray, left: int, top: int, cash: int) -> bool:
        if find_and_click_icon(frame, TPL_CASHOUT, left, top):
            if self.settlement_mgr:
                self.settlement_mgr.expected_cashout = cash
            save_pending_cashout(cash)
            return True
        return False

    def update_state_flicker_guards(self, current_state: str):
        if current_state in ("START_BET", "HOLD_CARDS"):
            if self.settlement_mgr:
                self.settlement_mgr.reset_round(self.strategy)
            self.reward_reader.reset_round()
            self.has_confirmed_success = False
            clear_pending_cashout()
        elif current_state in ('HIGH_LOW', 'FAIL', 'RESULT'):
            self.reward_reader.reset_prompt()
            self.has_confirmed_success = False
            self.poker_deal_solved = False
            self.solved_hand_ids = []
            self.target_held_indices = set()
            self.last_replace_click_time = 0.0
            self.has_done_initial_hold = False
        if current_state != "FAIL":
            self.has_recorded_fail = False

    def handle_unknown_state(self):
        self.unknown_frames_count += 1
        if self.unknown_frames_count == 10:
            log_debug("[State Warning] Unknown game state for 10 consecutive frames (~5.0s). Waiting for recognized screen...")
        elif self.unknown_frames_count > 10 and self.unknown_frames_count % 30 == 0:
            log_debug(f"[State Warning] Still in UNKNOWN state ({self.unknown_frames_count} frames, ~{self.unknown_frames_count * 0.5:.1f}s)...")

    def reset_unknown_state(self, new_state: str):
        if self.unknown_frames_count >= 10:
            log_debug(f"[State Transition] Recovered from UNKNOWN state after {self.unknown_frames_count} frames -> New state: {new_state}")
        self.unknown_frames_count = 0


def handle_start_bet(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    ctx.poker_deal_solved = False
    ctx.solved_hand_ids = []
    ctx.target_held_indices = set()
    ctx.has_logged_final_hand = False
    ctx.has_done_initial_hold = False
    ctx.last_replace_click_time = 0.0
    new_date = get_game_date()
    if new_date != ctx.current_game_date:
        ctx.current_game_date = new_date
        ctx.daily_coins = 0
        ctx.daily_fails = 0
        ctx.round_count = 0
        ctx.net_profit = 0
        save_daily_data(0, 0, rounds=0)
        if ctx.on_stats_update:
            ctx.on_stats_update(0, 0, 0)
        print(f"\n[Daily Reset] 4:00 PM EST rollover reached ({new_date}). Counters reset to 0.\n")

    ctx.counter.reset()
    ctx.upcoming_card_val = None
    ctx.current_card_already_removed = False

    # Try clicking Start icon for current language
    started = False
    for tpl in ICON_TEMPLATES["START_BET"]:
        if find_and_click_icon(img, tpl, win_left, win_top):
            started = True
            break

    if started:
        if not ctx.in_round:
            ctx.round_count += 1
            ctx.step_count = 0
            ctx.in_round = True
            save_daily_data(ctx.daily_coins, ctx.daily_fails, rounds=ctx.round_count)
            print(f"\n" + tr('round_header', round=ctx.round_count, coins=f"{ctx.daily_coins:,}", target=f"{ctx.target_limit:,}", fails=ctx.daily_fails))
            log_debug(f"=== Starting Round #{ctx.round_count} (Coins: {ctx.daily_coins}, Fails: {ctx.daily_fails}, Net: {ctx.net_profit}) ===")
            log_debug(f"[Poker Entry] Entry fee -{ctx.ticket_cost} coins applied for Round #{ctx.round_count}")
    else:
        log_debug("[Start Bet Warning] START_BET state active but start button icon template was below threshold")
    time.sleep(0.35)


def handle_hold_cards(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    ctx.current_card_already_removed = False
    recognized_cards, rects = ctx.card_rec.recognize(img)
    if len(recognized_cards) == 5 and all(getattr(c, "rank_score", 1.0) >= 0.60 for c in recognized_cards):
        hand_ids = [c.card_id for c in recognized_cards]
        if ctx.poker_deal_solved and hand_ids != ctx.solved_hand_ids:
            old_labels = " ".join(card_text(cid) for cid in ctx.solved_hand_ids)
            new_labels = " ".join(card_text(cid) for cid in hand_ids)
            log_debug(f"[Poker Deal] Hand cards changed on screen (Was: [{old_labels}] -> Now: [{new_labels}]). Re-evaluating optimal hold.")
            ctx.counter.reset()
            ctx.poker_deal_solved = False
            ctx.has_done_initial_hold = False
            ctx.last_replace_click_time = 0.0
            ctx.has_logged_final_hand = False

        if not ctx.poker_deal_solved:
            ctx.solved_hand_ids = list(hand_ids)
            card_values = [v for c in recognized_cards if c.card_id != JOKER_ID if (v := get_card_point_value(c)) is not None]
            ctx.counter.remove_cards(card_values)

            cat_idx = _evaluate_category5(*(c.card_id for c in recognized_cards))
            cat_trans_key = f"poker_cat_{cat_idx}"
            cat_name = tr(cat_trans_key) if cat_trans_key in localization.TRANSLATIONS.get(localization.get_lang(), {}) else CATEGORY_NAMES[cat_idx]
            card_labels = [card_text(c.card_id) for c in recognized_cards]
            cards_str = " ".join(card_labels)

            best, _ = calculate_best(hand_ids, "standard")
            ctx.target_held_indices = set(best.held_indices)
            held_labels = [card_labels[i] for i in best.held_indices]
            held_str = " ".join(held_labels) if held_labels else tr("poker_hold_none")
            draw_count = 5 - len(best.held_indices)

            print(tr('poker_hand_dealt', cards=cards_str, category=cat_name))
            print(f"  " + tr('poker_optimal_hold', held=held_str, draw_count=draw_count, ev=best.expected_payout, rate=best.win_probability))

            card_diag = ", ".join(f"{card_text(c.card_id)}(conf={c.rank_score:.2f},margin={c.rank_margin:.2f})" for c in recognized_cards)
            log_debug(f"[Poker Deal] 5 cards recognized: {card_diag}")
            log_debug(f"[Poker Solver] Hand: {cat_name} | Best Hold: mask={best.mask:#07b} indices={best.held_indices} (Keep: {held_str}) | EV={best.expected_payout:.2f} | WinProb={best.win_probability:.2%}")
            ctx.poker_deal_solved = True
            ctx.has_done_initial_hold = False
            ctx.last_replace_click_time = 0.0
            ctx.has_logged_final_hand = False

        card_labels = [card_text(c.card_id) for c in recognized_cards]
        # Inspect current visual hold state (lock badge + downward shift)
        currently_held = get_currently_held_indices(rects, img.shape[0], img=img)
        to_toggle = ctx.target_held_indices ^ currently_held

        if to_toggle:
            if not ctx.has_done_initial_hold:
                toggle_labels = " ".join(card_labels[i] for i in sorted(to_toggle))
                log_debug(f"[Poker Hold] Selecting target cards: [{toggle_labels}] (slots {sorted(to_toggle)})")
            else:
                current_held_str = " ".join(card_labels[i] for i in sorted(currently_held)) if currently_held else tr("poker_hold_none")
                target_held_str = " ".join(card_labels[i] for i in sorted(ctx.target_held_indices)) if ctx.target_held_indices else tr("poker_hold_none")
                toggled_str = " ".join(card_labels[i] for i in sorted(to_toggle))
                print(f"  " + tr('poker_hold_resync', held=target_held_str, toggled=toggled_str))
                log_debug(
                    f"[Poker Hold Sync] Selection mismatch! Currently held: [{current_held_str}] (slots {sorted(currently_held)}) | "
                    f"Target: [{target_held_str}] (slots {sorted(ctx.target_held_indices)}) -> Re-clicking: [{toggled_str}] (slots {sorted(to_toggle)})"
                )
            for idx in sorted(to_toggle):
                x, y, w_box, h_box = rects[idx]
                safe_click(x + w_box // 2, y + h_box // 2, win_left, win_top)
                time.sleep(0.08)
            ctx.has_done_initial_hold = True
            time.sleep(0.10)
        else:
            ctx.has_done_initial_hold = True
            held_cards_str = " ".join(card_labels[i] for i in sorted(ctx.target_held_indices)) if ctx.target_held_indices else tr("poker_hold_none")
            log_debug(f"[Poker Hold Sync] Cards verified in desired hold state: [{held_cards_str}] (slots {sorted(ctx.target_held_indices)})")

        can_click_replace = (
            not ctx.has_logged_final_hand
            and (time.monotonic() - ctx.last_replace_click_time >= 1.5)
        )
        if can_click_replace:
            fresh_img, f_left, f_top = capture_game_window()
            img_for_replace = fresh_img if fresh_img is not None else img
            wl = f_left if fresh_img is not None else win_left
            wt = f_top if fresh_img is not None else win_top

            clicked = find_and_click_icon(img_for_replace, TPL_REPLACE, wl, wt)
            if not clicked:
                for tpl_ok in OK_AS_IS_TEMPLATES:
                    if find_and_click_icon(img_for_replace, tpl_ok, wl, wt):
                        clicked = True
                        break

            if clicked:
                ctx.last_replace_click_time = time.monotonic()
                time.sleep(0.25)
                for _ in range(15):
                    time.sleep(0.08)
                    post_img, _, _ = capture_game_window()
                    if ctx.try_log_final_poker_hand(post_img):
                        break
            else:
                log_debug("[Poker Hold] Replace / OK as is button click did not trigger or missed; will retry next frame")
                time.sleep(0.2)
        else:
            time.sleep(0.2)
    else:
        log_debug(f"[Poker Deal Warning] Detected {len(recognized_cards)}/5 cards in frame. Waiting for animation...")


def handle_tap_to_proceed(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    ctx.try_log_final_poker_hand(img)
    h, w = img.shape[:2]
    log_debug(f"[State] TAP_TO_PROCEED: Clicking screen center ({w // 2}, {h // 2}) to advance prompt")
    safe_click(w // 2, h // 2, win_left, win_top)
    time.sleep(0.20)


def handle_ask_challenge(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    ctx.try_log_final_poker_hand(img)
    if getattr(ctx.strategy, "base_cash", None) is None:
        if is_success_prompt(img):
            raise RuntimeError('Currently mid-doubling, cannot recover win count. Please start from a fresh round.')
        real_reward = read_challenge_payout(img, REWARD_ZONE)
        next_reward = ctx.reward_reader.observe(real_reward, time.monotonic())
        if next_reward is None:
            log_debug(f"[Challenge OCR] Waiting for initial payout stabilization (raw={real_reward})...")
            time.sleep(0.25)
            return
        current_cashout = next_reward // 2
        ctx.strategy.start_round(current_cashout, ctx.daily_coins)
        log_debug(f"[Challenge OCR] Initial payout confirmed: current_cashout={current_cashout}, next_reward={next_reward}")
    else:
        if is_success_prompt(img) and not ctx.has_confirmed_success:
            ctx.strategy.confirm_success()
            ctx.has_confirmed_success = True

        if getattr(ctx.strategy, "requires_ongoing_ocr", True):
            real_reward = read_challenge_payout(img, REWARD_ZONE)
            next_reward = ctx.reward_reader.observe(real_reward, time.monotonic())
            if next_reward is None:
                log_debug(f"[Challenge OCR] Waiting for ongoing payout stabilization (raw={real_reward})...")
                time.sleep(0.25)
                return
            current_cashout = next_reward // 2
            log_debug(f"[Challenge OCR] Ongoing payout confirmed: current_cashout={current_cashout}, next_reward={next_reward}")
        else:
            current_cashout = ctx.strategy.expected_cash or 0
            next_reward = current_cashout * 2

    if ctx.upcoming_card_val is not None:
        _, win_rate = ctx.counter.get_best_choice_and_rate(ctx.upcoming_card_val)
        rate_text = tr('risk_prediction', rate=win_rate)
    else:
        win_rate = 1.0
        rate_text = tr('risk_blind')

    action = ctx.strategy.decide(current_cashout, next_reward, win_rate, ctx.daily_coins)

    # Apply active strategy modifiers and card overrides from cached configuration
    runtime_config = ctx.get_config()
    opp_a2 = runtime_config.get("opp_a2", True)
    opp_3k = runtime_config.get("opp_3k", False)
    opp_4q = runtime_config.get("opp_4q", False)
    opp_5j = runtime_config.get("opp_5j", False)
    opp_610 = runtime_config.get("opp_610", False)
    opp_79 = runtime_config.get("opp_79", False)
    opp_8 = runtime_config.get("opp_8", False)

    mod_fast_build = runtime_config.get("mod_fast_build", False)
    mod_drop_78 = runtime_config.get("mod_drop_78", runtime_config.get("param_drop_seven_eight", False))
    mod_drop_6789 = runtime_config.get("mod_drop_6789", False)
    mod_drop_8 = runtime_config.get("mod_drop_8", False)
    mod_free_roll = runtime_config.get("mod_free_roll", False)
    mod_sprint_floor = runtime_config.get("mod_sprint_floor", False)
    mod_mega_sprint = runtime_config.get("mod_mega_sprint", False)

    user_cushion = runtime_config.get("param_cushion_target")
    cushion_target = int(user_cushion) if user_cushion is not None else getattr(ctx.strategy, "cushion_target", 19800)
    if hasattr(ctx.strategy, "cushion_target"):
        ctx.strategy.cushion_target = cushion_target

    action, mod_reason = apply_strategy_modifiers(
        decision=action,
        card_val=ctx.upcoming_card_val,
        current_cashout=current_cashout,
        next_reward=next_reward,
        daily_coins=ctx.daily_coins,
        target_limit=ctx.target_limit,
        cushion_target=cushion_target,
        opp_a2=opp_a2,
        opp_3k=opp_3k,
        opp_4q=opp_4q,
        opp_5j=opp_5j,
        opp_610=opp_610,
        opp_79=opp_79,
        opp_8=opp_8,
        mod_fast_build=mod_fast_build,
        mod_drop_78=mod_drop_78,
        mod_drop_6789=mod_drop_6789,
        mod_drop_8=mod_drop_8,
        mod_free_roll=mod_free_roll,
        mod_sprint_floor=mod_sprint_floor,
        mod_mega_sprint=mod_mega_sprint,
        win_rate=win_rate,
    )

    print(tr('challenge_current', cashout=f"{current_cashout:,}", reward=f"{next_reward:,}"))
    print(f"  {rate_text}")

    if mod_reason:
        if action == 'challenge' and hasattr(ctx.strategy, 'last_cashout'):
            ctx.strategy.last_cashout = None
        if mod_reason == 'opportunistic_card':
            rank_name = {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"}.get(ctx.upcoming_card_val, str(ctx.upcoming_card_val))
            print(f"  " + tr('opportunistic_double_msg', rank=rank_name, rate=win_rate, reward=next_reward, limit=ctx.target_limit))
        elif mod_reason == 'mod_fast_build':
            print(f"  " + tr('mod_fast_build_msg', reward=next_reward, cushion=cushion_target))
        elif mod_reason == 'mod_free_roll':
            print(f"  " + tr('mod_free_roll_msg', cashout=current_cashout))
        elif mod_reason == 'mod_drop_6789':
            rank_name = str(ctx.upcoming_card_val)
            print(f"  " + tr('mod_drop_6789_msg', rank=rank_name, cashout=current_cashout))
        elif mod_reason == 'mod_drop_78':
            rank_name = str(ctx.upcoming_card_val)
            print(f"  " + tr('mod_drop_78_msg', rank=rank_name, cashout=current_cashout))
        elif mod_reason == 'mod_drop_8':
            rank_name = str(ctx.upcoming_card_val)
            print(f"  " + tr('mod_drop_8_msg', rank=rank_name, cashout=current_cashout))
        elif mod_reason == 'mod_mega_sprint':
            print(f"  " + tr('mod_mega_sprint_msg', cashout=current_cashout))
        elif mod_reason == 'mod_sprint_floor':
            print(f"  " + tr('mod_sprint_floor_msg', cashout=current_cashout))

    effective_cash = ctx.strategy.expected_cash or current_cashout
    reason_str = mod_reason or ctx.strat_name
    if action == 'cashout':
        print(f"  " + tr('challenge_decision_cashout', reason=reason_str))
        log_debug(f"[Decision] CASHOUT (effective_cash={effective_cash}, daily={ctx.daily_coins}, mod={mod_reason})")
        ctx.request_cashout(img, win_left, win_top, effective_cash)
    else:
        print(f"  " + tr('challenge_decision_double', reason=reason_str))
        log_debug(f"[Decision] DOUBLE UP (next_reward={next_reward}, headroom={cushion_target - (ctx.daily_coins + next_reward)}, mod={mod_reason})")
        find_and_click_icon(img, TPL_CONFIRM_DOUBLE, win_left, win_top, threshold=0.55)

    time.sleep(0.6)


def handle_high_low(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    try:
        # 1. Detect all white face-up cards with new engine
        rects = find_all_card_rects(img, HIGH_LOW_SEARCH_ZONE)

        if rects:
            # Sort by X coordinate to get the rightmost face-up card
            rects.sort(key=lambda r: r[0])
            current_rect = rects[-1]
            old_right_x = current_rect[0]

            single_card = ctx.card_rec.recognize_card(img, current_rect)
            if single_card.card_id != JOKER_ID:
                current_card_val = get_card_point_value(single_card)
                if current_card_val is None:
                    log_debug(f"[High-Low Warning] Unable to parse card rank: {single_card.rank}")
                    time.sleep(0.2)
                    return
                if not ctx.current_card_already_removed:
                    ctx.counter.remove_cards([current_card_val])
                    ctx.current_card_already_removed = True
                best_choice, rate = ctx.counter.get_best_choice_and_rate(current_card_val)

                ctx.step_count += 1
                card_label = card_text(single_card.card_id)

                print(tr('hl_step_header', step=ctx.step_count, card=card_label, remaining=ctx.counter.total_cards))
                print(f"  " + tr('visible_card_choice', rank=card_label, choice=best_choice.upper(), rate=rate))

                high_cards = sum(ctx.counter._counts[current_card_val + 1:])
                low_cards = sum(ctx.counter._counts[2:current_card_val])
                tie_cards = ctx.counter._counts[current_card_val]
                tot = max(1, ctx.counter.total_cards)
                log_debug(f"[High-Low Step #{ctx.step_count}] Visible: {card_label} (rank='{single_card.rank}', suit='{single_card.suit}', conf={single_card.rank_score:.2f}, margin={single_card.rank_margin:.2f}, box={current_rect})")
                log_debug(f"[High-Low Deck] Remaining={tot} | HIGH={high_cards}/{tot} ({high_cards/tot:.1%}) | LOW={low_cards}/{tot} ({low_cards/tot:.1%}) | TIE={tie_cards}/{tot} ({tie_cards/tot:.1%}) -> Choice: {best_choice.upper()}")

                if best_choice == "high":
                    guessed = find_and_click_icon(img, TPL_HIGH, win_left, win_top)
                else:
                    guessed = find_and_click_icon(img, TPL_LOW, win_left, win_top)
                if ctx.strategy is not None and guessed:
                    ctx.strategy.guess_clicked()
                ctx.current_card_already_removed = False

                # === 2. Continuous State Tracking & Burst Capture ===
                log_debug(f"[High-Low Step #{ctx.step_count}] Burst card tracking started...")
                ctx.upcoming_card_val = None
                candidate_card = None
                stable_count = 0

                # Narrow horizontal search zone to right of previous card for faster contour detection
                burst_x = max(HIGH_LOW_SEARCH_ZONE[0], old_right_x + 10)
                burst_w = (HIGH_LOW_SEARCH_ZONE[0] + HIGH_LOW_SEARCH_ZONE[2]) - burst_x
                burst_zone = (burst_x, HIGH_LOW_SEARCH_ZONE[1], burst_w, HIGH_LOW_SEARCH_ZONE[3]) if burst_w > 100 else HIGH_LOW_SEARCH_ZONE

                for i in range(25):
                    time.sleep(0.04)
                    flip_img, _, _ = capture_game_window()

                    if flip_img is not None:
                        try:
                            new_rects = find_all_card_rects(flip_img, burst_zone)
                            if new_rects:
                                new_rects.sort(key=lambda r: r[0])
                                newest_rect = new_rects[-1]

                                if newest_rect[0] > old_right_x + 50:
                                    newest_card = ctx.card_rec.recognize_card(flip_img, newest_rect)
                                    if (newest_card.card_id != JOKER_ID
                                            and getattr(newest_card, 'rank_score', 1.0) >= 0.65):
                                        if candidate_card is not None and candidate_card.rank == newest_card.rank:
                                            stable_count += 1
                                        else:
                                            candidate_card = newest_card
                                            stable_count = 1

                                        if stable_count >= 2 or getattr(newest_card, 'rank_score', 0) >= 0.80:
                                            new_val = get_card_point_value(newest_card)
                                            if new_val is not None:
                                                ctx.upcoming_card_val = new_val
                                                ctx.counter.remove_cards([ctx.upcoming_card_val])
                                                ctx.current_card_already_removed = True

                                                flipped_label = card_text(newest_card.card_id)
                                                if new_val > current_card_val:
                                                    cmp_txt = f"{new_val} > {current_card_val}"
                                                    outcome = "WIN" if best_choice == "high" else "LOSS"
                                                elif new_val < current_card_val:
                                                    cmp_txt = f"{new_val} < {current_card_val}"
                                                    outcome = "WIN" if best_choice == "low" else "LOSS"
                                                else:
                                                    cmp_txt = f"{new_val} == {current_card_val}"
                                                    outcome = "TIE (Push)"

                                                print(f"  " + tr('hl_card_flipped', card=flipped_label, cmp=cmp_txt, outcome=outcome))
                                                log_debug(f"[Burst Tracking] Frame {i + 1}: Detected [{flipped_label}] (rank='{newest_card.rank}', suit='{newest_card.suit}', conf={newest_card.rank_score:.2f}, margin={newest_card.rank_margin:.2f}, stable={stable_count}) -> {cmp_txt} [{outcome}]")

                                                if ctx.debug_mode:
                                                    DEBUG_DIR.mkdir(exist_ok=True)
                                                    cx, cy, cw, ch = newest_rect
                                                    cv2.imwrite(str(DEBUG_DIR / "2_next_card.png"),
                                                                flip_img[max(0, cy - 40):cy + ch + 40,
                                                                max(0, cx - 40):cx + cw + 40])
                                                break
                        except Exception:
                            continue

                if ctx.upcoming_card_val is None:
                    print(f"  " + tr('hl_tracking_timeout_user'))
                    log_debug(f"[Burst Tracking Warning] Frame tracking timed out after 25 frames. Unable to identify next card.")

                time.sleep(0.15)
        else:
            print(tr('warn_no_cards'))
            log_debug(f"[High-Low Warning] No white face-up card contours found in {HIGH_LOW_SEARCH_ZONE}")
    except Exception as e:
        print(tr('err_high_low', error=e))
        log_debug(f"[High-Low Exception] {e}")


def handle_fail(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    ctx.try_log_final_poker_hand(img)
    clear_pending_cashout()
    if not ctx.has_recorded_fail:
        ctx.daily_fails += 1
        loss = ctx.daily_fails * ctx.ticket_cost
        ctx.net_profit = ctx.daily_coins - loss
        save_daily_data(ctx.daily_coins, ctx.daily_fails, rounds=ctx.round_count)
        print(f"\n" + tr('fail_summary', fails=ctx.daily_fails, loss=loss, profit=ctx.net_profit))
        log_debug(f"[Round #{ctx.round_count} BUST] Total fails: {ctx.daily_fails}, ticket loss: {loss}, net profit: {ctx.net_profit}")
        if ctx.on_stats_update:
            ctx.on_stats_update(ctx.daily_coins, ctx.daily_fails, ctx.net_profit)
        if ctx.strategy is not None:
            ctx.strategy.begin_settlement(cashout_requested=False)
            ctx.strategy.notify_fail()
            if hasattr(ctx.strategy, "_check_auto_adjust"):
                ctx.strategy._check_auto_adjust(ctx.daily_coins, ctx.daily_fails, ctx.ticket_cost)
        ctx.has_recorded_fail = True
        ctx.in_round = False

    time.sleep(0.35)
    find_and_click_icon(img, TPL_CONFIRM_DOUBLE, win_left, win_top, threshold=0.55)
    time.sleep(0.40)


def handle_result(ctx: BotSessionState, img: np.ndarray, win_left: int, win_top: int):
    ctx.try_log_final_poker_hand(img)
    amount = read_settlement_payout(img, RESULT_REWARD_ZONE, expected=ctx.settlement_mgr.expected_cashout if ctx.settlement_mgr else None)
    if ctx.settlement_mgr:
        ctx.daily_coins, can_proceed = ctx.settlement_mgr.process_result(
            amount=amount,
            now=time.monotonic(),
            daily_coins=ctx.daily_coins,
            daily_fails=ctx.daily_fails,
            strategy=ctx.strategy,
            on_stats_update=ctx.on_stats_update,
            ticket_cost=ctx.ticket_cost,
            on_prompt_settlement=ctx.on_prompt_settlement,
        )
        if not can_proceed:
            time.sleep(0.2)
            return

    clear_pending_cashout()
    ctx.in_round = False
    time.sleep(0.35)
    find_and_click_icon(img, TPL_CONFIRM_DOUBLE, win_left, win_top, threshold=0.55)
    time.sleep(0.40)


STATE_HANDLERS: dict[str, Callable[[BotSessionState, np.ndarray, int, int], None]] = {
    "START_BET": handle_start_bet,
    "HOLD_CARDS": handle_hold_cards,
    "TAP_TO_PROCEED": handle_tap_to_proceed,
    "ASK_CHALLENGE": handle_ask_challenge,
    "HIGH_LOW": handle_high_low,
    "FAIL": handle_fail,
    "RESULT": handle_result,
}


def auto_play_loop(mode='max_profit', on_stats_update=None, lang=None, on_prompt_settlement=None):
    if lang is not None:
        set_lang(lang)
    config = load_config()
    target_limit = int(config.get("target_limit", TARGET_LIMIT))
    ticket_cost = int(config.get("ticket_cost", 50))
    recovery_mode = config.get("settlement_recovery_mode", "auto")
    ocr_timeout = float(config.get("settlement_ocr_timeout", 8.0))

    strategy = get_strategy(mode, **strategy_kwargs_from_config(mode, config))
    counter = HighLowCounter()
    card_rec = CardRecognizer(TEMPLATE_DIR)
    daily_coins, daily_fails = load_daily_data()
    round_count = load_daily_rounds()
    net_profit = daily_coins - (daily_fails * ticket_cost)

    strat_name = getattr(strategy, "name", mode)
    strat_labels = get_strategy_labels()
    keys = tuple(STRATEGY_REGISTRY.keys())
    idx = keys.index(mode) if mode in keys else -1
    strat_display = strat_labels[idx] if 0 <= idx < len(strat_labels) else strat_name
    user_cushion = config.get("param_cushion_target")
    cushion_val = int(user_cushion) if user_cushion is not None else getattr(strategy, "cushion_target", 19800)
    if hasattr(strategy, "cushion_target"):
        strategy.cushion_target = cushion_val
    mod_fast_build = config.get("mod_fast_build", False)
    mod_drop_78 = config.get("mod_drop_78", config.get("param_drop_seven_eight", False))
    mod_drop_6789 = config.get("mod_drop_6789", False)
    mod_drop_8 = config.get("mod_drop_8", False)
    mod_free_roll = config.get("mod_free_roll", False)
    mod_sprint_floor = config.get("mod_sprint_floor", False)
    mod_mega_sprint = config.get("mod_mega_sprint", False)

    opp_a2 = config.get("opp_a2", True)
    opp_3k = config.get("opp_3k", False)
    opp_4q = config.get("opp_4q", False)
    opp_5j = config.get("opp_5j", False)
    opp_610 = config.get("opp_610", False)
    opp_79 = config.get("opp_79", False)
    opp_8 = config.get("opp_8", False)
    debug_mode = config.get("debug_logging", False)

    print("=" * 52)
    print(tr('banner_title', time=time.strftime('%Y-%m-%d %H:%M:%S')))
    print(tr('banner_strategy', name=strat_display))
    print(tr('banner_targets', target=f"{target_limit:,}", cushion=f"{cushion_val:,}", ticket=ticket_cost))
    rounds_str = f" | {tr('banner_rounds', rounds=round_count)}" if round_count > 0 else ""
    print(tr('banner_stats', coins=f"{daily_coins:,}", fails=daily_fails, rounds=rounds_str, profit=f"{net_profit:,}"))
    print(tr('banner_modifiers_header'))
    print(tr('banner_mod_row1',
             fast_build=tr('state_on') if mod_fast_build else tr('state_off'),
             free_roll=tr('state_on') if mod_free_roll else tr('state_off')))
    print(tr('banner_mod_bailouts',
             b6789=tr('state_on') if mod_drop_6789 else tr('state_off'),
             b78=tr('state_on') if mod_drop_78 else tr('state_off'),
             b8=tr('state_on') if mod_drop_8 else tr('state_off')))
    print(tr('banner_mod_sprint',
             sf=tr('state_on') if mod_sprint_floor else tr('state_off'),
             ms=tr('state_on') if mod_mega_sprint else tr('state_off')))
    print(tr('banner_mod_overrides',
             a2=tr('state_on') if opp_a2 else tr('state_off'),
             k3=tr('state_on') if opp_3k else tr('state_off'),
             q4=tr('state_on') if opp_4q else tr('state_off'),
             j5=tr('state_on') if opp_5j else tr('state_off'),
             t6=tr('state_on') if opp_610 else tr('state_off'),
             s7=tr('state_on') if opp_79 else tr('state_off'),
             e8=tr('state_on') if opp_8 else tr('state_off')))
    print(tr('banner_debug_log', status=tr('state_enabled') if debug_mode else tr('state_disabled')))
    print("=" * 52 + "\n")
    print(tr('start_bot', coins=daily_coins, fails=daily_fails, profit=net_profit))
    preload_templates()

    log_debug("=" * 52)
    log_debug(f"Bot session started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_debug(f"Strategy: {strat_name}, Mode: {mode}, Target: {target_limit}, Cushion: {cushion_val}")
    log_debug(f"Modifiers: fast_build={mod_fast_build}, free_roll={mod_free_roll}, drop_6789={mod_drop_6789}, drop_78={mod_drop_78}, drop_8={mod_drop_8}, sprint_floor={mod_sprint_floor}, mega_sprint={mod_mega_sprint}")
    log_debug(f"Card overrides: a2={opp_a2}, 3k={opp_3k}, 4q={opp_4q}, 5j={opp_5j}, 610={opp_610}, 79={opp_79}, 8={opp_8}")
    log_debug("=" * 52)
    if on_stats_update:
        on_stats_update(daily_coins, daily_fails, net_profit)

    reward_reader = ChallengeRewardReader()

    ctx = BotSessionState(
        mode=mode,
        strat_name=strat_name,
        target_limit=target_limit,
        cushion_val=cushion_val,
        ticket_cost=ticket_cost,
        daily_coins=daily_coins,
        daily_fails=daily_fails,
        round_count=round_count,
        net_profit=net_profit,
        strategy=strategy,
        counter=counter,
        card_rec=card_rec,
        reward_reader=reward_reader,
        settlement_mgr=None,
        on_stats_update=on_stats_update,
        on_prompt_settlement=on_prompt_settlement,
    )
    ctx.debug_mode = debug_mode

    settlement_mgr = SettlementManager(
        SettlementReader(timeout=ocr_timeout),
        save_data_fn=ctx.save_data_wrapper,
        recovery_mode=recovery_mode,
        on_prompt_settlement=on_prompt_settlement,
    )
    settlement_mgr.reset_round(strategy)
    pending_cash = load_pending_cashout()
    if pending_cash:
        settlement_mgr.expected_cashout = pending_cash
    ctx.settlement_mgr = settlement_mgr

    while ctx.daily_coins < ctx.target_limit and bot_running:
        img, win_left, win_top = capture_game_window()
        if img is None:
            print(tr('window_not_found'))
            time.sleep(1)
            continue

        expected_next = STATE_TRANSITIONS.get(ctx.last_state) if ctx.last_state else None
        current_state = (
            detect_game_state(img, expected_state=expected_next)
            if expected_next
            else detect_game_state(img)
        )
        ctx.update_state_flicker_guards(current_state)

        if current_state == "UNKNOWN":
            ctx.handle_unknown_state()
            time.sleep(0.15)
            continue

        ctx.reset_unknown_state(current_state)
        ctx.last_state = current_state

        handler = STATE_HANDLERS.get(current_state)
        if handler:
            handler(ctx, img, win_left, win_top)
        else:
            time.sleep(0.20)

    if ctx.daily_coins >= ctx.target_limit:
        print(tr('state_full'))


if __name__ == "__main__":
    auto_play_loop()
