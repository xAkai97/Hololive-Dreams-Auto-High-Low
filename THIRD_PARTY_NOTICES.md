# Third-Party Notices & Acknowledgments

## Licensing Status

This repository does not apply a blanket repository-wide open-source license because it builds upon upstream repositories that currently publish no explicit license.

---

## 1. Original Project & Core Concept
- **Repository**: [mwty-0415/Hololive-Dreams-Auto-High-Low](https://github.com/mwty-0415/Hololive-Dreams-Auto-High-Low)
- **Author**: [mwty-0415](https://github.com/mwty-0415) (Bilibili: [hmr0000](https://space.bilibili.com/519062381) / YouTube: [@hmr0000](https://www.youtube.com/@hmr0000))
- **Notice**: Foundational automation state machine, icons, and High-Low recognition.
- **License**: **No license published upstream**; retained assets and derived code are not relicensed.

---

## 2. Computer Vision & Strategy Insights
- **Repositories**:
  - [harrykuang-dev/Hololive-Dreams-Auto-High-Low](https://github.com/harrykuang-dev/Hololive-Dreams-Auto-High-Low)
  - [harrykuang-dev/Hololive-Dreams-High-low-Auto-Personal](https://github.com/harrykuang-dev/Hololive-Dreams-High-low-Auto-Personal)
- **Author**: [harrykuang-dev](https://github.com/harrykuang-dev)
- **Notice**: Enhanced OCR heuristics (cyan HSV result OCR), settlement verification routines, live screenshot test fixtures (`tests/fixtures/`), minimized Unity window restore handling (`src/window_control.py`), and overlapping Japanese double-up prompt recognition (`src/auto_bot.py`).
- **License**: **No root license published upstream**; retained fixtures and ported/derived code are not relicensed.

---

## 3. Poker Card Recognition & Hand Solver
- **Repository**: [Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)
- **Author**: [Oreki0504](https://github.com/Oreki0504) (`Copyright (c) 2026 Totarou Oriki`)
- **Notice**: Card template matching (`src/recognizer.py`) and poker hand solver (`src/poker_core.py`).
- **License**: **MIT License** — full notice retained in [licenses/poker-core-MIT.txt](licenses/poker-core-MIT.txt).

---

## 4. Game Assets, Screenshots & Artwork
In-game UI templates (`templates/`), game screenshots (`tests/fixtures/`), and character artwork (`backgrounds/minato_aqua.png`) remain the property of their respective rights holders (`© COVER` / `© QualiArts, Inc.`) and are not relicensed by this project.

---

## 5. Third-Party Dependencies
Third-party runtime and build libraries listed in [requirements.txt](requirements.txt), [requirements-build.txt](requirements-build.txt), and [requirements-dev.txt](requirements-dev.txt) retain their respective licenses.
