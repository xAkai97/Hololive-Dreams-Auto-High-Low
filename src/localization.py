"""Centralized localization strings and translation helper for Hololive Dreams Auto Bot."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_LANG = "zh"
_current_lang = DEFAULT_LANG

LANGUAGE_NAMES: dict[str, str] = {
    "zh": "简体中文",
    "tw": "繁體中文",
    "en": "English",
    "ja": "日本語",
}


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

    Users can add new translations (e.g. ko.json, es.json) or override existing
    translations by placing a JSON file into the 'locales' directory.
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
                STRATEGY_LABELS[lang_code] = STRATEGY_LABELS.get("en", STRATEGY_LABELS[DEFAULT_LANG])

            translations = data.get("translations", data)
            if lang_code not in TRANSLATIONS:
                TRANSLATIONS[lang_code] = {}
            for k, v in translations.items():
                if isinstance(v, str) and k != "language_name":
                    TRANSLATIONS[lang_code][k] = v
        except Exception as exc:
            print(f"[i18n] Failed to load locale {file_path.name}: {exc}")

    return get_available_languages()


def get_available_languages() -> list[tuple[str, str]]:
    """Return sorted list of (lang_code, display_name) with built-in languages first."""
    builtin_order = ["zh", "tw", "en", "ja"]
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


ERROR_TRANSLATIONS: dict[str, dict[str, str]] = {
    "结算金额未能稳定确认": {
        "en": "Settlement amount could not be stably confirmed.",
        "ja": "精算金額を安定して確認できませんでした。",
    },
    "挑战奖金无法确认": {
        "en": "Challenge reward could not be confirmed.",
        "ja": "挑戦賞金を確認できませんでした。",
    },
    "当前已在翻倍途中": {
        "en": "Currently mid-challenge; cannot recover round count. Please restart from a fresh round.",
        "ja": "現在ダブルアップの途中のため、成功回数を復元できません。新しい対局からやり直してください。",
    },
    "缺少本局翻倍记录": {
        "en": "Missing doubling history for this round. Please check manually.",
        "ja": "本局のダブルアップ記録がないため照合できません。手動で確認してください。",
    },
    "本局起手奖金已无法保留第三阶段": {
        "en": "Initial prize cannot preserve the 3rd stage, please handle manually.",
        "ja": "本局の初期賞金では第3段階を保持できません。手動で対応してください。",
    },
    "游戏客户区尺寸异常": {
        "en": "Abnormal game client dimensions.",
        "ja": "ゲームクライアントのサイズが異常です。",
    },
}


def format_error(error: Exception | str, lang: str | None = None) -> str:
    err_str = str(error)
    active_lang = lang or _current_lang
    if active_lang in ("zh", "tw"):
        return err_str
    for pattern, mapping in ERROR_TRANSLATIONS.items():
        if pattern in err_str:
            return mapping.get(active_lang, mapping.get("en", err_str))
    return err_str


STRATEGY_LABELS = {
    "zh": ("1.0.1 原版", "三阶段：最大 → 计次 → 最大"),
    "tw": ("1.0.1 原版", "三階段：最大 → 計次 → 最大"),
    "en": ("1.0.1 Legacy", "3 Stages: Max → Win Count → Max"),
    "ja": ("1.0.1 従来モード", "3段階：最大 → 成功回数 → 最大"),
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "title": "Hololive Dreams 自动猜高低",
        "lang_label": "界面语言",
        "hotkey_label": "停止快捷键",
        "status_idle": "状态：等待启动",
        "status_running": "状态：运行中...",
        "status_stopping": "状态：正在停止...",
        "status_crashed": "状态：崩溃异常",
        "coins_prefix": "金币：{coins} / 20000",
        "net_profit_prefix": "净利: {profit:+d}",
        "fails_prefix": "失败: {fails}",
        "btn_exit": "退出",
        "btn_start": "启动挂机",
        "btn_stop": "停止挂机",
        "btn_bg": "切换背景",
        "btn_running": "运行中...",
        "hotkey_listening": "[按键...]",
        "hotkey_prompt": "\n[系统] 请点击键盘上想要切换的键...",
        "hotkey_success": "[系统] 停止快捷键已成功更换为: {key}\n",
        "hotkey_fallback": "[系统] 无法绑定按键 '{key}'，已自动恢复默认 F11\n",
        "system_stopping": "\n[系统] 收到停止指令 (或按下了快捷键)，正在等待当前动作完成并安全退出...",
        "system_stopped": "\n[系统] 挂机已完全停止。",
        "system_crash": "崩溃异常: {error}",

        "start_bot": "开始自动挂机... 当日累计代币: {coins} | 累计失败: {fails} 次 | 今日净利润: {profit}",
        "phased_completed": "[三阶段] 今日三个目标均已完成，停止挂机。",
        "phased_all_done": "[三阶段] 三个目标均已成功入账，停止挂机。",
        "window_not_found": "未找到游戏窗口，请确保游戏没有被完全最小化...",
        "state_start_bet": "\n[状态] 初始下注",
        "state_hold_cards": "\n[状态] 留牌阶段",
        "state_settlement_wait": "\n[状态] 结算界面，等待金额稳定后核对账目...",
        "phased_round_status": "[三阶段] 第 {stage}/3 阶段 | 已成功 {successes} 次 | 目标: {goal} | {action}",
        "phased_target_wins": "{wins} 次成功",
        "phased_target_auto": "游戏自动结算",
        "action_cashout": "收手入账",
        "action_continue": "继续翻倍",
        "challenge_current": "\n[账房] 当前在手现金: {cashout} | 挑战成功后将变为: {reward}",
        "risk_prediction": "[风控] 基于预判，下一轮真实胜率为: {rate:.2%}",
        "risk_blind": "[风控] 第一轮或盲盒状态，默认直接挑战！",
        "target_achieved": "🎉 终极目标达成！在手奖金已达 {cashout} (超1w)，安全提现大丰收！",
        "sprint_continue": "🚀 冲刺期继续追击（无视胜率，目标在手1w）！当前在手仅 {cashout}，冲刺 {reward}！",
        "cushion_warning": "🛑 警报：提现(+{cashout})在安全线内，但再翻倍(+{reward})总额将达 {total} 提前破限！果断收手垫刀！",
        "lucky_cashout": "🎉 意外天胡！垫刀途中在手直接达 {cashout} (超1w)，直接收手大丰收！",
        "force_double": "⚠️ 提现此笔(+{cashout})总额将达 {total} 破限且未破万！拒绝提现，强行搏翻倍！",
        "low_rate_cashout": "🛑 发育局胜率太低 ({rate:.2%})，提现 {cashout} 垫刀！",
        "safe_continue": "🔥 利润安全且再翻倍不会超限，普通局继续追击翻倍！",
        "visible_card_choice": "\n明牌: {rank}, 选: {choice} (胜率: {rate:.2%})",
        "tracking_start": "[预判] 启动多帧对比追踪...",
        "tracking_found": "[预判] 第 {frame} 帧追踪到新卡牌！下一张将是: {rank}",
        "tracking_timeout": "[预判] 连拍追踪超时，未能看清下一张牌。",
        "warn_no_cards": "\n[警告] 画面中未识别到任何白色卡牌，请确认画面处于 HIGH_LOW 状态且搜索区正常。",
        "err_high_low": "\n[异常] 猜高低逻辑崩溃: {error}",
        "fail_summary": "\n💔 对局失败！累计失败: {fails} 次 (门票损失: {loss}) | 今日净利润: {profit}",
        "settle_success": "💰 成功入账: {earned} ! 当前总金币: {coins} | 累计失败: {fails} 次 | 今日净利润: {profit}",
        "click_trigger": "👉 成功触发点击: {name} (匹配度: {score:.2f} >= {threshold})",
        "icon_not_found": "❌ 找不到图标文件: {path}",
        "warn_no_window": "[警告] 尚未取得有效游戏窗口，取消点击。",
        "warn_window_lost": "[警告] 游戏窗口已失效，取消点击。",
        "warn_cannot_read_coords": "[警告] 无法读取游戏窗口坐标，取消点击: {error}",
        "warn_background_capture_fail": "[警告] 后台窗口截图失败，切换到前台截图: {error}",
    },
    "tw": {
        "title": "Hololive Dreams 自動猜高低",
        "lang_label": "介面語言",
        "hotkey_label": "停止快捷鍵",
        "status_idle": "狀態：等待啟動",
        "status_running": "狀態：運行中...",
        "status_stopping": "狀態：正在停止...",
        "status_crashed": "狀態：崩潰異常",
        "coins_prefix": "金幣：{coins} / 20000",
        "net_profit_prefix": "淨利: {profit:+d}",
        "fails_prefix": "失敗: {fails}",
        "btn_exit": "退出",
        "btn_start": "啟動掛機",
        "btn_stop": "停止掛機",
        "btn_bg": "切換背景",
        "btn_running": "運行中...",
        "hotkey_listening": "[按鍵...]",
        "hotkey_prompt": "\n[系統] 請點擊鍵盤上想要切換的鍵...",
        "hotkey_success": "[系統] 停止快捷鍵已成功更換為: {key}\n",
        "hotkey_fallback": "[系統] 無法綁定按鍵 '{key}'，已自動恢復預設 F11\n",
        "system_stopping": "\n[系統] 收到停止指令 (或按下了快捷鍵)，正在等待當前動作完成並安全退出...",
        "system_stopped": "\n[系統] 掛機已完全停止。",
        "system_crash": "崩潰異常: {error}",

        "start_bot": "開始自動掛機... 當日累計代幣: {coins} | 累計失敗: {fails} 次 | 今日淨利潤: {profit}",
        "phased_completed": "[三階段] 今日三個目標均已完成，停止掛機。",
        "phased_all_done": "[三階段] 三個目標均已成功入帳，停止掛機。",
        "window_not_found": "未找到遊戲視窗，請確保遊戲沒有被完全最小化...",
        "state_start_bet": "\n[狀態] 初始下注",
        "state_hold_cards": "\n[狀態] 留牌階段",
        "state_settlement_wait": "\n[狀態] 結算畫面，等待金額穩定後核對帳目...",
        "phased_round_status": "[三階段] 第 {stage}/3 階段 | 已成功 {successes} 次 | 目標: {goal} | {action}",
        "phased_target_wins": "{wins} 次成功",
        "phased_target_auto": "遊戲自動結算",
        "action_cashout": "收手入帳",
        "action_continue": "繼續翻倍",
        "challenge_current": "\n[帳房] 當前在手現金: {cashout} | 挑戰成功後將變為: {reward}",
        "risk_prediction": "[風控] 基於預判，下一輪真實勝率為: {rate:.2%}",
        "risk_blind": "[風控] 第一輪或盲盒狀態，預設直接挑戰！",
        "target_achieved": "🎉 終極目標達成！在手獎金已達 {cashout} (超1w)，安全提現大豐收！",
        "sprint_continue": "🚀 衝刺期繼續追擊（無視勝率，目標在手1w）！當前在手僅 {cashout}，衝刺 {reward}！",
        "cushion_warning": "🛑 警報：提現(+{cashout})在安全線內，但再翻倍(+{reward})總額將達 {total} 提前破限！果斷收手墊刀！",
        "lucky_cashout": "🎉 意外天胡！墊刀途中在手直接達 {cashout} (超1w)，直接收手大豐收！",
        "force_double": "⚠️ 提現此筆(+{cashout})總額將達 {total} 破限且未破萬！拒絕提現，強行搏翻倍！",
        "low_rate_cashout": "🛑 發育局勝率太低 ({rate:.2%})，提現 {cashout} 墊刀！",
        "safe_continue": "🔥 利潤安全且再翻倍不會超限，普通局繼續追擊翻倍！",
        "visible_card_choice": "\n明牌: {rank}, 選: {choice} (勝率: {rate:.2%})",
        "tracking_start": "[預判] 啟動多幀對比追蹤...",
        "tracking_found": "[預判] 第 {frame} 幀追蹤到新卡牌！下一張將是: {rank}",
        "tracking_timeout": "[預判] 連拍追蹤超時，未能看清下一張牌。",
        "warn_no_cards": "\n[警告] 畫面中未識別到任何白色卡牌，請確認畫面處於 HIGH_LOW 狀態且搜尋區正常。",
        "err_high_low": "\n[異常] 猜高低邏輯崩潰: {error}",
        "fail_summary": "\n💔 對局失敗！累計失敗: {fails} 次 (門票損失: {loss}) | 今日淨利潤: {profit}",
        "settle_success": "💰 成功入帳: {earned} ! 當前總金幣: {coins} | 累計失敗: {fails} 次 | 今日淨利潤: {profit}",
        "click_trigger": "👉 成功觸發點擊: {name} (匹配度: {score:.2f} >= {threshold})",
        "icon_not_found": "❌ 找不到圖示檔案: {path}",
        "warn_no_window": "[警告] 尚未取得有效遊戲視窗，取消點擊。",
        "warn_window_lost": "[警告] 遊戲視窗已失效，取消點擊。",
        "warn_cannot_read_coords": "[警告] 無法讀取遊戲視窗座標，取消點擊: {error}",
        "warn_background_capture_fail": "[警告] 後台視窗截圖失敗，切換到前台截圖: {error}",
    },
    "en": {
        "title": "Hololive Dreams Auto Bot",
        "lang_label": "Language",
        "hotkey_label": "Stop Hotkey",
        "status_idle": "Status: Idle",
        "status_running": "Status: Running...",
        "status_stopping": "Status: Stopping...",
        "status_crashed": "Status: Crashed",
        "coins_prefix": "Coins: {coins} / 20000",
        "net_profit_prefix": "Net: {profit:+d}",
        "fails_prefix": "Fails: {fails}",
        "btn_exit": "Exit",
        "btn_start": "Start Bot",
        "btn_stop": "Stop Bot",
        "btn_bg": "Toggle BG",
        "btn_running": "Running...",
        "hotkey_listening": "[Press key...]",
        "hotkey_prompt": "\n[System] Press any key on your keyboard to bind as stop key...",
        "hotkey_success": "[System] Stop hotkey updated to: {key}\n",
        "hotkey_fallback": "[System] Failed to bind '{key}', defaulted to F11\n",
        "system_stopping": "\n[System] Stop command received. Waiting for current action to finish safely...",
        "system_stopped": "\n[System] Bot stopped completely.",
        "system_crash": "Crash error: {error}",

        "start_bot": "Starting bot... Today's coins: {coins} | Fails: {fails} | Net profit: {profit}",
        "phased_completed": "[3-Stage] All 3 daily targets completed. Bot stopped.",
        "phased_all_done": "[3-Stage] All 3 targets confirmed and settled. Bot stopped.",
        "window_not_found": "Game window not found. Ensure the game is not fully minimized...",
        "state_start_bet": "\n[State] Initial Bet",
        "state_hold_cards": "\n[State] Hold Cards",
        "state_settlement_wait": "\n[State] Result screen, waiting for amount to stabilize...",
        "phased_round_status": "[3-Stage] Stage {stage}/3 | Wins: {successes} | Target: {goal} | {action}",
        "phased_target_wins": "{wins} wins",
        "phased_target_auto": "Auto Settlement",
        "action_cashout": "Cashout",
        "action_continue": "Double",
        "challenge_current": "\n[Cashier] Current cash: {cashout} | On win: {reward}",
        "risk_prediction": "[Risk] Based on prediction, win rate: {rate:.2%}",
        "risk_blind": "[Risk] Round 1 or blind draw, doubling by default!",
        "target_achieved": "🎉 Ultimate target reached! Cash reached {cashout} (>10k). Safe cashout!",
        "sprint_continue": "🚀 Sprint phase! Cash is {cashout}, pursuing {reward} (target >10k)!",
        "cushion_warning": "🛑 Cushion Alert: Cashout (+{cashout}) is safe, but doubling (+{reward}) would total {total}, exceeding limit! Cashing out!",
        "lucky_cashout": "🎉 Jackpot! Cash reached {cashout} (>10k) during cushion phase. Cashing out!",
        "force_double": "⚠️ Cashout (+{cashout}) would total {total}, breaking limit without reaching 10k! Forcing double!",
        "low_rate_cashout": "🛑 Win rate too low ({rate:.2%}), cashing out {cashout}!",
        "safe_continue": "🔥 Safe profit and double remains within limit. Continuing challenge!",
        "visible_card_choice": "\nVisible: {rank}, Choice: {choice} (Win rate: {rate:.2%})",
        "tracking_start": "[Predict] Multi-frame tracking started...",
        "tracking_found": "[Predict] Frame {frame} detected new card! Next card: {rank}",
        "tracking_timeout": "[Predict] Frame tracking timed out. Unable to identify next card.",
        "warn_no_cards": "\n[Warning] No face-up cards recognized. Ensure screen is in HIGH_LOW state.",
        "err_high_low": "\n[Exception] High/Low logic exception: {error}",
        "fail_summary": "\n💔 Round failed! Total fails: {fails} (Ticket cost: {loss}) | Net profit: {profit}",
        "settle_success": "💰 Credited: {earned}! Total coins: {coins} | Fails: {fails} | Net profit: {profit}",
        "click_trigger": "👉 Clicked: {name} (Match: {score:.2f} >= {threshold})",
        "icon_not_found": "❌ Icon template not found: {path}",
        "warn_no_window": "[Warning] Valid game window not captured. Click cancelled.",
        "warn_window_lost": "[Warning] Game window lost. Click cancelled.",
        "warn_cannot_read_coords": "[Warning] Unable to get game window coordinates: {error}",
        "warn_background_capture_fail": "[Warning] Background capture failed, falling back to foreground: {error}",
    },
    "ja": {
        "title": "Hololive Dreams 自動Bot",
        "lang_label": "言語",
        "hotkey_label": "停止ショートカット",
        "status_idle": "ステータス: 待機中",
        "status_running": "ステータス: 実行中...",
        "status_stopping": "ステータス: 停止中...",
        "status_crashed": "ステータス: クラッシュ",
        "coins_prefix": "コイン: {coins} / 20000",
        "net_profit_prefix": "純利益: {profit:+d}",
        "fails_prefix": "失敗: {fails}",
        "btn_exit": "終了",
        "btn_start": "起動",
        "btn_stop": "停止",
        "btn_bg": "背景切替",
        "btn_running": "実行中...",
        "hotkey_listening": "[キー押下...]",
        "hotkey_prompt": "\n[システム] バインドしたいキーを押してください...",
        "hotkey_success": "[システム] 停止ショートカットを更新しました: {key}\n",
        "hotkey_fallback": "[システム] キー '{key}' のバインドに失敗したため、F11に戻しました\n",
        "system_stopping": "\n[システム] 停止コマンドを受信しました。現在の操作完了を待っています...",
        "system_stopped": "\n[システム] Botが完全に停止しました。",
        "system_crash": "クラッシュ異常: {error}",

        "start_bot": "自動Botを開始... 本日の獲得コイン: {coins} | 失敗: {fails} 回 | 純利益: {profit}",
        "phased_completed": "[3段階] 本日の3つの目標がすべて完了しました。Botを停止します。",
        "phased_all_done": "[3段階] 3つの目標がすべて正常に入金されました。Botを停止します。",
        "window_not_found": "ゲームウィンドウが見つかりません。最小化されていないか確認してください...",
        "state_start_bet": "\n[状態] 初期ベット",
        "state_hold_cards": "\n[状態] カード保持フェーズ",
        "state_settlement_wait": "\n[状態] リザルト画面。金額安定後に照合します...",
        "phased_round_status": "[3段階] 第 {stage}/3 段階 | 成功: {successes} 回 | 目標: {goal} | {action}",
        "phased_target_wins": "{wins} 回成功",
        "phased_target_auto": "自動精算",
        "action_cashout": "精算して終了",
        "action_continue": "ダブルアップ継続",
        "challenge_current": "\n[出納] 現在の手元資金: {cashout} | 勝利時: {reward}",
        "risk_prediction": "[リスク管理] 予測に基づく次回勝率: {rate:.2%}",
        "risk_blind": "[リスク管理] 第1ラウンドまたはブラインド状態のため挑戦継続！",
        "target_achieved": "🎉 最終目標達成！手元賞金が {cashout} (1万超) に達したため安全に利確！",
        "sprint_continue": "🚀 スプリント！手元 {cashout}、1万超を目指して {reward} に挑戦！",
        "cushion_warning": "🛑 警告：利確(+{cashout})は安全圏ですが、倍増(+{reward})すると合計 {total} で上限オーバー！利確します！",
        "lucky_cashout": "🎉 大当たり！手元が {cashout} (1万超) に達したため即利確！",
        "force_double": "⚠️ 利確(+{cashout})すると合計 {total} で上限突破かつ1万未満！勝負継続！",
        "low_rate_cashout": "🛑 勝率低下 ({rate:.2%}) のため、{cashout} で利確！",
        "safe_continue": "🔥 利益安全圏内かつ上限未満のため、ダブルアップ継続！",
        "visible_card_choice": "\n見せ札: {rank}, 選択: {choice} (勝率: {rate:.2%})",
        "tracking_start": "[予測] マルチフレーム追跡を開始...",
        "tracking_found": "[予測] 第 {frame} フレームで新カード検出！次回カード: {rank}",
        "tracking_timeout": "[予測] 追跡タイムアウト。次回カードを判別できませんでした。",
        "warn_no_cards": "\n[警告] 表向きカードが認識できません。HIGH_LOW状態と検索領域を確認してください。",
        "err_high_low": "\n[異常] High/Low処理エラー: {error}",
        "fail_summary": "\n💔 敗北！累計失敗: {fails} 回 (チケット損失: {loss}) | 純利益: {profit}",
        "settle_success": "💰 入金成功: {earned}! 現在のコイン: {coins} | 失敗: {fails} 回 | 純利益: {profit}",
        "click_trigger": "👉 クリック実行: {name} (一致度: {score:.2f} >= {threshold})",
        "icon_not_found": "❌ アイコン画像が見つかりません: {path}",
        "warn_no_window": "[警告] 有効なゲームウィンドウがないためクリックを中止しました。",
        "warn_window_lost": "[警告] ゲームウィンドウが無効になったためクリックを中止しました。",
        "warn_cannot_read_coords": "[警告] ウィンドウ座標を取得できません: {error}",
        "warn_background_capture_fail": "[警告] バックグラウンドキャプチャ失敗、フォアグラウンドに切替: {error}",
    },
}
