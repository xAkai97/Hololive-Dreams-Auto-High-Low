# Hololive Dreams Auto Bot

An advanced automated assistant, card-counting engine, and simulation suite for the casino mini-game in *Hololive Dreams*. Features Numba JIT accelerated poker hand optimization, dynamic High-Low odds tracking, 7 modular doubling policies with strategy modifiers, OCR self-healing, and an extensible multilingual GUI.

---

## ✨ Key Features

- **Optimal Hand Selection**: Powered by Numba JIT acceleration to evaluate initial poker hands and hold the mathematically optimal card combinations.
- **Dynamic Card Counting**: Tracks remaining cards across the 52-card deck during the High-Low phase (and 53-card deck with Joker in poker), accurately factoring in equal-rank tie-losses to calculate exact real-time winning probabilities.
- **Multi-Resolution & High-DPI Support**: Native support for any display resolution (720p, 1080p, 1440p / 2K, 2160p / 4K) and Windows display scaling (100%–200%+). Automatically normalizes frames using Per-Monitor DPI V2 awareness and area-averaged anti-aliasing, with proportional subpixel mouse click mapping.
- **Smart Cushion & Sprint Mechanics**:
  - **Cushion Phase**: Automatically cashes out when odds are unfavorable to steadily build bankroll toward 19,800 without prematurely crossing the 20,000 daily cap.
  - **Sprint Phase**: Unlocks aggressive play once total coins reach 19,800, pushing for 10,000+ coins in a single final run for maximum daily profit (~29k-32k).
- **Strategy Modifiers Drawer & Mutual Exclusion**:
  - **Strategic Overrides**: Fast Build (double to cushion limit), Free-Roll (bankroll safety), Sprint Floor ($\ge 11,200$), and Mega Sprint Floor ($\ge 12,800$).
  - **Defensive Bailouts**: Middle-card protection against volatility (Bail on 8, Bail on 7/8, Bail on 6/7/8/9).
  - **Card Overrides**: Opportunistic doubling overrides for high-value cards (A/2, 3/K, 4/Q, 5/J, 6/10, 7/9, 8) with strict daily cap lockout prevention guard ($< 20,000$).
  - **Intelligent Mutual Exclusion**: Automatically prevents contradictory modifier combinations directly in the UI.
- **Automated Daily Rollover**: Synchronized with the 4:00 PM EST daily reset cycle to seamlessly reset session counters and data without manual intervention.
- **Interactive Tooltips**: Built-in hover tooltips explaining every setting and modifier in detail across all supported languages.
- **Custom Backgrounds**: Drop any `.png`, `.jpg`, or `.webp` into `backgrounds/`. The bot auto-detects them and lets you cycle through them directly from the UI.
- **Extensible Multilingual Support**: Built-in support for English, Simplified Chinese, Traditional Chinese, and Japanese. Custom translation files can be dropped directly into `locales/`.
- **Profit & Loss Tracking**: Tracks failed runs and ticket fees (50 coins/entry), calculating net profit in real time.
- **Global Stop Hotkey**: Supports customizable hotkeys (default `INSERT`) to safely halt automation at any time.

---

## 📁 Project Structure

```text
├── main_ui.py                 # Main application graphical launcher
├── requirements.txt           # Python dependencies
├── Hololive Dreams-Auto.spec  # PyInstaller packaging configuration
├── src/                       # Core engine and decision-making logic
│   ├── auto_bot.py            # Main automation loop and game control
│   ├── window_control.py      # Multi-resolution DPI-aware capture and click manager
│   ├── simulation.py          # Offline Monte Carlo simulation and benchmark engine
│   ├── localization.py        # Dynamic language registry and translation helper
│   ├── poker_core.py          # Numba JIT accelerated hand strategy solver
│   ├── strategies/            # 7 modular doubling policy engines & modifiers
│   │   ├── base.py            # BaseStrategy abstract interface
│   │   ├── max_profit.py      # Max profit ~29-32k cushion/sprint policy
│   │   ├── fastest_clear.py   # Speedrun all-or-nothing policy
│   │   ├── balanced.py        # Moderate risk ~25k policy
│   │   ├── aggressive_balanced.py # Aggressive ~28k policy
│   │   ├── adaptive_rush.py   # Auto-downshifting rush policy
│   │   ├── grinder.py         # Ultra-safe conservative policy
│   │   ├── custom_parametric.py # User-tunable parametric policy
│   │   └── modifiers.py       # Fast Build, Sprint Floor, Bail 7/8, Opportunistic overrides
│   ├── challenge_reward.py    # Challenge payout validation and stabilization
│   ├── settlement.py          # Settlement balance verification & recovery
│   └── reward_vision.py       # Real-time challenge bonus OCR
├── config.json                # User settings, window coordinates, and daily stats (auto-generated)
├── log.txt                    # Active UI session log (auto-generated)
├── logs/                      # Archived session logs rotated on launch (auto-generated)
├── backgrounds/               # Drop custom background images here (.png, .jpg, etc.)
├── assets/                    # Application icons and static assets
├── locales/                   # External JSON translations (en.json, zh.json, ja.json, tw.json)
├── templates/                 # Game recognition templates
├── docs/                      # Documentation and detailed strategy guides
│   └── strategies.md          # Comprehensive 7-strategy guide & modifiers
└── tests/                     # Unit test suite
```

---

## 🛠️ Running from Source

### Prerequisites
- Python 3.10+ (tested through 3.14)
- Windows OS (game window scaling and background capture support)

```bash
git clone https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low.git
cd Hololive-Dreams-Auto-High-Low
pip install -r requirements.txt
python main_ui.py
```

---

## 🚀 Building Standalone Executable (.exe)

Install dependencies:
```powershell
python -m pip install -r requirements.txt
```

Run the automated 1-click build script:
```powershell
# In PowerShell:
./build.ps1

# Or in Command Prompt:
build.bat
```

*(Alternatively, you can run manually: `python -m PyInstaller -y --workpath "$env:TEMP\pyi_build" --distpath "$env:TEMP\pyi_dist" "Hololive Dreams-Auto.spec"`).*

> [!TIP]
> The automated build script works universally across local drives, external disks, and network/SMB shares by compiling temporary artifacts on the local disk to prevent file-locking.

The standalone output package will be created in `dist/Hololive-Dreams-Auto/`. Keep the entire folder together (including `_internal/`, `backgrounds/`, `assets/`, and `locales/`); do not move the `.exe` alone.

---

## 🎨 Custom Backgrounds

To customize the interface appearance:
1. Drop your favorite image (`.png`, `.jpg`, `.jpeg`, `.bmp`, or `.webp`) into the `backgrounds/` folder.
2. Launch the application.
3. If multiple images exist, clicking the **"Background"** button in the UI cycles through each image or turns off the background.

---

## 🌐 Custom Translations

To add a new language or modify existing strings:
1. Navigate to the `locales/` folder.
2. Copy an existing file (e.g. `en.json`) and name it with your locale code (e.g. `ko.json`, `es.json`).
3. Set `"language_name"` (e.g. `"한국어"`) and translate the values.
4. Restart the bot — the new language will automatically appear in the UI dropdown.

---

## 💾 Data & Storage Locations

The application operates in **Portable Mode** by default and automatically falls back to **AppData** if running from a protected directory:

| Mode | Location | When Used |
| :--- | :--- | :--- |
| **Portable Mode** *(Default)* | Application folder (`config.json`, `log.txt`, `logs/`) | Default behavior when the folder has write permissions (e.g. running from source or extracted portable `.exe`). |
| **AppData Fallback** | `%APPDATA%\HololiveDreamsAuto\` | Automatically engaged if the application folder is write-protected or read-only (e.g. installed under `C:\Program Files\`). |

### Generated Files & Folders
- `config.json`: Stores user preferences (language, hotkeys, strategy selection, strategy modifiers toggles, log retention settings, and daily coin stats).
- `log.txt`: Active session execution log. You can view or export this from the **Logs** menu bar.
- `logs/`: Timestamped archives of previous sessions (`log_YYYY-MM-DD_HH-MM-SS.txt`), automatically rotated on launch and pruned according to your configured retention settings (default: 14 days or 20 MB).
- `debug/`: Debug screenshots captured during vision or OCR failures (when debug mode is active).

---

## 📖 Instructions

1. Launch *Hololive Dreams* and ensure the game window is not minimized to the taskbar (it can be obscured or running behind other windows).
2. Ensure the game is running in a standard **16:9 aspect ratio** (e.g. 1280x720, 1920x1080, 2560x1440, or 3840x2160 in windowed or fullscreen mode). Displays with custom Windows DPI scaling (125%, 150%, 200%) are supported out of the box.
3. Launch the bot and configure your preferred language and stop hotkey.
4. Select your desired strategy mode and click **"Start Bot"**.
5. Press your configured stop hotkey at any time to safely halt automation.

---

## 🙏 Credits & Acknowledgments

This project originated as an enhanced extension of foundational automation work created by the open-source community:

- **Original Project & Concept**: [mwty-0415/Hololive-Dreams-Auto-High-Low](https://github.com/mwty-0415/Hololive-Dreams-Auto-High-Low) by [mwty-0415](https://github.com/mwty-0415) (Bilibili: [hmr0000](https://space.bilibili.com/519062381) / YouTube: [@hmr0000](https://www.youtube.com/@hmr0000)) for the initial game automation architecture and High-Low core.
- **Computer Vision & Strategy Insights**: [harrykuang-dev/Hololive-Dreams-Auto-High-Low](https://github.com/harrykuang-dev/Hololive-Dreams-Auto-High-Low) by [harrykuang-dev](https://github.com/harrykuang-dev) for OCR enhancements and diagnostic insights.
- **Poker Card Recognition & Hand Solver**: [Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper) by [Oreki0504](https://github.com/Oreki0504) for card recognition templates and poker hand evaluation logic.

All original copyrights and licenses are respected and retained.

---

## ⚠️ Disclaimer

- This tool is developed strictly for educational, computer vision, and automation research purposes.
- Do not use this tool for commercial purposes or in ways that compromise fair play. The developers assume no liability for any issues arising from its use.
