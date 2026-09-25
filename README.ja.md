# Hololive Dreams 自動周回・支援ツール (Auto Bot)

<p align="center">
  <a href="README.md"><b>English</b></a> |
  <a href="README.zh-CN.md"><b>简体中文</b></a> |
  <a href="README.zh-TW.md"><b>繁體中文</b></a> |
  <a href="README.ja.md"><b>日本語</b></a>
</p>

---

『Hololive Dreams』のミニゲーム向けに設計された全自動周回・戦略決定支援ツールです。ポーカーの最適ホールド判定、ハイ＆ロー（High-Low）の動的カウンティング、拡張可能な多言語UIを搭載しています。

---

## ✨ 主な機能

- **ポーカー最適手札計算**：Numba JIT による高速演算で、配られた5枚の手札から期待値が最大となるキープカードを自動選定します。
- **動的カードカウンティング**：ハイ＆ロー中に残りの山札を追跡し、リアルタイムの勝率に基づき最適な選択（High / Low）を行います。
- **リスク管理とスプリントモード**：
  - **安定期**：勝率が低い場合は無理をせず利益を確定（ドロップ）し、目標コインまで着実に貯蓄します。
  - **スプリント期**：累計コインが19,800に達するとリスク制限を解除し、1撃10,000以上の大量獲得を目指して強気に挑戦します。
- **3段階のダブルアップ戦略**：確認された成功回数に基づいてドロップ時期を決定する柔軟な進行に対応しています。詳細は [3段階ダブルアップ戦略解説](THREE_STAGE.md#en) を参照してください。
- **拡張可能な多言語対応**：簡体字中国語、繁体字中国語、英語、日本語に対応。`locales/` フォルダに JSON ファイルを追加することで、新しい言語を簡単に追加できます。
- **収支・利益トラッキング**：失敗回数と入場料（1回あたり50コイン）の損失を自動集計し、当日の純利益をリアルタイムで表示します。
- **グローバル停止ショートカット**：任意のキー（初期設定：`INSERT`）でいつでも安全に停止できます。

---

## 🛠️ ソースコードからの実行

### 動作環境
- 推奨 Python 3.10 – 3.12
- Windows OS

```bash
git clone https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low.git
cd Hololive-Dreams-Auto-High-Low
pip install -r requirements.txt
python main_ui.py
```

---

## 🚀 単体実行ファイル (.exe) のビルド

```powershell
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller -y "Hololive Dreams-Auto.spec"
```

ビルド完了後、`dist/Hololive Dreams-Auto/` フォルダに出力されます。`_internal/` や `locales/` を含むフォルダ全体をそのまま保持し、`.exe` のみを取り出して移動しないでください。

---

## 🌐 カスタム翻訳の追加

新しい言語を追加、または既存の翻訳を編集する場合：
1. `locales/` フォルダを開きます。
2. 既存のファイル（例: `ja.json`）をコピーし、言語コード名（例: `ko.json`、`de.json`）に変更します。
3. `"language_name"`（例: `"한국어"`）を設定し、各テキストを翻訳します。
4. アプリを再起動すると、UI の言語選択プルダウンに自動的に追加されます。

---

## 📖 使用方法

1. ゲームを起動し、ウィンドウが完全に最小化されていない状態にします（他ウィンドウの背面に隠れていても動作可能）。
2. ツールを起動し、言語、戦略モード、停止ショートカットキーを設定します。
3. **「起動」** ボタンを押すと自動周回が開始されます。
4. 途中で停止したい場合は、設定した停止キーを押すと安全に終了します。

---

## 🙏 謝辞 (Acknowledgments)

- **原作者**: [mwty-0415](https://github.com/mwty-0415) (Bilibili: [hmr0000](https://space.bilibili.com/519062381) / YouTube: [@hmr0000](https://www.youtube.com/@hmr0000))
- **戦略強化・精算機能改善**: [harrykuang-dev](https://github.com/harrykuang-dev)
- **手札認識・アルゴリズム基盤**: [Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)

---

## ⚠️ 免責事項

- 本ツールは Python プログラミング、画像認識、および自動化技術の研究・学習を目的として作成されています。
- 本ツールを不正目的や商用目的で使用することを禁止します。本ツールの利用によって生じたいかなる損害についても、開発者は責任を負いません。
