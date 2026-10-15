# Hololive Dreams Auto Bot

An advanced automated assistant, card-counting engine, and simulation suite for the casino mini-game in *Hololive Dreams*. Features Numba JIT accelerated poker hand optimization, dynamic High-Low odds tracking, 7 modular doubling policies with strategy modifiers, OCR self-healing, and an extensible multilingual GUI.

---

## ✨ Key Features

- **Optimal Hand Selection**: Powered by Numba JIT acceleration to evaluate initial poker hands and hold the mathematically optimal card combinations.
- **Dynamic Card Counting**: Tracks remaining cards across the 52-card deck during the High-Low phase (and 53-card deck with Joker in poker), accurately factoring in equal-rank tie pushes (re-rolls) to calculate exact real-time winning probabilities.
- **Multi-Resolution & High-DPI Support**: Native support for any display resolution (720p, 1080p, 1440p / 2K, 2160p / 4K) and Windows display scaling (100%–200%+). Automatically normalizes frames using Per-Monitor DPI V2 awareness and area-averaged anti-aliasing, with proportional subpixel mouse click mapping.
- **Smart Cushion & Sprint Mechanics**:
  - **Cushion Phase**: Automatically cashes out when odds are unfavorable to steadily build bankroll toward 19,800 without prematurely crossing the 20,000 daily cap.
  - **Sprint Phase**: Unlocks aggressive play once total coins reach 19,800, pushing for 10,000+ coins in a single final run for maximum daily profit (~29k-32k).
- **Strategy Modifiers Drawer with Collapsible Categories**:
  - **Progression & Sprint**: Fast Build (double to cushion limit), Free-Roll (double on 200 or less), Sprint Floor (11.2k+), and Mega Sprint Floor (12.8k+).
  - **Defensive Bailouts**: Middle-card protection against volatility under 19.8k cushion (Bail on 8 only, Bail on 7/8, Bail on 6/7/8/9).
  - **Card Overrides**: Opportunistic doubling overrides for high-value cards (A/2, 3/K, 4/Q, 5/J, 6/10, 7/9, 8) with strict daily cap lockout prevention guard ($< 20,000$).
  - **Interactive Drawer**: Each modifier category can be collapsed or expanded independently (`▼` / `▶`) with persistent state saving and dynamic container resizing.
  - **Intelligent Mutual Exclusion**: Automatically prevents contradictory modifier combinations directly in the UI.
- **Unified Start & Stop Control**: Modern full-width toggle button with dynamic state switching between Start Bot and glowing red Stop Bot.
- **Multilingual Fonts & Dynamic Scaling**: Locale-aware typography adaptation (Chinese, Japanese, English) with manual font overrides and dynamic UI font scale slider (80% to 130%).
- **Glassmorphic UI & Field Box Opacity**: Real-time PIL alpha-blended frosted glass styling across stats and settings cards with customizable opacity (0% to 100%) and clean plain default background.
- **Integrated Help & Documentation**: Instant access to verified game rules, paytables, cap overflow guides, online GitHub documentation, and local Markdown references directly from the Help menu.
- **Automated Daily Rollover**: Synchronized with the 4:00 PM EST daily reset cycle to seamlessly reset session counters and data without manual intervention.
- **Interactive Tooltips**: Built-in hover tooltips explaining every setting and modifier in natural, accessible language across English, Simplified Chinese, Traditional Chinese, and Japanese.
- **Custom Backgrounds**: Drop any `.png`, `.jpg`, or `.webp` into `backgrounds/`. The bot auto-detects them and lets you cycle through them directly from the UI.
- **Profit & Loss Tracking**: Tracks failed runs and ticket fees (50 coins/entry), calculating net profit in real time.
- **Global Stop Hotkey**: Supports customizable hotkeys (default `INSERT`) to safely halt automation at any time.

---

## 📁 Project Structure

```text
├── AGENTS.md                  # Development guide & system context for AI coding assistants
├── main_ui.py                 # Main application graphical launcher
├── build.ps1                  # 1-click automated PowerShell packaging script
├── build.bat                  # 1-click automated Command Prompt packaging script
├── requirements.txt           # Core runtime dependencies
├── requirements-build.txt     # Packaging & PyInstaller dependencies
├── LICENSE                    # MIT License
├── THIRD_PARTY_NOTICES.md     # Upstream open-source attribution
├── Hololive Dreams-Auto.spec  # PyInstaller packaging configuration
├── src/                       # Core engine and decision-making logic
│   ├── auto_bot.py            # Main automation loop and game control
│   ├── window_control.py      # Multi-resolution DPI-aware capture and click manager
│   ├── recognizer.py          # Multi-scale OpenCV template matching card & icon recognizer
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
│   │   └── modifiers.py       # Fast Build, Sprint Floor, Bailouts, Opportunistic overrides
│   ├── challenge_reward.py    # Challenge payout validation and stabilization
│   ├── settlement.py          # Settlement balance verification & recovery
│   ├── reward_vision.py       # Real-time challenge bonus OCR
│   └── ui/                    # Modular GUI framework (ModernMenu, widgets, dialogs)
├── config.json                # User settings, window coordinates, and daily stats (auto-generated)
├── log.txt                    # Active UI session log (auto-generated)
├── logs/                      # Archived session logs rotated on launch (auto-generated)
├── backgrounds/               # Drop custom background images here (.png, .jpg, etc.)
├── assets/                    # Application icons and static assets
├── locales/                   # External JSON translations (en.json, zh.json, ja.json, tw.json)
├── templates/                 # Game recognition templates
├── tools/                     # Development utilities & calibration helpers
├── docs/                      # Documentation and detailed technical guides
│   ├── strategies.md          # Comprehensive 7-strategy guide & modifiers
│   └── ALGORITHMS.md          # Mathematical formulas, probability models & Numba solver
└── tests/                     # 18 unit & integration test files (154 tests)
```

---

## 🛠️ Running from Source

### Prerequisites
- Python 3.10+ (tested through 3.14)
- Windows OS (game window scaling and background capture support)

```powershell
git clone https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low.git
cd Hololive-Dreams-Auto-High-Low
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main_ui.py
```

---

## 🚀 Building Standalone Executable (.exe)

Install dependencies:
```powershell
python -m pip install -r requirements-build.txt
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

## 🌐 Custom Translations & In-Game Language Support

### Adding Bot UI Translations
To translate the bot interface into a new language:
1. Navigate to the `locales/` folder.
2. Copy an existing file (e.g. `en.json`) and name it with your locale code (e.g. `ko.json`, `es.json`).
3. Set `"language_name"` (e.g. `"한국어"`) and translate the string values.
4. Restart the bot — the new language will automatically appear in the UI dropdown.

> [!IMPORTANT]
> **In-Game Language Requirement**:
> While *Hololive Dreams* provides 6 language options, the bot's computer vision engine currently includes button recognition templates (`Start`, `Proceed`, `Chance`, `Result`, `Too Bad`, etc.) for **4 supported game languages**:
> - 🇬🇧 **English (`en`)**
> - 🇯🇵 **Japanese (`ja`)**
> - 🇨🇳 **Simplified Chinese (`zh`)**
> - 🇹🇼 **Traditional Chinese (`tw`)**
>
> You can set the bot's UI to any custom language, but **the game's in-game language must be set to one of the 4 supported languages above** for automatic button detection. Supporting a new in-game language (e.g. Korean or Indonesian) is as simple as creating a new folder with corresponding button capture templates under `templates/icons/<lang>/` — the bot will automatically discover and register them on launch without requiring code changes.

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
- `logs/`: Timestamped archives of previous sessions (`log_YYYY-MM-DD_*.txt`, `debug_log_*.txt`), automatically rotated on launch and pruned according to your configured retention settings (default: 14 days or 20 MB).
- `debug/`: Debug screenshots captured during vision or OCR failures (when debug mode is active).

---

## 📖 Instructions

1. Launch *Hololive Dreams* and ensure the game window is not minimized to the taskbar (it can be obscured or running behind other windows).
2. Set the in-game language to one of the 4 supported languages (**English**, **Japanese**, **Simplified Chinese**, or **Traditional Chinese**). Ensure the game runs in a standard **16:9 aspect ratio** (e.g. 1280x720, 1920x1080, 2560x1440, or 3840x2160 in windowed or fullscreen mode). Custom Windows DPI scaling (125%, 150%, 200%) is supported out of the box.
3. Launch the bot and configure your preferred language and stop hotkey.
4. Select your desired strategy mode and click **"Start Bot"**.
5. Press your configured stop hotkey at any time to safely halt automation.

---

## 🙏 Credits & Acknowledgments

This project originated as an enhanced extension of foundational automation work created by the open-source community:

- **Original Project & Core Concept**:
  - **Repository**: [mwty-0415/Hololive-Dreams-Auto-High-Low](https://github.com/mwty-0415/Hololive-Dreams-Auto-High-Low)
  - **Author**: [mwty-0415](https://github.com/mwty-0415) (Bilibili: [hmr0000](https://space.bilibili.com/519062381) / YouTube: [@hmr0000](https://www.youtube.com/@hmr0000))
  - **Notice**: Foundational game automation state machine and High-Low core recognition.
- **Computer Vision & Strategy Insights**:
  - **Repository**: [harrykuang-dev/Hololive-Dreams-Auto-High-Low](https://github.com/harrykuang-dev/Hololive-Dreams-Auto-High-Low)
  - **Author**: [harrykuang-dev](https://github.com/harrykuang-dev)
  - **Notice**: Enhanced OCR heuristics, settlement verification routines, and diagnostic insights.
- **Poker Card Recognition & Hand Solver**:
  - **Repository**: [Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)
  - **Author**: [Oreki0504](https://github.com/Oreki0504)
  - **Notice**: Card template patterns and poker hand evaluation logic.

All original copyrights, trademarks, and open-source licenses are respected and retained. For complete attribution notices, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## ⚠️ Disclaimer

- This tool is developed strictly for educational, computer vision, and automation research purposes.
- Do not use this tool for commercial purposes or in ways that compromise fair play. The developers assume no liability for any issues arising from its use.
