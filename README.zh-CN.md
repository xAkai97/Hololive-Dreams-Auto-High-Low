# Hololive Dreams 自动挂机脚本 (Auto Bot)

<p align="center">
  <a href="README.md"><b>English</b></a> |
  <a href="README.zh-CN.md"><b>简体中文</b></a> |
  <a href="README.zh-TW.md"><b>繁體中文</b></a> |
  <a href="README.ja.md"><b>日本語</b></a>
</p>

---

专为《Hololive Dreams》小游戏设计的全自动挂机与策略决策工具，集成智能留牌算法、高低牌动态算牌及多语言可扩展界面。

---

## ✨ 核心特性

- **最优留牌计算**：基于 Numba JIT 高性能加速，自动评估起手五张牌并计算期望收益最高的保留组合。
- **动态算牌记牌**：内置 High-Low 记牌引擎，根据剩余牌堆实时计算当前最高胜率分支。
- **风控止盈与极限冲刺**：
  - **垫刀期**：胜率偏低时主动收手提现，确保单日收益平稳累积。
  - **冲刺期**：金币达 19,800 后自动解除风控，以追求单笔 10,000+ 巨额奖金为目标发起冲刺。
- **三阶段翻倍策略**：支持根据确认成功次数决定收手阶段，详情请参阅 [三阶段翻倍策略说明](THREE_STAGE.md#zh-cn)。
- **可扩展多语言支持**：原生内置简体中文、繁體中文、English 及 日本語，支持在 `locales/` 目录下热插拔自定义语言包。
- **收支监控**：自动记录失败轮次与门票扣除（50/局），实时核算净利润。
- **全局快捷键**：支持自定义全局停止热键（默认 `INSERT`），挂机时随时安全接管。

---

## 🛠️ 源码运行

### 环境要求
- 建议 Python 3.10 – 3.12
- Windows 操作系统

```bash
git clone https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low.git
cd Hololive-Dreams-Auto-High-Low
pip install -r requirements.txt
python main_ui.py
```

---

## 🚀 打包为独立执行程序 (.exe)

```powershell
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller -y "Hololive Dreams-Auto.spec"
```

生成的文件位于 `dist/Hololive Dreams-Auto/` 目录。请保留包含 `_internal/` 和 `locales/` 的整个文件夹，切勿单独提取 `.exe` 文件运行。

---

## 🌐 自定义语言包

若需要添加新语言或修改现有翻译文本：
1. 打开 `locales/` 文件夹。
2. 复制现有文件（例如 `zh.json`）并重命名为目标语言代码（例如 `ko.json`、`fr.json`）。
3. 修改 `"language_name"`（例如 `"한국어"`）并调整翻译词条。
4. 重新启动程序，UI 下拉菜单将自动加载并显示新语言。

---

## 📖 使用说明

1. 启动游戏并保持游戏窗口未完全最小化（支持被其他窗口遮挡，但不可最小化至任务栏）。
2. 打开辅助工具，按需选择界面语言、策略模式与全局停止快捷键。
3. 点击 **「启动挂机」** 开始自动化运行。
4. 挂机过程中随时按下设定的停止快捷键即可安全关停。

---

## 🙏 致谢与鸣谢 (Acknowledgments)

- **原作者**：[mwty-0415](https://github.com/mwty-0415)（Bilibili：[hmr0000](https://space.bilibili.com/519062381) / YouTube：[@hmr0000](https://www.youtube.com/@hmr0000)）
- **策略增强与结算优化**：[harrykuang-dev](https://github.com/harrykuang-dev)
- **留牌阶段识牌与算法基底**：[Oreki0504/hololive-dreams-helper](https://github.com/Oreki0504/hololive-dreams-helper)

---

## ⚠️ 免责声明

- 本工具仅供 Python 编程学习、图像识别技术研究交流使用。
- 请勿用于破坏游戏生态或任何商业盈利场景，因使用本工具造成的任何问题开发者概不负责。
