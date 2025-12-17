# ------------------------------------------------------------
# LlmStrategy_Exact_Full.py
# 完全复刻 MQL4 神龙通道（结构优化 + 超清晰注释版）
# 逻辑与原版完全相同，只是提升了可读性与模块化
# 作者: 神龙通道至尊版（保留你原作者名）
# ------------------------------------------------------------

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
import json
import os
from typing import Dict, Optional
import numpy as np

from myutility import BarGenerator, Interval


def save_results_fixed(engine, statistics):
    """修复numpy类型序列化问题的保存函数"""

    # 创建结果目录
    results_dir = "backtest_results"
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 转换统计结果中的numpy类型为Python原生类型
    def convert_numpy_types(obj):
        """递归转换对象中的numpy类型为Python原生类型"""
        if isinstance(obj, dict):
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        else:
            return obj

    # 转换统计结果
    converted_stats = convert_numpy_types(statistics)

    # 保存统计结果
    stats_file = os.path.join(results_dir, f"statistics_{timestamp}.json")
    try:
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(converted_stats, f, indent=2, ensure_ascii=False)
        print(f"✓ 统计结果已保存: {stats_file}")
    except Exception as e:
        print(f"✗ 保存统计结果失败: {e}")
        # 备用方案：保存为文本
        with open(stats_file.replace(".json", ".txt"), "w", encoding="utf-8") as f:
            for key, value in converted_stats.items():
                f.write(f"{key}: {value}\n")
        print(f"✓ 统计结果已保存为文本: {stats_file.replace('.json', '.txt')}")

    # 保存回测日志
    log_file = os.path.join(results_dir, f"backtest_log_{timestamp}.txt")
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            for log in engine.logs:
                f.write(log + "\n")
        print(f"✓ 回测日志已保存: {log_file}")
    except Exception as e:
        print(f"✗ 保存回测日志失败: {e}")

    trades_file = os.path.join(results_dir, f"trades_{timestamp}.json")
    trades_list = [convert_numpy_types(tr.__dict__) for tr in engine.trades.values()]
    with open(trades_file, "w", encoding="utf-8") as f:
        json.dump(trades_list, f, indent=2, ensure_ascii=False)
    print("Saved trades to", trades_file)


from vnpy_ctastrategy import (
    CtaTemplate,
    Direction,
    BarData,
    TradeData,
    ArrayManager,
)
from vnpy_ctastrategy.base import Offset


# 数据结构
# -------------------------
@dataclass
class PendingWindow:
    """
    长周期窗口信息：
    - direction: 当前窗口方向 long/short
    - start_bar: 窗口开始的长周期 Bar 计数
    - long_end: 窗口结束 Bar 计数
    - long_end_time: 窗口结束时间
    """

    direction: str
    start_bar: int
    long_end: int
    long_end_time: datetime


class PositionState:
    """内部仓位状态管理"""

    def __init__(self):
        self.direction: Optional[str] = None  # long/short/None
        self.entry_price: float = 0.0
        self.sl: float = 0.0
        self.tp: float = 0.0
        self.volume: float = 0.0


class SignalStrategy:
    """
    短周期策略接口：
    - 只在 long/short pending window 内触发开仓信号
    - 返回值 'long'/'short'/None
    """

    def generate_entry_signal(
        self, am: ArrayManager, bar: BarData, window_direction: str
    ):
        return None


class Shenlong(SignalStrategy):
    """
    Shenlong 指标复刻：
    - 可触发开仓 'long'/'short'
    - 可触发平仓 'close_long'/'close_short'
    """

    def __init__(
        self,
        owner,
        sh=30,
        xma_n_3=25,
        xma_n_3_1=25,
        xma_n_2=25,
        xma_n_2_1=25,
        belt_weights_len=20,
        belt_smooth_period=90,
    ):
        self.owner = owner
        self.sh = sh
        self.xma_n_3 = xma_n_3
        self.xma_n_3_1 = xma_n_3_1
        self.xma_n_2 = xma_n_2
        self.xma_n_2_1 = xma_n_2_1
        self.belt_weights_len = belt_weights_len
        self.belt_smooth_period = belt_smooth_period
        self.weight_sum = belt_weights_len * (belt_weights_len + 1) / 2

    # ============================================================
    # 核心处理：把你原来 on_4hour_bar 中的逻辑全部封装进这里
    # ============================================================

    def generate_entry_signal(
        self, am: ArrayManager, bar: BarData, dir: str
    ):
        """
        返回：
        - 'long' / 'short' → 新窗口触发短周期开仓
        - 'close_long' / 'close_short' → 立即平仓
        - None → 无信号
        """
        if str is None:
            return None
        self.owner.output_msg(f"receive signal: {dir}")
        highs = am.high_array[::-1]  # 0 最新
        lows = am.low_array[::-1]
        closes = am.close_array[::-1]
        length = len(highs) - self.sh

        # Belt/XMA 计算
        # belt2, belt3, belt4, slld_0, slld_8 = self._compute_belt_exact(
        #     length, highs, lows
        # )
        xma3_1, xma2_1 = self._compute_xma_exact(length, highs, lows)

        # g_ibuf buffers
        g_ibuf_116 = 2.0 * xma3_1 - xma2_1
        g_ibuf_120 = 2.0 * xma2_1 - xma3_1

        def safe(arr, idx):
            try:
                return float(arr[idx])
            except:
                return float("nan")

        # 下通道线
        g116_0 = safe(g_ibuf_116, 0)
        g116_1 = safe(g_ibuf_116, 1)
        # 上通道线
        g120_0 = safe(g_ibuf_120, 0)
        g120_1 = safe(g_ibuf_120, 1)

        low_0, low_1 = lows[0], lows[1]
        high_0, high_1 = highs[0], highs[1]
        close_0, close_1 = closes[0], closes[1]

        # 开仓条件
        condition_buy = g116_1 < close_1 and g116_0 > close_0 and (dir == "long")
        condition_close_buy = close_1 < g120_1 and close_0 > g120_0 and (dir == "long")
        condition_sell = close_1 < g120_1 and close_0 > g120_0 and (dir == "short")
        condition_close_sell = g116_1 < close_1 and g116_0 > close_0 and (dir == "short")
        # condition_buy = g116_1 < low_1 and g116_0 > low_0 and (g116_0 > slld8_0)
        # condition_sell = high_1 < g120_1 and high_0 > g120_0 and (g120_0 < slld0_0)

        # 平仓条件
        split = "[shenlong_signal]  "
        if condition_buy:
            self.owner.output_msg(
                f"{split}long trigger Bar信息 - 时间: {bar.datetime}, O: {bar.open_price}, H: {bar.high_price}, L: {bar.low_price}, C: {bar.close_price}, V: {bar.volume}"
            )
            self.owner.output_msg(
                f"{split}指标值: g116_0={g116_0:.6f}, g116_1={g116_1:.6f}, g120_0={g120_0:.6f}, g120_1={g120_1:.6f}"
            )
            self.owner.output_msg(
                f"{split}价格: low_0={low_0:.4f}, low_1={low_1:.4f}, high_0={high_0:.4f}, high_1={high_1:.4f}, close_0={close_0:.4f}, close_1={close_1:.4f}"
            )
            return "long"
        elif condition_sell:
            self.owner.output_msg(
                f"{split}short trigger Bar信息 - 时间: {bar.datetime}, O: {bar.open_price}, H: {bar.high_price}, L: {bar.low_price}, C: {bar.close_price}, V: {bar.volume}"
            )
            self.owner.output_msg(
                f"{split}指标值: g116_0={g116_0:.6f}, g116_1={g116_1:.6f}, g120_0={g120_0:.6f}, g120_1={g120_1:.6f}"
            )
            self.owner.output_msg(
                f"{split}价格: low_0={low_0:.4f}, low_1={low_1:.4f}, high_0={high_0:.4f}, high_1={high_1:.4f}, close_0={close_0:.4f}, close_1={close_1:.4f}"
            )
            return "short"
        elif condition_close_buy:
            self.owner.output_msg(
                f"{split}close_long Bar信息 - 时间: {bar.datetime}, O: {bar.open_price}, H: {bar.high_price}, L: {bar.low_price}, C: {bar.close_price}, V: {bar.volume}"
            )
            self.owner.output_msg(
                f"{split}指标值: g116_0={g116_0:.6f}, g116_1={g116_1:.6f}, g120_0={g120_0:.6f}, g120_1={g120_1:.6f}"
            )
            self.owner.output_msg(
                f"{split}价格: low_0={low_0:.4f}, low_1={low_1:.4f}, high_0={high_0:.4f}, high_1={high_1:.4f}, close_0={close_0:.4f}, close_1={close_1:.4f}"
            )
            return "close_long"
        elif condition_close_sell:
            self.owner.output_msg(
                f"{split}close_short Bar信息 - 时间: {bar.datetime}, O: {bar.open_price}, H: {bar.high_price}, L: {bar.low_price}, C: {bar.close_price}, V: {bar.volume}"
            )
            self.owner.output_msg(
                f"{split}指标值: g116_0={g116_0:.6f}, g116_1={g116_1:.6f}, g120_0={g120_0:.6f}, g120_1={g120_1:.6f}"
            )
            self.owner.output_msg(
                f"{split}价格: low_0={low_0:.4f}, low_1={low_1:.4f}, high_0={high_0:.4f}, high_1={high_1:.4f}, close_0={close_0:.4f}, close_1={close_1:.4f}"
            )
            return "close_short"
        return None

    # ============================================================
    # 计算部分（完全复刻 MQL4 行为）
    # ============================================================
    def _compute_belt_exact(
        self, length: int, highs: np.ndarray, lows: np.ndarray
    ) -> tuple:
        """
        精确复刻 MQL4 的 Belt 计算（数组方向与 MQL4 一致：0=最新）
        返回：belt2, belt3, belt4, slld_0, slld_8
        细节注释：
        - 输入 highs/lows 已经是 MQL4 顺序（0=最新），length 表示有效计算长度（len(highs)-sh）
        - 为保持 MQL4 的行为，数组初始化全部为 0（而不是 NaN），并且 EMA 平滑按照 MQL4 那样正向迭代
        - 公式与原版一致：belt0/belt1 用加权求和，belt2/belt3 用 EMA 平滑，belt4=belt2-belt3，slld0=belt2+2*belt4, slld8=belt3-2*belt4
        """
        n = self.belt_weights_len + 1

        # 如果可用长度不足，返回长度为 length 的 NaN 数组（调用端会用 safe() 处理）
        if length < n:
            return tuple([np.full(length, np.nan) for _ in range(5)])

        # 初始数组均为 0，与 MQL4 ArrayInitialize(array,0) 的行为一致
        belt0 = np.zeros(length)
        belt1 = np.zeros(length)
        belt2 = np.zeros(length)
        belt3 = np.zeros(length)
        belt4 = np.zeros(length)
        slld_0 = np.zeros(length)
        slld_8 = np.zeros(length)

        # -------------------------
        # 逐条计算 belt0/belt1（加权和）
        # 原逻辑：对每个 i，累加权重 * highs[i+w] 与 weight * lows[i+w]
        # 注意：遍历方向采用从 length-1 到 0，与 MQL4 的索引映射一致（保持行为）
        # -------------------------
        for i in range(length - 1, -1, -1):
            # 防护：确保 i + belt_weights_len 在 highs 索引范围内
            if i + self.belt_weights_len >= len(highs):
                # 如果越界就跳过，这与原版在边界处理上的行为一致
                continue

            sum_high = 0.0
            sum_low = 0.0
            # w 从 0 到 n-1，对应权重 belt_weights_len - w
            for w in range(n):
                weight = self.belt_weights_len - w
                # 原版在 MQL4 中的索引对应到我们的 highs 已经是 MQL4 顺序（0=最新），
                # 因此直接使用 highs[i + w] 与 lows[i + w]
                sum_high += weight * highs[i + w]
                sum_low += weight * lows[i + w]

            belt0[i] = sum_high / self.weight_sum
            belt1[i] = sum_low / self.weight_sum
            # print(
            #     f"H={highs[i]}, L={lows[i]}"
            #     f"Bar {i}, belt0={belt0[i]:.5f}, belt1={belt1[i]:.5f}"
            # )
        # -------------------------
        # EMA 平滑（与 MQL4 保持一致）
        # belt2[i] = (2*belt0[i] + (period-1)*belt2[i+1]) / (period+1)
        # 从 length-2 到 0 反向迭代，保持 MQL4 的累积效果
        # -------------------------
        for i in range(length - 2, -1, -1):
            belt2[i] = (2 * belt0[i] + (self.belt_smooth_period - 1) * belt2[i + 1]) / (
                self.belt_smooth_period + 1
            )
            belt3[i] = (2 * belt1[i] + (self.belt_smooth_period - 1) * belt3[i + 1]) / (
                self.belt_smooth_period + 1
            )

        # belt4 与 slld
        belt4 = belt2 - belt3
        slld_0 = belt2 + 2.0 * belt4
        slld_8 = belt3 - 2.0 * belt4

        return belt2, belt3, belt4, slld_0, slld_8

    def _compute_centered_ma_mql4(
        self, length: int, data: np.ndarray, window: int
    ) -> np.ndarray:
        """
        中心移动平均计算（保持 ArrayManager 顺序，但在计算时映射索引）
        """
        result = np.zeros(len(data))
        half_window = (window - 1) // 2

        # 使用 ArrayManager 顺序（0=最旧，-1=最新）
        # 但在计算时映射到 MQL4 的逻辑
        for mql4_i in range(length, -1, -1):  # 从最旧到最新 (与 MQL4 一致)
            if mql4_i >= half_window:
                # 正常情况
                sum_val = 0.0
                for mql4_j in range(mql4_i + half_window, mql4_i - half_window - 1, -1):
                    # 使用 lows[-1-mql4_j] 来访问 MQL4 索引对应的数据
                    # if (mql4_j < len(data)):
                    sum_val += data[mql4_j]
                result[mql4_i] = sum_val / window
            else:
                # 边界情况
                sum_val = 0.0
                for mql4_j in range(mql4_i + half_window, -1, -1):
                    # if (mql4_j < len(data)):
                    sum_val += data[mql4_j]

                # MQL4 的特殊权重调整
                adjustment = (half_window - mql4_i) / (half_window + mql4_i + 1)
                result[mql4_i] = (sum_val + sum_val * adjustment) / window
        # result = result[::-1]
        # for i in range(0, length):
        #     print(
        #         f"Bar {i}: result={result[i]}"
        #     )
        return result

    def _compute_xma_exact(
        self, length: int, highs: np.ndarray, lows: np.ndarray
    ) -> tuple:
        """
        精确复刻 MQL4 的 XMA（双重中心化移动平均）：
        - 先对 lows 做一次中心化平均 -> xma3_0，然后再对 xma3_0 做第二次中心化平均 -> xma3_1
        - 对 highs 做同样的两次平滑得到 xma2_1
        返回 (xma3_1, xma2_1)，数组方向均为 MQL4（0=最新）
        """
        # 第一次中心平均（低价）
        xma3_0 = self._compute_centered_ma_mql4(length, lows, self.xma_n_3)
        # 第二次中心平均（低价）
        xma3_1 = self._compute_centered_ma_mql4(length, xma3_0, self.xma_n_3_1)
        # 第一次中心平均（高价）
        xma2_0 = self._compute_centered_ma_mql4(length, highs, self.xma_n_2)
        # 第二次中心平均（高价）
        xma2_1 = self._compute_centered_ma_mql4(length, xma2_0, self.xma_n_2_1)

        return xma3_1, xma2_1


# -------------------------
# 短周期策略示例：EMA Cross
# -------------------------
class EMA_Trend(SignalStrategy):
    """短周期开仓策略示例"""

    def __init__(
        self, owner, fast=34, slow=89, mom_value=0, mom_period=30, adx_period=14
    ):
        self.fast = fast
        self.slow = slow
        self.owner = owner
        self.mom_value = mom_value
        self.mom_period = mom_period
        self.adx_period = adx_period
        self.fast_ema = []
        self.slow_ema = []

    def generate_entry_signal(self, am, bar, window_direction):
        if not am.inited:
            return None
        # ======= 1. MA 多重均线趋势因子 ========
        fast = am.ema(self.fast, array=False)
        slow = am.ema(self.slow, array=False)

        self.ma_trend = 1 if fast > slow else -1

        # ======= 2. 动量因子（Momentum） ========
        self.mom_value = bar.close_price - am.close[-self.mom_period]
        mom_trend = 1 if self.mom_value > 0 else -1

        # ======= 3. ADX 趋势强度因子 ========
        adx = am.adx(self.adx_period, array=False)
        self.adx_value = adx
        trend_strength = 1 if adx > 25 else 0  # ADX > 25 才认为趋势强

        # ======= 汇总所有趋势因子 ========
        trend_score = 0
        trend_score += 1 if self.ma_trend == 1 else -1
        trend_score += 1 if mom_trend == 1 else -1
        trend_score += 1 if trend_strength == 1 else -1
        # ATR 不计方向：只用于是否过滤
        if trend_score >= 2 and trend_strength == 1:
            return "long"
        if trend_score <= 2 and trend_strength == 1:
            return "short"
        return None


# -------------------------
# 核心策略类
# -------------------------
class DualStrategy(CtaTemplate):
    author = "samirliu"

    long_kline = 2
    short_kline = 3
    signal_window = 4
    atr_window = 14
    sl_multiplier = 1.5
    tp_multiplier = 4.0
    max_trades_per_window = 1
    trade_volume = 1
    max_pos = 1
    fast_ema = 5
    slow_ema = 30
    init_bar_size = 500
    risk_threshold = 0.2
    leverage_ratio = 10
    long_signal = None
    parameters = [
        "long_kline",
        "short_kline",
        "signal_window",
        "atr_window",
        "sl_multiplier",
        "tp_multiplier",
        "max_trades_per_window",
        "trade_volume",
        "max_pos",
        "fast_ema",
        "slow_ema",
        "init_bar_size",
        "risk_threshold",
        "leverage_ratio",
    ]
    variables = ["long_bar_count"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 状态
        self.pos_state = PositionState()
        self._pending_entry: Optional[dict] = None
        self._pending_close: Optional[dict] = None
        self.long_bar_count: int = 0

        # 周期映射
        self._long_map = {3: 60 * 24, 2: 4 * 60, 1: 60}
        self._short_map = {4: 60, 3: 30, 2: 15, 1: 5}
        self.long_minutes = self._long_map.get(self.long_kline, 60 * 24)
        self.short_minutes = self._short_map.get(self.short_kline, 30)
        self.close_position_flag = False

        # BarGenerator 初始化
        if self.long_kline == 3:
            self.bg_long = BarGenerator(
                self.on_bar,
                window=1,
                on_window_bar=self.on_long_bar,
                interval=Interval.DAILY,
                daily_end=time(21, 59),
            )
        elif self.long_kline == 2:
            self.bg_long = BarGenerator(
                self.on_bar,
                window=self.long_minutes,
                on_window_bar=self.on_long_bar,
                interval=Interval.FOUR_HOURS,
            )
        else:
            self.bg_long = BarGenerator(
                self.on_bar,
                window=self.long_minutes,
                on_window_bar=self.on_long_bar,
                interval=Interval.MINUTE,
            )
        self.bg_short = BarGenerator(
            self.on_bar,
            window=self.short_minutes,
            on_window_bar=self.on_short_bar,
            interval=Interval.MINUTE,
        )

        # ArrayManager
        self.am_long = ArrayManager(self.init_bar_size)
        self.am_short = ArrayManager(self.init_bar_size * 3)
        self.bg_long_bars: list[BarData] = []
        # 默认插件
        self.long_signal_strategy: SignalStrategy = EMA_Trend(owner=self, fast=self.fast_ema, slow=self.slow_ema)
        self.short_signal_strategy: SignalStrategy = Shenlong(owner=self)

    def on_init(self):
        self.output_msg("DualStrategy initialized")
        self.current_capital = self.cta_engine.capital
        self.leverage_capital = self.cta_engine.capital * self.leverage_ratio

    # -------------------------
    # 主 on_bar
    # -------------------------
    def on_bar(self, bar: BarData):
        # 检查资金风险
        if (
            self.current_capital <= self.cta_engine.capital * self.risk_threshold
        ):  # 低于风险阈值就停止
            self.output_msg(f"⚠️ 资金风险过高 ({self.current_capital:.2f})，停止交易")
            return
        """接收每根分钟/日线"""
        self.check_exit_conditions(bar)
        self.bg_long.update_bar(bar)
        self.bg_short.update_bar(bar)
        self.last_bar_price = bar.close_price

    # -------------------------
    # 长周期处理
    # -------------------------
    def on_long_bar(self, bar: BarData):
        self.long_bar_count += 1
        self.am_long.update_bar(bar)
        self.bg_long_bars.append(bar)
        if len(self.bg_long_bars) > 500:
            self.bg_long_bars.pop(0)
        if not self.am_long.inited:
            return
        # print(
        #     f"[{self.long_bar_count}] 计数器 Bar: {bar.datetime} O:{bar.open_price} H:{bar.high_price} L:{bar.low_price} C:{bar.close_price}"
        #     f" pos_state info: {self.pos_state.direction}, {self.pos_state.entry_price},{self.pos_state.volume}, {self.pos_state.tp}, {self.pos_state.sl}"
        # )
        signal = self.long_signal_strategy.generate_entry_signal(self.am_long, bar, None)
        self.long_signal = signal
        # 平仓信号优先
        if signal in ["long", "short"]:
            self.output_msg(
                f"[on_long_bar] generate signal: direction={signal} start_bar={self.long_bar_count}"
            )
            # 立即反转平仓
            if signal == "long" and (
                self.pos_state.direction == "short" or getattr(self, "pos", 0) < 0
            ):
                self.close_position(bar.close_price, "Reversed long by long-window")
            elif signal == "short" and (
                self.pos_state.direction == "long" or getattr(self, "pos", 0) > 0
            ):
                self.close_position(bar.close_price, "Reversed short by long-window")

    # -------------------------
    # 短周期开仓
    # -------------------------
    def on_short_bar(self, bar: BarData):
        self.am_short.update_bar(bar)
        if not self.am_short.inited:
            return
        atr = self.am_long.atr(self.atr_window)
        side = self.long_signal
        if (side is not None):
            entry_signal = self.short_signal_strategy.generate_entry_signal(
                self.am_short, bar, side
            )
            if entry_signal == self.pos_state.direction and self.max_pos <= abs(self.pos):
                return
            if entry_signal == "long":
                self.open_long(
                    bar.close_price,
                    self.trade_volume,
                    bar.close_price - atr * self.sl_multiplier,
                    bar.close_price + atr * self.tp_multiplier,
                )
            elif entry_signal == "short":
                self.open_short(
                    bar.close_price,
                    self.trade_volume,
                    bar.close_price + atr * self.sl_multiplier,
                    bar.close_price - atr * self.tp_multiplier,
                )
            elif entry_signal == "close_long" and self.pos > 0:
                self.close_position(bar.close_price, "Reversed close_long by short-window")
            elif entry_signal == "close_short" and self.pos < 0:
                self.close_position(bar.close_price, "Reversed close_short by short-window")
        self.check_signal_exit(bar)

    # -------------------------
    # 开仓/平仓接口
    # -------------------------
    def open_long(self, price, volume, sl, tp):
        try:
            orderid = self.buy(price, volume)
        except:
            orderid = None
        self._pending_entry = {
            "side": "long",
            "price": price,
            "volume": volume,
            "sl": sl,
            "tp": tp,
            "orderid": orderid,
        }
        self.output_msg(
            f"[open_long] price={price} vol={volume} orderid={orderid} sl={sl} tp={tp}"
        )

    def open_short(self, price, volume, sl, tp):
        try:
            orderid = self.short(price, volume)
        except:
            orderid = None
        self._pending_entry = {
            "side": "short",
            "price": price,
            "volume": volume,
            "sl": sl,
            "tp": tp,
            "orderid": orderid,
        }
        self.output_msg(
            f"[open_short] price={price} vol={volume} orderid={orderid} sl={sl} tp={tp}"
        )

    def close_position(self, price, reason):
        if self.pos == 0 or self.close_position_flag:
            return
        vol = abs(self.pos)
        if self.pos < 0:
            dirn = "short"
        else:
            dirn = "long"
        try:
            if dirn == "long":
                orderid = self.sell(price, vol)
                self.output_msg(
                    f"[close_position： sell] side={dirn} price={price} vol={vol} orderid={orderid} reason={reason}"
                )
            else:
                orderid = self.cover(price, vol)
                self.output_msg(
                    f"[close_position： cover] side={dirn} price={price} vol={vol} orderid={orderid} reason={reason}"
                )
            self.close_position_flag = True
        except:
            orderid = None
        self._pending_close = {
            "side": dirn,
            "price": price,
            "volume": vol,
            "orderid": orderid,
            "reason": reason,
        }

    # -------------------------
    # SL/TP 检查
    # -------------------------
    def check_exit_conditions(self, bar: BarData):
        net_pos = getattr(self, "pos", None)
        if (net_pos is None or net_pos == 0) and self.pos_state.direction is None:
            return
        sl = self.pos_state.sl
        tp = self.pos_state.tp
        if self.pos_state.direction == "long":
            if sl and bar.low_price <= sl:
                self.close_position(sl, "SL_LONG hit")
            elif tp and bar.high_price >= tp:
                self.close_position(tp, "TP_LONG hit")
        elif self.pos_state.direction == "short":
            if sl and bar.high_price >= sl:
                self.close_position(sl, "SL_SHORT hit")
            elif tp and bar.low_price <= tp:
                self.close_position(tp, "TP_SHORT hit")

    # -------------------------
    # 插件接口：短周期信号触发平仓
    # -------------------------
    def check_signal_exit(self, bar: BarData):
        # 可由 short_signal_strategy 或其他插件实现反向平仓逻辑
        pass

    # -------------------------
    # 成交同步
    # -------------------------
    def on_trade(self, trade: TradeData):
        self.update_capital(trade)

        try:
            if trade.offset == Offset.OPEN:
                pending = self._pending_entry or {}
                if pending:
                    side = pending["side"]
                    sl = pending.get("sl")
                    tp = pending.get("tp")
                    self.pos_state.direction = side
                    self.pos_state.entry_price = trade.price
                    self.pos_state.volume = trade.volume
                    self.pos_state.sl = sl
                    self.pos_state.tp = tp
                    self._pending_entry = None
            # 如果收到平仓信号
            elif trade.offset == Offset.CLOSE:
                # 持有多头且收到平多信号
                if (
                    self.pos_state.direction == "long"
                    and trade.direction == Direction.SHORT
                ):
                    self.pos_state.volume -= trade.volume
                    if self.pos_state.volume <= 0:
                        self.pos_state = PositionState()
                # 持有空头且收到平空信号
                elif (
                    self.pos_state.direction == "short"
                    and trade.direction == Direction.LONG
                ):
                    self.pos_state.volume -= trade.volume
                    if self.pos_state.volume <= 0:
                        self.pos_state = PositionState()
                pending_close = self._pending_close or {}
                if pending_close:
                    self._pending_close = None
        except Exception as e:
            self.write_error(f"on_trade error: {e}")

    def on_order(self, order):
        self.output_msg(
            f"[on_order] orderid={order.orderid}, order bar={order.datetime}, "
            f"status={order.status}, is_buy={order.direction}, volume={order.volume}"
        )
        pass

    def on_stop_order(self, stop_order):
        self.output_msg(
            f"[on_stop_order] orderid={stop_order.orderid}, order bar={stop_order.datetime}, "
            f"status={stop_order.status}, is_buy={stop_order.direction}, volume={stop_order.volume}"
        )
        pass

    def on_stop(self):
        """回测结束时自动保存结果"""
        # if self.cta_engine.mode == "backtesting":  # 确保只在回测时运行
        try:
            # 获取回测引擎（注意：cta_engine 就是 BacktestingEngine 实例）
            self.cover_pos()
            engine = self.cta_engine
            print(f"mode: {self.cta_engine.mode}")
            df = engine.calculate_result()
            # 获取统计结果
            statistics = engine.calculate_statistics()
            if not statistics:
                self.write_log("回测结果为空，跳过保存")
                return

            # 调用你的保存函数
            save_results_fixed(engine, statistics)
            self.write_log("✅ 回测结果已自动保存到 backtest_results/ 目录")

        except Exception as e:
            self.write_log(f"❌ 保存回测结果失败: {str(e)}")
            import traceback

            self.write_log(traceback.format_exc())

    def update_capital(self, trade: TradeData):
        
        # 计算成交金额
        trade_amount = trade.volume * trade.price * self.cta_engine.size
        # 计算手续费
        commission = trade_amount * self.cta_engine.rate
        # 计算滑点成本（简化处理）
        slippage_cost = trade.price * self.cta_engine.size * self.cta_engine.slippage * 0.01
        # 根据交易方向更新资金
        if trade.direction == Direction.LONG:
            # 买入：资金减少
            self.leverage_capital -= trade_amount + commission + slippage_cost
        elif trade.direction == Direction.SHORT:
            # 卖出：资金增加（假设是平仓或做空）
            self.leverage_capital += trade_amount - commission - slippage_cost
        self.output_msg(
                f"leverage_capital: {self.leverage_capital}, trade_amount: {trade_amount},commission: {commission}, slippage_cost: {slippage_cost} "
                )
        if self.pos == 0:
            tmp_capital = self.current_capital
            self.close_position_flag = False
            self.current_capital = (
                self.cta_engine.capital
                + self.leverage_capital
                - self.cta_engine.capital * self.leverage_ratio
            )
            self.output_msg(
                f"current_capital: {self.current_capital} value: {self.current_capital - tmp_capital}"
                )
        self.output_msg(
            f"[on_trade] orderid={trade.orderid}, trade bar={trade.datetime}, "
            f"{trade.direction.name}-{trade.direction.value}-{trade.offset.name}, leverage_capital = {self.leverage_capital:.2f} "
            f"price={trade.price}, volume={trade.volume}, pos={self.pos}\n"
        )

    def output_msg(self, msg: str):
        print(msg)
        self.write_log(msg)

    def cover_pos(self):
        """更新当前资金"""
        # 获取当前持仓
        pos = self.pos
        # 计算当前市值
        if pos > 0:
            market_value = pos * self.last_bar_price * self.cta_engine.size
        elif pos < 0:
            market_value = pos * self.last_bar_price * self.cta_engine.size
        else:
            market_value = 0
        # 简化计算：实际需要考虑已实现盈亏
        # 这里只是一个示例
        self.leverage_capital += market_value
        self.output_msg(
            f"[cover_pos] capital = {self.current_capital:.2f},leverage_capital = {self.leverage_capital:.2f}"
        )
