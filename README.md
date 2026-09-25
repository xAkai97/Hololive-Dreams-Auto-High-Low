# Hololive Dreams Auto Bot

An automated assistant and decision-making bot for the casino mini-game in *Hololive Dreams*, featuring optimal poker-hand calculation, dynamic High-Low card counting, and an extensible multilingual GUI.

---

## ✨ Key Features

- **Optimal Hand Selection**: Powered by Numba JIT acceleration to evaluate initial poker hands and hold the mathematically optimal card combinations.
- **Dynamic Card Counting**: Tracks remaining cards in the deck during the High-Low phase to compute real-time winning probabilities.
- **Smart Risk Control & Sprint Modes**:
  - **Staging Phase**: Automatically drops/cashes out when odds are unfavorable to steadily build bankroll.
  - **Sprint Phase**: Unlocks aggressive play once total coins reach 19,800, pushing for 10,000+ coins in a single run.
- **Three-Stage Doubling Strategy**: Supports customizable progression where stages cash out based on confirmed win counts rather than unstable readings. See [Three-Stage Doubling Strategy Guide](THREE_STAGE.md).
- **Extensible Multilingual Support**: Built-in support for English, Simplified Chinese, Traditional Chinese, and Japanese. Custom translation files can be dropped directly into `locales/`.
- **Profit & Loss Tracking**: Tracks failed runs and ticket fees (50 coins/entry), calculating net profit in real time.
- **Global Stop Hotkey**: Supports customizable hotkeys (default `INSERT`) to safely halt automation at any time.

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

The output will be created in `dist/Hololive Dreams-Auto/`. Keep the entire folder together (including the `_internal/` directory and `locales/` folder); do not move the `.exe` alone.

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
2. Launch the bot and configure your preferred language and stop hotkey.
3. Select your desired strategy mode and click **"Start Bot"**.
4. Press your configured stop hotkey at any time to safely halt automation.

---

## 🙏 Acknowledgments

- **Original Author**: [mwty-0415](https://github.com/mwty-0415) (Bilibili: [hmr0000](https://space.bilibili.com/519062381) / YouTube: [@hmr0000](https://www.youtube.com/@hmr0000))
- **Enhancements & Strategies**: [harrykuang-dev](https://github.com/harrykuang-dev)
- **Poker Card Recognition & Hand Logic**: [Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)

---

## ⚠️ Disclaimer

- This tool is developed strictly for educational, computer vision, and automation research purposes.
- Do not use this tool for commercial purposes or in ways that compromise fair play. The developers assume no liability for any issues arising from its use.
