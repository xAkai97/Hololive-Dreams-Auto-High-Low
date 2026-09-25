# Hololive Dreams 自動掛機腳本 (Auto Bot)

<p align="center">
  <a href="README.md"><b>English</b></a> |
  <a href="README.zh-CN.md"><b>简体中文</b></a> |
  <a href="README.zh-TW.md"><b>繁體中文</b></a> |
  <a href="README.ja.md"><b>日本語</b></a>
</p>

---

專為《Hololive Dreams》小遊戲設計的全自動掛機與策略決策工具，整合智慧留牌演算法、高低牌動態算牌及多語言可擴充介面。

---

## ✨ 核心特色

- **最佳留牌計算**：基於 Numba JIT 高效能加速，自動評估初始五張手牌並計算期望收益最高的保留組合。
- **動態算牌記牌**：內建 High-Low 算牌引擎，根據剩餘牌堆即時計算當前最高勝率選項。
- **風控止盈與極限衝刺**：
  - **墊刀期**：勝率偏低時主動收手提現，確保代幣在安全線內穩定累積。
  - **衝刺期**：當代幣達到 19,800 後自動解除風控，鎖定單局 10,000+ 巨額獎金發起衝刺。
- **三階段翻倍策略**：支援依據確認成功次數決定收手階段，詳細規則請參閱 [三階段翻倍策略說明](THREE_STAGE.md#zh-tw)。
- **可擴充多語言支援**：原生內建簡體中文、繁體中文、English 及 日本語，支援在 `locales/` 目錄下隨插即用自訂語系檔。
- **收支與淨利監控**：自動記錄失敗次數與入場門票消耗（50/局），即時計算淨利潤。
- **全域快捷鍵**：支援自訂全域停止快捷鍵（預設為 `INSERT`），掛機途中隨時安全接管。

---

## 🛠️ 原始碼執行

### 環境需求
- 建議 Python 3.10 – 3.12
- Windows 作業系統

```bash
git clone https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low.git
cd Hololive-Dreams-Auto-High-Low
pip install -r requirements.txt
python main_ui.py
```

---

## 🚀 打包為獨立執行檔 (.exe)

```powershell
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller -y "Hololive Dreams-Auto.spec"
```

產生的檔案位於 `dist/Hololive Dreams-Auto/` 資料夾。請保留包含 `_internal/` 與 `locales/` 的整個資料夾，切勿單獨取出 `.exe` 執行。

---

## 🌐 自訂語系檔

若欲新增語言或修改現有翻譯文本：
1. 開啟 `locales/` 資料夾。
2. 複製現有檔案（例如 `tw.json`）並重新命名為目標語系代碼（例如 `ko.json`、`fr.json`）。
3. 修改 `"language_name"`（例如 `"한국어"`）並調整翻譯詞條。
4. 重新啟動程式，UI 下拉選單將自動載入並顯示新語言。

---

## 📖 使用說明

1. 開啟遊戲並維持遊戲視窗未被完全最小化（可被其他視窗遮擋，但不可縮小至工作列）。
2. 開啟本輔助程式，依需求設定語言、策略模式與停止快捷鍵。
3. 點擊 **「啟動掛機」** 進入全自動流程。
4. 任何時候按下設定的停止快捷鍵皆可安全停機。

---

## 🙏 致謝與鳴謝 (Acknowledgments)

- **原作者**：[mwty-0415](https://github.com/mwty-0415)（Bilibili：[hmr0000](https://space.bilibili.com/519062381) / YouTube：[@hmr0000](https://www.youtube.com/@hmr0000)）
- **策略增強與結算優化**：[harrykuang-dev](https://github.com/harrykuang-dev)
- **留牌階段識牌與演算法基底**：[Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)

---

## ⚠️ 免責聲明

- 本工具僅供 Python 程式學習、電腦視覺技術研究交流使用。
- 請勿將本工具用於破壞遊戲平衡或任何商業營利用途，使用本程式產生的任何後果開發者概不負責。
