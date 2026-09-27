# Hololive Dreams Auto Bot

An automated assistant and decision-making bot for the casino mini-game in *Hololive Dreams*, featuring optimal poker-hand calculation, dynamic High-Low card counting, and an extensible multilingual GUI.

---

## ✨ Key Features

- **Optimal Hand Selection**: Powered by Numba JIT acceleration to evaluate initial poker hands and hold the mathematically optimal card combinations.
- **Dynamic Card Counting**: Tracks remaining cards across the 53-card deck during the High-Low phase, accurately factoring in equal-rank tie-losses to calculate exact real-time winning probabilities.
- **Multi-Resolution & High-DPI Support**: Native support for any display resolution (720p, 1080p, 1440p / 2K, 2160p / 4K) and Windows display scaling (100%–200%+). Automatically normalizes frames using Per-Monitor DPI V2 awareness and area-averaged anti-aliasing, with proportional subpixel mouse click mapping.
- **Smart Risk Control & Sprint Modes (1.0.1 Legacy)**:
  - **Staging Phase**: Automatically drops/cashes out when odds are unfavorable to steadily build bankroll.
  - **Sprint Phase**: Unlocks aggressive play once total coins reach 19,800, pushing for 10,000+ coins in a single run.
  - See [1.0.1 Legacy Strategy Guide](docs/LEGACY_STRATEGY.md).
- **Three-Stage Doubling Strategy**: Supports customizable progression where stages cash out based on confirmed win counts rather than unstable readings. See [Three-Stage Doubling Strategy Guide](docs/THREE_STAGE.md).
- **Opportunistic High-Chance Doubling**: Toggleable on-canvas checkboxes (`A & 2` default ON, `3 & K`, `4 & Q`) to automatically continue doubling on high-win-rate cards while strictly under the daily cap ($< 20,000$ / max 19,800). See [Strategy Guide](docs/strategies.md).
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
│   ├── strategies/            # 9 modular doubling policy engines
│   │   ├── base.py            # BaseStrategy abstract interface
│   │   ├── max_profit.py      # Max profit ~32k cushion/sprint policy
│   │   ├── legacy_101.py      # 1.0.1 risk control & sprint policy
│   │   ├── three_stages.py    # Three-stage doubling strategy
│   │   ├── fastest_clear.py   # Speedrun all-or-nothing policy
│   │   ├── balanced.py        # Moderate risk ~25k policy
│   │   ├── aggressive_balanced.py # Aggressive ~28k policy
│   │   ├── adaptive_rush.py   # Auto-downshifting rush policy
│   │   ├── grinder.py         # Ultra-safe conservative policy
│   │   └── custom_parametric.py # User-tunable parametric policy
│   ├── challenge_reward.py    # Hand payout vision and OCR
│   ├── settlement.py          # Settlement balance verification
│   └── reward_vision.py       # Ongoing reward OCR
├── backgrounds/               # Drop custom background images here (.png, .jpg, etc.)
├── assets/                    # Application icons and static assets
├── locales/                   # External JSON translations (en.json, zh.json, ja.json, tw.json)
├── templates/                 # Game recognition templates
├── docs/                      # Documentation and detailed strategy guides
│   ├── strategies.md          # Comprehensive 9-strategy guide & opportunistic doubling
│   ├── LEGACY_STRATEGY.md     # 1.0.1 Legacy strategy deep dive
│   └── THREE_STAGE.md         # Three-stage doubling strategy guide
└── tests/                     # Unit test suite
```

---

## 🛠️ Running from Source

### Prerequisites
- Python 3.10 – 3.12 recommended
- Windows OS (game window scaling and background capture support)

```bash
git clone https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low.git
cd Hololive-Dreams-Auto-High-Low
pip install -r requirements.txt
python main_ui.py
```

---

## 🚀 Building Standalone Executable (.exe)

```powershell
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller -y "Hololive Dreams-Auto.spec"
```

The output will be created in `dist/Hololive Dreams-Auto/`. Keep the entire folder together (including `_internal/`, `backgrounds/`, `assets/`, and `locales/`); do not move the `.exe` alone.

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

## 📖 Instructions

1. Launch *Hololive Dreams* and ensure the game window is not minimized to the taskbar (it can be obscured or running behind other windows).
2. Ensure the game is running in a standard **16:9 aspect ratio** (e.g. 1280x720, 1920x1080, 2560x1440, or 3840x2160 in windowed or fullscreen mode). Displays with custom Windows DPI scaling (125%, 150%, 200%) are supported out of the box.
3. Launch the bot and configure your preferred language and stop hotkey.
4. Select your desired strategy mode and click **"Start Bot"**.
5. Press your configured stop hotkey at any time to safely halt automation.

---

## 🙏 Acknowledgments

- **Original Author**: [mwty-0415](https://github.com/mwty-0415) (Bilibili: [hmr0000](https://space.bilibili.com/519062381) / YouTube: [@hmr0000](https://www.youtube.com/@hmr0000))
- **Enhancements & Strategies**: [harrykuang-dev](https://github.com/harrykuang-dev)
- **Poker Card Recognition & Hand Logic**: [Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)

---

## ⚠️ Disclaimer

- This tool is developed strictly for educational, computer vision, and automation research purposes.
- Do not use this tool for commercial purposes or in ways that compromise fair play. The developers assume no liability for any issues arising from its use.
