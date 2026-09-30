import numpy as np
import cv2
import random
import time
import os
import json
import re
import sys
from pathlib import Path
import ddddocr

from recognizer import CardRecognizer
from poker_core import calculate_best, JOKER_ID
from settlement import SettlementReader, SettlementManager, is_valid_settlement_amount
from reward_vision import read_challenge_number
from challenge_reward import ChallengeRewardReader
from strategies import BaseStrategy, get_strategy
import localization
from localization import tr, set_lang, get_lang
from window_control import (
    GAME_TITLE,
    REFERENCE_WIDTH,
    REFERENCE_HEIGHT,
    find_game_window,
    capture_game_window,
    safe_click,
    init_dpi_awareness,
)

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
ASSETS_DIR = RESOURCE_DIR / "assets"
DEBUG_DIR = APP_DIR / "debug"
LOGS_DIR = APP_DIR / "logs"
LOG_FILE = APP_DIR / "log.txt"
DATA_FILE = APP_DIR / "config.json"


def resource_path(*parts):
    return str(RESOURCE_DIR.joinpath(*parts))

# === Dynamic Bounding Box Parameters ===
CARD_WIDTH = 260
# Large search area covering middle screen to prevent missing detections
HIGH_LOW_SEARCH_ZONE = (42, 358, 1256, 451)

# Yellow bonus payout OCR detection zone
REWARD_ZONE = (606, 389, 870, 253)

# Blue settlement text OCR detection zone
RESULT_REWARD_ZONE = (990, 290, 600, 150)


# === Card Value Mapping ===
def get_card_point_value(card):
    if card.card_id == JOKER_ID:
        return 0

    raw = str(card.rank).upper().strip()
    if "." in raw:
        raw = raw.split(".")[-1]

    robust_map = {
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

    if raw in robust_map:
        return robust_map[raw]

    print(f"[Warning] Recognizer output unparseable rank: '{raw}', ID: {card.card_id}")
    return 8


ICON_TEMPLATES = {
    "START_BET": [
        resource_path("templates", "icons", "en", "start_en.png"),
        resource_path("templates", "icons", "ja", "start_ja.png"),
        resource_path("templates", "icons", "zh", "start_zh.png"),
        resource_path("templates", "icons", "tw", "start_tw.png"),
    ],
    "HOLD_CARDS": [resource_path("templates", "icons", "tpl_replace.png")],
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
    "FULL": [
        resource_path("templates", "icons", "en", "full_en.png"),
        resource_path("templates", "icons", "ja", "full_ja.png"),
        resource_path("templates", "icons", "zh", "full_zh.png"),
        resource_path("templates", "icons", "tw", "full_tw.png"),
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
TPL_HIGH = resource_path("templates", "icons", "tpl_high.png")
TPL_LOW = resource_path("templates", "icons", "tpl_low.png")
TPL_CONFIRM_DOUBLE = resource_path("templates", "icons", "tpl_check.png")
TPL_CASHOUT = resource_path("templates", "icons", "tpl_cross.png")


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

        high_rate = high_count / self.total_cards
        low_rate = low_count / self.total_cards

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
        print(tr('click_trigger', name=os.path.basename(tpl_path), score=max_val, threshold=threshold))
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


def detect_game_state(screen_bgr, lang: str | None = None) -> str:
    screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
    THRESHOLD = 0.85
    active_lang = lang or localization.get_lang()

    # Fast path: try templates matching active language first
    for state, tpl_path in _LANG_TEMPLATES.get(active_lang, []):
        tpl_img = get_template(tpl_path)
        if tpl_img is None or tpl_img.shape[0] > screen_gray.shape[0] or tpl_img.shape[1] > screen_gray.shape[1]:
            continue
        res = cv2.matchTemplate(screen_gray, tpl_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= THRESHOLD:
            return state

    # Fallback path: search remaining languages if not matched
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


def save_pending_cashout(cash: int):
    current = load_config()
    current["pending_cashout"] = cash
    current["pending_cashout_date"] = time.strftime("%Y-%m-%d")
    temporary = Path(DATA_FILE).with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    os.replace(temporary, DATA_FILE)


def clear_pending_cashout():
    current = load_config()
    if "pending_cashout" in current or "pending_cashout_date" in current:
        current.pop("pending_cashout", None)
        current.pop("pending_cashout_date", None)
        temporary = Path(DATA_FILE).with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        os.replace(temporary, DATA_FILE)


def load_pending_cashout() -> int | None:
    data = load_config()
    if data.get("pending_cashout_date") == time.strftime("%Y-%m-%d"):
        val = data.get("pending_cashout")
        if isinstance(val, int) and is_valid_settlement_amount(val):
            return val
    return None



# ================= 3. Data & Main Loop =================
def load_config() -> dict:
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def load_daily_data():
    data = load_config()
    if data.get("date") == time.strftime("%Y-%m-%d"):
        try:
            coins = max(0, int(data.get("coins", 0)))
            fails = max(0, int(data.get("fails", 0)))
            return coins, fails
        except (ValueError, TypeError):
            return 0, 0
    return 0, 0


def load_daily_stage():
    data = load_config()
    if not data:
        return 0
    raw_stage = data.get('phased_stage', 0) if data.get('date') == time.strftime('%Y-%m-%d') else 0
    try:
        stage = int(raw_stage)
        if 0 <= stage <= 3:
            return stage
    except (ValueError, TypeError):
        pass
    return 0


def save_daily_data(coins, fails, stage=None, **settings):
    # Save coins and stage together; legacy mode preserves the saved stage.
    if stage is None:
        stage = load_daily_stage()
    current = load_config()
    current.update({
        "coins": coins,
        "fails": fails,
        "date": time.strftime("%Y-%m-%d"),
        "phased_stage": stage,
    })
    if settings:
        current.update(settings)
    temporary = Path(DATA_FILE).with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    os.replace(temporary, DATA_FILE)


def auto_play_loop(mode='legacy_101', on_stats_update=None, lang=None, on_prompt_settlement=None):
    upcoming_card_val = None
    if lang is not None:
        set_lang(lang)
    config = load_config()
    target_limit = int(config.get("target_limit", TARGET_LIMIT))
    ticket_cost = int(config.get("ticket_cost", 50))
    recovery_mode = config.get("settlement_recovery_mode", "auto")
    ocr_timeout = float(config.get("settlement_ocr_timeout", 8.0))

    strat_kwargs = {}
    if mode == "custom_parametric":
        if "param_min_win_rate" in config:
            strat_kwargs["min_win_rate"] = float(config["param_min_win_rate"]) / 100.0
        if "param_cashout_target" in config:
            strat_kwargs["cashout_target"] = int(config["param_cashout_target"])
        if "param_sprint_threshold" in config:
            strat_kwargs["sprint_threshold"] = int(config["param_sprint_threshold"])
        if "param_sprint_cashout" in config:
            strat_kwargs["sprint_cashout"] = int(config["param_sprint_cashout"])
        if "param_max_doubles" in config:
            strat_kwargs["max_doubles"] = int(config["param_max_doubles"])
        if "param_drop_seven_eight" in config:
            strat_kwargs["drop_on_seven_eight"] = bool(config["param_drop_seven_eight"])
        if "param_fail_safety_limit" in config:
            strat_kwargs["fail_safety_limit"] = int(config["param_fail_safety_limit"])

    strategy = get_strategy(mode, stage=load_daily_stage(), **strat_kwargs)
    if strategy.complete:
        print(tr('phased_completed'))
        return
    counter = HighLowCounter()
    card_rec = CardRecognizer(TEMPLATE_DIR)
    daily_coins, daily_fails = load_daily_data()
    net_profit = daily_coins - (daily_fails * ticket_cost)
    print(tr('start_bot', coins=daily_coins, fails=daily_fails, profit=net_profit))
    if on_stats_update:
        on_stats_update(daily_coins, daily_fails, net_profit)

    reward_reader = ChallengeRewardReader()
    settlement_mgr = SettlementManager(
        SettlementReader(timeout=ocr_timeout),
        save_data_fn=save_daily_data,
        recovery_mode=recovery_mode,
        on_prompt_settlement=on_prompt_settlement,
    )
    # Ensure settlement manager is fresh on each bot start to avoid stale has_tallied preventing credit on resume
    settlement_mgr.reset_round(strategy)
    pending_cash = load_pending_cashout()
    if pending_cash:
        settlement_mgr.expected_cashout = pending_cash

    has_recorded_fail = False  # Prevent duplicate fee deduction during FAIL animation
    has_confirmed_success = False  # Prevent duplicate success count during multi-frame ASK_CHALLENGE prompt

    def request_cashout(frame, left, top, cash):
        if find_and_click_icon(frame, TPL_CASHOUT, left, top):
            settlement_mgr.expected_cashout = cash
            save_pending_cashout(cash)
            return True
        return False

    while daily_coins < target_limit and bot_running:
        img, win_left, win_top = capture_game_window()
        if img is None:
            print(tr('window_not_found'))
            time.sleep(1)
            continue

        current_state = detect_game_state(img)

        # Only a new round resets accounting; UNKNOWN may be a result flicker.
        if current_state in ("START_BET", "HOLD_CARDS"):
            settlement_mgr.reset_round(strategy)
            reward_reader.reset_round()
            has_confirmed_success = False
            clear_pending_cashout()
        elif current_state in ('HIGH_LOW', 'FAIL', 'RESULT'):
            reward_reader.reset_prompt()
            has_confirmed_success = False
        if current_state != "FAIL":
            has_recorded_fail = False


        if current_state == "UNKNOWN":
            time.sleep(0.5)
            continue

        if current_state == "FULL":
            print(tr('state_full'))
            break

        if current_state == "START_BET":
            print(tr('state_start_bet'))
            counter.reset()
            upcoming_card_val = None

            # Try clicking Start icon for current language
            for tpl in ICON_TEMPLATES["START_BET"]:
                if find_and_click_icon(img, tpl, win_left, win_top):
                    break
            time.sleep(1)

        elif current_state == "HOLD_CARDS":
            print(tr('state_hold_cards'))
            recognized_cards, rects = card_rec.recognize(img)
            if len(recognized_cards) == 5:
                hand_ids = [c.card_id for c in recognized_cards]
                card_values = [get_card_point_value(c) for c in recognized_cards if c.card_id != JOKER_ID]
                counter.remove_cards(card_values)

                best, _ = calculate_best(hand_ids, "standard")

                for idx in best.held_indices:
                    x, y, w_box, h_box = rects[idx]
                    safe_click(x + w_box // 2, y + h_box // 2, win_left, win_top)
                    time.sleep(0.15)

                time.sleep(0.3)
                find_and_click_icon(img, TPL_REPLACE, win_left, win_top)
                time.sleep(1)

        elif current_state == "TAP_TO_PROCEED":
            h, w = img.shape[:2]
            safe_click(w // 2, h // 2, win_left, win_top)
            time.sleep(0.6)

        elif current_state == "ASK_CHALLENGE":
            if getattr(strategy, "base_cash", None) is None:
                if is_success_prompt(img):
                    raise RuntimeError('Currently mid-doubling, cannot recover win count. Please start from a fresh round.')
                real_reward = read_challenge_payout(img, REWARD_ZONE)
                next_reward = reward_reader.observe(real_reward, time.monotonic())
                if next_reward is None:
                    time.sleep(0.25)
                    continue
                current_cashout = next_reward // 2
                try:
                    strategy.start_round(current_cashout, daily_coins)
                except RuntimeError as e:
                    if hasattr(strategy, 'stage') and strategy.stage == 1:
                        # Auto-advance to stage 2 (Sprint) so bot doesn't crash on high poker hands
                        strategy.stage = 2
                        strategy.reset_round()
                        strategy.start_round(current_cashout, daily_coins)
                    else:
                        raise
            else:
                if is_success_prompt(img) and not has_confirmed_success:
                    strategy.confirm_success()
                    has_confirmed_success = True

                if getattr(strategy, "requires_ongoing_ocr", True):
                    real_reward = read_challenge_payout(img, REWARD_ZONE)
                    next_reward = reward_reader.observe(real_reward, time.monotonic())
                    if next_reward is None:
                        time.sleep(0.25)
                        continue
                    current_cashout = next_reward // 2
                else:
                    current_cashout = strategy.expected_cash or 0
                    next_reward = current_cashout * 2

            if upcoming_card_val is not None:
                _, win_rate = counter.get_best_choice_and_rate(upcoming_card_val)
                print(tr('risk_prediction', rate=win_rate))
            else:
                win_rate = 1.0
                print(tr('risk_blind'))

            action = strategy.decide(current_cashout, next_reward, win_rate, daily_coins)

            # Opportunistic high-chance card continuation override (when safely under daily target limit)
            if action == 'cashout' and upcoming_card_val is not None:
                runtime_config = load_config()
                opp_mode = runtime_config.get("opportunistic_double_mode", "a_2_only")
                opp_a2 = runtime_config.get("opp_a2", opp_mode in ("a_2_only", "include_3_k", "include_4_q"))
                opp_3k = runtime_config.get("opp_3k", opp_mode in ("include_3_k", "include_4_q"))
                opp_4q = runtime_config.get("opp_4q", opp_mode == "include_4_q")

                should_double = False
                if upcoming_card_val in (2, 14) and opp_a2:
                    should_double = True
                elif upcoming_card_val in (3, 13) and opp_3k:
                    should_double = True
                elif upcoming_card_val in (4, 12) and opp_4q:
                    should_double = True

                if should_double and (daily_coins + next_reward < target_limit):
                    action = 'challenge'
                    if hasattr(strategy, 'last_cashout'):
                        strategy.last_cashout = None
                    rank_name = {2: "2", 3: "3", 4: "4", 12: "Q", 13: "K", 14: "A"}.get(upcoming_card_val, str(upcoming_card_val))
                    print(tr('opportunistic_double_msg', rank=rank_name, rate=win_rate, reward=next_reward, limit=target_limit))

            if hasattr(strategy, 'stage') and hasattr(strategy, 'target_wins'):
                goal = (tr('phased_target_auto') if strategy.target_wins is None
                        else tr('phased_target_wins', wins=strategy.target_wins))
                action_text = tr('action_cashout') if action == 'cashout' else tr('action_continue')
                print(tr('phased_round_status', stage=strategy.stage + 1, successes=getattr(strategy, 'successes', 0), goal=goal, action=action_text))
            else:
                print(tr('challenge_current', cashout=current_cashout, reward=next_reward))
                if hasattr(strategy, 'last_reason') and strategy.last_reason:
                    meta = getattr(strategy, 'last_meta', {})
                    reason_text = tr(strategy.last_reason, **meta)
                    print(reason_text if reason_text != strategy.last_reason else f"[{strategy.name}] {strategy.last_reason}")

            effective_cash = strategy.expected_cash or current_cashout
            if action == 'cashout':
                request_cashout(img, win_left, win_top, effective_cash)
            else:
                find_and_click_icon(img, TPL_CONFIRM_DOUBLE, win_left, win_top, threshold=0.55)

            time.sleep(0.6)
        elif current_state == "HIGH_LOW":
            if getattr(strategy, "base_cash", None) is None and hasattr(strategy, "successes"):
                raise RuntimeError('Currently mid-doubling, cannot recover win count. Please start from a fresh round.')
            try:
                # 1. Detect all white face-up cards with new engine
                rects = find_all_card_rects(img, HIGH_LOW_SEARCH_ZONE)

                if rects:
                    # Sort by X coordinate to get the rightmost face-up card
                    rects.sort(key=lambda r: r[0])
                    current_rect = rects[-1]

                    old_right_x = current_rect[0]

                    single_card = card_rec.recognize_card(img, current_rect)
                    if single_card.card_id != JOKER_ID:
                        current_card_val = get_card_point_value(single_card)
                        counter.remove_cards([current_card_val])
                        best_choice, rate = counter.get_best_choice_and_rate(current_card_val)

                        print(tr('visible_card_choice', rank=single_card.rank, choice=best_choice.upper(), rate=rate))

                        if best_choice == "high":
                            guessed = find_and_click_icon(img, TPL_HIGH, win_left, win_top)
                        else:
                            guessed = find_and_click_icon(img, TPL_LOW, win_left, win_top)
                        if strategy is not None and guessed:
                            strategy.guess_clicked()

                        # === 2. Continuous State Tracking & Burst Capture ===
                        print(tr('tracking_start'))
                        upcoming_card_val = None
                        DEBUG_DIR.mkdir(exist_ok=True)
                        candidate_card = None
                        stable_count = 0

                        for i in range(25):
                            time.sleep(0.04)
                            flip_img, _, _ = capture_game_window()

                            if flip_img is not None:
                                try:
                                    new_rects = find_all_card_rects(flip_img, HIGH_LOW_SEARCH_ZONE)
                                    if new_rects:
                                        # Get rightmost white card from burst frames
                                        new_rects.sort(key=lambda r: r[0])
                                        newest_rect = new_rects[-1]

                                        # Core check: if rightmost card X increases by > 50px,
                                        # indicates a new card flipped face-up
                                        if newest_rect[0] > old_right_x + 50:
                                            newest_card = card_rec.recognize_card(flip_img, newest_rect)
                                            # Require minimum confidence to avoid capturing mid-flip blur
                                            if (newest_card.card_id != JOKER_ID
                                                    and getattr(newest_card, 'rank_score', 1.0) >= 0.65):
                                                if candidate_card is not None and candidate_card.rank == newest_card.rank:
                                                    stable_count += 1
                                                else:
                                                    candidate_card = newest_card
                                                    stable_count = 1

                                                # Accept immediately if high confidence, or require 2 stabilized frames
                                                if stable_count >= 2 or getattr(newest_card, 'rank_score', 0) >= 0.80:
                                                    upcoming_card_val = get_card_point_value(newest_card)
                                                    print(tr('tracking_found', frame=i + 1, rank=newest_card.rank))

                                                    cx, cy, cw, ch = newest_rect
                                                    cv2.imwrite(str(DEBUG_DIR / "2_next_card.png"),
                                                                flip_img[max(0, cy - 40):cy + ch + 40,
                                                                max(0, cx - 40):cx + cw + 40])
                                                    break
                                except Exception:
                                    continue

                        if upcoming_card_val is None:
                            print(tr('tracking_timeout'))

                        time.sleep(0.6)
                else:
                    print(tr('warn_no_cards'))
            except Exception as e:
                print(tr('err_high_low', error=e))

        elif current_state == "FAIL":
            clear_pending_cashout()
            if not has_recorded_fail:
                daily_fails += 1
                loss = daily_fails * ticket_cost
                net_profit = daily_coins - loss
                save_daily_data(daily_coins, daily_fails)
                print(tr('fail_summary', fails=daily_fails, loss=loss, profit=net_profit))
                if on_stats_update:
                    on_stats_update(daily_coins, daily_fails, net_profit)
                if strategy is not None:
                    strategy.begin_settlement(cashout_requested=False)
                has_recorded_fail = True

            time.sleep(0.8)
            find_and_click_icon(img, TPL_CONFIRM_DOUBLE, win_left, win_top, threshold=0.55)
            time.sleep(1)

        elif current_state == "RESULT":
            amount = read_settlement_payout(img, RESULT_REWARD_ZONE, expected=settlement_mgr.expected_cashout)
            daily_coins, can_proceed = settlement_mgr.process_result(
                amount=amount,
                now=time.monotonic(),
                daily_coins=daily_coins,
                daily_fails=daily_fails,
                strategy=strategy,
                on_stats_update=on_stats_update,
                ticket_cost=ticket_cost,
                on_prompt_settlement=on_prompt_settlement,
            )
            if not can_proceed:
                time.sleep(0.2)
                continue

            clear_pending_cashout()
            time.sleep(0.8)
            find_and_click_icon(img, TPL_CONFIRM_DOUBLE, win_left, win_top, threshold=0.55)
            time.sleep(1)
            if strategy is not None and strategy.complete:
                print(tr('phased_all_done'))
                break

    if daily_coins >= target_limit:
        print(tr('state_full'))


if __name__ == "__main__":
    auto_play_loop()
