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
ERROR_TRANSLATIONS: dict[str, dict[str, str]] = {}


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

    Translations, strategy labels, and error messages are loaded directly from JSON files
    in the 'locales' directory (e.g. en.json, zh.json, tw.json, ja.json). Users can add new
    translations or edit existing ones without touching Python code.
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
                if isinstance(v, str) and k not in ("language_name", "strategy_labels", "error_translations"):
                    TRANSLATIONS[lang_code][k] = v

            error_translations = data.get("error_translations")
            if error_translations and isinstance(error_translations, dict):
                for pattern, msg in error_translations.items():
                    if pattern not in ERROR_TRANSLATIONS:
                        ERROR_TRANSLATIONS[pattern] = {}
                    ERROR_TRANSLATIONS[pattern][lang_code] = str(msg)
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


def format_error(error: Exception | str, lang: str | None = None) -> str:
    err_str = str(error)
    active_lang = lang or _current_lang
    for pattern, mapping in ERROR_TRANSLATIONS.items():
        if pattern in err_str:
            return mapping.get(active_lang, mapping.get("en", err_str))
    return err_str


# Automatically load all locale JSON files from the locales directory on module import
load_external_locales()
