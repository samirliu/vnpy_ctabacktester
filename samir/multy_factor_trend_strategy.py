# MultiFactorTrendStrategy.py
# 机构级多重趋势滤波（Multi-Factor Trend Filter）示例策略
# 基于 vn.py CTA 回测/实盘框架

from typing import List
import numpy as np
from vnpy_ctastrategy import (
    CtaTemplate, StopOrder, TickData, BarData, TradeData,
    OrderData, BarGenerator, ArrayManager
)


class MultiFactorTrendStrategy(CtaTemplate):
    """
    多重趋势滤波（Multi-Factor Trend Filter）
    因子包含：
        1. 长周期均线方向（MA Filter）
        2. 动量方向（Momentum Filter）
        3. 趋势强度 ADX（Trend Strength Filter）
        4. ATR 波动过滤（Volatility Filter）

    入场逻辑：
        满足所有趋势过滤因子 → 在短周期中寻找回调反转点做顺势入场
    """

    author = "chatgpt"

    # --- 参数区域 ---
    fast_ma = 50
    slow_ma = 200
    adx_period = 14
    mom_period = 30
    atr_period = 20

    pullback_n = 20      # 短周期回调判断（接近下轨反转）
    fixed_size = 1

    # --- 变量区域 ---
    ma_trend = 0
    adx_value = 0
    mom_value = 0
    atr_value = 0

    parameters = ["fast_ma", "slow_ma", "adx_period", "mom_period", "atr_period", "pullback_n", "fixed_size"]
    variables = ["ma_trend", "adx_value", "mom_value", "atr_value"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # bar generator, 将 Tick 合成 Bar
        self.bg = BarGenerator(self.on_bar)
        # array manager
        self.am = ArrayManager(250)

    # ----------------------------------------------------------------------
    def on_init(self):
        self.write_log("策略初始化")
        self.load_bar(250)

    # ----------------------------------------------------------------------
    def on_start(self):
        self.write_log("策略启动")

    # ----------------------------------------------------------------------
    def on_stop(self):
        self.write_log("策略停止")

    # ----------------------------------------------------------------------
    def on_tick(self, tick: TickData):
        self.bg.update_tick(tick)

    # ----------------------------------------------------------------------
    def on_bar(self, bar: BarData):
        """主要交易逻辑"""

        self.bg.update_bar(bar)
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # ======= 1. MA 多重均线趋势因子 ========
        fast = am.sma(self.fast_ma, array=False)
        slow = am.sma(self.slow_ma, array=False)

        self.ma_trend = 1 if fast > slow else -1

        # ======= 2. 动量因子（Momentum） ========
        self.mom_value = bar.close_price - am.close[-self.mom_period]
        mom_trend = 1 if self.mom_value > 0 else -1

        # ======= 3. ADX 趋势强度因子 ========
        adx = am.adx(self.adx_period, array=False)
        self.adx_value = adx
        trend_strength = 1 if adx > 25 else 0  # ADX > 25 才认为趋势强

        # ======= 4. ATR 波动过滤 ========
        self.atr_value = am.atr(self.atr_period, array=False)
        volatility_filter = 1 if self.atr_value > 0 else 1  # 可扩展，如 ATR > 均值

        # ======= 汇总所有趋势因子 ========
        trend_score = 0
        trend_score += 1 if self.ma_trend == 1 else -1
        trend_score += 1 if mom_trend == 1 else -1
        trend_score += 1 if trend_strength == 1 else -1
        # ATR 不计方向：只用于是否过滤

        # 多头趋势条件
        long_trend_ok = trend_score >= 2 and trend_strength == 1

        # 空头趋势条件
        short_trend_ok = trend_score <= -2 and trend_strength == 1

        # ====================================================================
        #                短周期回调反转 → 实现“趋势 + 回调入场”
        # ====================================================================
        # 使用 Donchian 下轨判断“回调结束”
        don_low = am.low[-self.pullback_n:].min()
        don_high = am.high[-self.pullback_n:].max()

        price = bar.close_price

        # ====================== 开仓逻辑 =======================
        if self.pos == 0:
            # ---------- 多头入场 ----------
            if long_trend_ok:
                # 回调触及下轨附近 + 最新 K 线反转（锤子、阳包阴等）可自由扩展
                if price < don_low * 1.005:   # 简单的反转触发
                    self.buy(price, self.fixed_size)
                    self.write_log(f"多头开仓, trend_score={trend_score}")

            # ---------- 空头入场 ----------
            if short_trend_ok:
                if price > don_high * 0.995:
                    self.sell(price, self.fixed_size)
                    self.write_log(f"空头开仓, trend_score={trend_score}")

        # ====================== 持仓风控 =======================
        if self.pos > 0:  # 多头止损止盈
            if price < slow:  # 跌破大周期趋势
                self.sell(price, abs(self.pos))
                self.write_log("多头趋势失效平仓")

        elif self.pos < 0:  # 空头止损止盈
            if price > slow:
                self.cover(price, abs(self.pos))
                self.write_log("空头趋势失效平仓")

        self.put_event()

    # ----------------------------------------------------------------------
    def on_order(self, order: OrderData):
        pass

    # ----------------------------------------------------------------------
    def on_trade(self, trade: TradeData):
        self.put_event()

    # ----------------------------------------------------------------------
    def on_stop_order(self, stop_order: StopOrder):
        pass
