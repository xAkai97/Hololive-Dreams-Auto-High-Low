"""Centralized localization strings and translation helper for Hololive Dreams Auto Bot."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_LANG = "en"
_current_lang = DEFAULT_LANG

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "zh": "简体中文",
    "tw": "繁體中文",
    "ja": "日本語",
}

STRATEGY_LABELS: dict[str, tuple[str, str]] = {}
TRANSLATIONS: dict[str, dict[str, str]] = {}


def set_lang(lang: str) -> None:
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_lang() -> str:
    return _current_lang


def get_locales_dir() -> Path:
    app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    resource_dir = Path(getattr(sys, "_MEIPASS", app_dir)).resolve()
    for candidate in [app_dir / "locales", resource_dir / "locales", Path(__file__).resolve().parent / "locales", Path("locales").resolve()]:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return app_dir / "locales"


def load_external_locales(locales_dir: Path | str | None = None) -> list[tuple[str, str]]:
    """Scan and load external JSON translation files.

    Translations and strategy labels are loaded directly from JSON files in the 'locales'
    directory (e.g. en.json, zh.json, tw.json, ja.json). Users can add new translations
    or edit existing ones without touching Python code.
    """
    target_dir = Path(locales_dir) if locales_dir else get_locales_dir()
    if not target_dir.exists() or not target_dir.is_dir():
        return get_available_languages()

    for file_path in target_dir.glob("*.json"):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            lang_code = file_path.stem.lower()
            lang_name = data.get("language_name", LANGUAGE_NAMES.get(lang_code, lang_code))
            LANGUAGE_NAMES[lang_code] = lang_name

            strategy_labels = data.get("strategy_labels")
            if strategy_labels and isinstance(strategy_labels, (list, tuple)) and len(strategy_labels) >= 2:
                STRATEGY_LABELS[lang_code] = (str(strategy_labels[0]), str(strategy_labels[1]))
            elif lang_code not in STRATEGY_LABELS:
                STRATEGY_LABELS[lang_code] = STRATEGY_LABELS.get("en", ("1.0.1 Legacy", "3 Stages: Max → Win Count → Max"))

            translations = data.get("translations", data)
            if lang_code not in TRANSLATIONS:
                TRANSLATIONS[lang_code] = {}
            for k, v in translations.items():
                if isinstance(v, str) and k != "language_name":
                    TRANSLATIONS[lang_code][k] = v
        except Exception as exc:
            print(f"[i18n] Failed to load locale {file_path.name}: {exc}")

    return get_available_languages()


def get_available_languages() -> list[tuple[str, str]]:
    """Return sorted list of (lang_code, display_name) with built-in languages first."""
    builtin_order = ["en", "zh", "tw", "ja"]
    result = []
    for code in builtin_order:
        if code in TRANSLATIONS:
            result.append((code, LANGUAGE_NAMES.get(code, code)))
    for code, name in sorted(LANGUAGE_NAMES.items()):
        if code not in builtin_order and code in TRANSLATIONS:
            result.append((code, name))
    return result


def tr(_key: str, _lang: str | None = None, **kwargs) -> str:
    active_lang = _lang or _current_lang
    bundle = TRANSLATIONS.get(active_lang, {})
    template = bundle.get(_key)
    if template is None:
        template = TRANSLATIONS.get("en", {}).get(_key)
    if template is None:
        template = TRANSLATIONS.get(DEFAULT_LANG, {}).get(_key, _key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


ERROR_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Settlement amount could not be confirmed": {
        "en": "Settlement amount could not be reliably confirmed.",
        "zh": "结算金额未能稳定确认，已停止且未将此笔入账。",
        "tw": "結算金額未能穩定確認，已停止且未將此筆入帳。",
        "ja": "精算金額を安定して確認できませんでした。",
    },
    "Challenge payout cannot be confirmed": {
        "en": "Challenge payout could not be confirmed.",
        "zh": "挑战奖金无法确认，已停止。",
        "tw": "挑戰獎金無法確認，已停止。",
        "ja": "挑戦賞金を確認できませんでした。",
    },
    "Currently mid-doubling": {
        "en": "Currently mid-challenge; cannot recover round count. Please restart from a fresh round.",
        "zh": "当前已在翻倍途中，无法恢复本局成功次数。请从新一局开始。",
        "tw": "當前已在翻倍途中，無法恢復本局成功次數。請從新一局開始。",
        "ja": "現在ダブルアップの途中のため、成功回数を復元できません。新しい対局からやり直してください。",
    },
    "Missing doubling history": {
        "en": "Missing doubling history for this round. Please check manually.",
        "zh": "缺少本局翻倍记录，无法核对入账。请手动核对后开始新一局。",
        "tw": "缺少本局翻倍紀錄，無法核對入帳。請手動核對後開始新一局。",
        "ja": "本局のダブルアップ記録がないため照合できません。手動で確認してください。",
    },
    "Initial payout for this round cannot reserve cap room": {
        "en": "Initial prize cannot preserve the 3rd stage, please handle manually.",
        "zh": "本局起手奖金已无法保留第三阶段，请手动处理。",
        "tw": "本局起手獎金已無法保留第三階段，請手動處理。",
        "ja": "本局の初期賞金では第3段階を保持できません。手動で対応してください。",
    },
    "Unexpected game client area size": {
        "en": "Unexpected game client dimensions.",
        "zh": "游戏客户区尺寸异常。",
        "tw": "遊戲客戶區尺寸異常。",
        "ja": "ゲームクライアントのサイズが異常です。",
    },
    "结算金额未能稳定确认": {
        "en": "Settlement amount could not be stably confirmed.",
        "ja": "精算金額を安定して確認できませんでした。",
    },
    "挑战奖金无法确认": {
        "en": "Challenge reward could not be confirmed.",
        "ja": "挑戦賞金を確認できませんでした。",
    },
    "当前已在翻倍途中": {
        "en": "Currently mid-challenge; cannot recover round count. Please restart from a fresh round.",
        "ja": "現在ダブルアップの途中のため、成功回数を復元できません。新しい対局からやり直してください。",
    },
    "缺少本局翻倍记录": {
        "en": "Missing doubling history for this round. Please check manually.",
        "ja": "本局のダブルアップ記録がないため照合できません。手動で確認してください。",
    },
    "本局起手奖金已无法保留第三阶段": {
        "en": "Initial prize cannot preserve the 3rd stage, please handle manually.",
        "ja": "本局の初期賞金では第3段階を保持できません。手動で対応してください。",
    },
    "游戏客户区尺寸异常": {
        "en": "Abnormal game client dimensions.",
        "ja": "ゲームクライアントのサイズが異常です。",
    },
}


def format_error(error: Exception | str, lang: str | None = None) -> str:
    err_str = str(error)
    active_lang = lang or _current_lang
    for pattern, mapping in ERROR_TRANSLATIONS.items():
        if pattern in err_str:
            return mapping.get(active_lang, mapping.get("en", err_str))
    return err_str


# Automatically load all locale JSON files from the locales directory on module import
load_external_locales()
