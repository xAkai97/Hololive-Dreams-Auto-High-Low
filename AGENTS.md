# Project Overview
Automated 5-Card Draw poker solver, High-Low card-counting bot, zero-click Observer Mode companion, and Monte Carlo strategy simulator for the *Hololive Dreams* mini-game on Windows.

## Commands
- **Environment**: Windows PowerShell (`pwsh`), Python 3.10–3.14 (`$py = (py -3.14 -c "import sys;print(sys.executable)")`). Reuse the active interpreter; do not create a `.venv` if one exists.
- **Run App**: `& $py main_ui.py`
- **Test** (mandatory before committing): `& $py -m unittest discover tests`
- **Simulate / Benchmark**: `& $py src/simulation.py --compare-all`
- **Build Executable**: `./build.ps1 -PythonPath $py` (or `build.bat`)

## References (Progressive Disclosure)
- **Game Mechanics, Strategies & Modifiers**: See `docs/strategies.md`.
- **Combinatorial Poker Solver, Tie-Push Math & Vision Pipeline**: See `docs/ALGORITHMS.md`.

## Code Standards
- **Line Endings**: Enforce LF (`\n`) on all `.py` files (`.gitattributes`).
- **Localization Parity**: Every key and `{placeholder}` in `locales/en.json` must match across `zh.json`, `tw.json`, and `ja.json` (verified by `tests/test_localization.py`).
- **Thread & UI Safety**: `main_ui.py` runs Tkinter on the main thread; background threads (`src/auto_bot.py`, `src/simulation.py`) must dispatch UI/log updates via `self._ui_queue` or `after()`.
- **Canvas Widgets**: Custom canvas controls in `src/ui/widgets.py` (`CanvasHeaderLabel`, `CanvasSegmentedPill`, `CanvasCheckbutton`) must guard redraws with `self._visible` to prevent off-tab ghost rendering at `(0, 0)`.

## Guardrails
- **Never hardcode screen pixel coordinates**: All captures and clicks must pass through `src/window_control.py` normalized to `1920x1080` reference bounds.
- **Zero-Click Observer Invariant**: When `scan_mode` is `True`, `safe_click` and all state handlers in `src/auto_bot.py` must never dispatch mouse clicks.
- **Test Isolation**: Unit tests must mock config/log writes (`save_daily_data`, `save_pending_cashout`, `LOGS_DIR`) so running tests never mutates live `config.json` or prunes `logs/`.
