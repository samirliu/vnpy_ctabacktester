class TripleTimeframeStrategy(CtaTemplate):
    """
    三周期策略标准骨架
    """

    author = "samirliu"

    # ========= 参数 =========
    long_kline = 2       # 4H
    mid_kline = 3        # 30m
    short_kline = 1      # 5m

    max_confirm_5m = 6   # 中周期信号的确认窗口（5m bars）

    init_bar_size = 500
    trade_volume = 1

    parameters = [
        "long_kline",
        "mid_kline",
        "short_kline",
        "max_confirm_5m",
        "trade_volume",
        "init_bar_size",
    ]

    variables = [
        "long_trend",
        "mid_bar_count",
        "short_bar_count",
    ]

    # ========= 初始化 =========
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # ---------- 状态 ----------
        self.long_trend: Optional[str] = None      # long / short / neutral
        self.pending_window: Optional[PendingWindow] = None

        self.mid_bar_count = 0
        self.short_bar_count = 0
        # ===== 趋势失效状态 =====
        self.trend_invalidated: bool = False
        self.invalidated_long_bar: int = 0
        self.long_bar_count: int = 0

        # grace period（4H bar 数）
        self.trend_invalidated_grace_period = 2

        # ---------- BarGenerator ----------
        self.bg_long = BarGenerator(
            self.on_bar,
            window=240,
            on_window_bar=self.on_long_bar,
            interval=Interval.MINUTE,
        )

        self.bg_mid = BarGenerator(
            self.on_bar,
            window=30,
            on_window_bar=self.on_mid_bar,
            interval=Interval.MINUTE,
        )

        self.bg_short = BarGenerator(
            self.on_bar,
            window=5,
            on_window_bar=self.on_short_bar,
            interval=Interval.MINUTE,
        )

        # ---------- ArrayManager ----------
        self.am_long = ArrayManager(self.init_bar_size)
        self.am_mid = ArrayManager(self.init_bar_size)
        self.am_short = ArrayManager(self.init_bar_size)

    # ========= 主 on_bar =========
    def on_bar(self, bar: BarData):
        self.bg_long.update_bar(bar)
        self.bg_mid.update_bar(bar)
        self.bg_short.update_bar(bar)

    # ========= 4H：趋势层 =========
    def on_long_bar(self, bar: BarData):
        self.long_bar_count += 1
        self.am_long.update_bar(bar)
        if not self.am_long.inited:
            return

        new_trend = self.detect_long_trend(bar)
        if self.trend_invalidated and new_trend == self.long_trend:
            self.write_log("[Trend Recovered] resume trading")
            self.trend_invalidated = False
        if new_trend != self.long_trend:
            self.on_trend_changed(bar, old=self.long_trend, new=new_trend)
            self.long_trend = new_trend
        # 趋势恢复（假破）



    def detect_long_trend(self, bar: BarData) -> Optional[str]:
        """
        你在这里放：
        - EMA
        - ADX
        - 结构判断
        """
        return None

    def on_trend_changed(self, bar: BarData, old, new):
        self.write_log(f"[Trend Changed] {old} → {new}")

        # 清空所有中周期候选
        self.pending_window = None

        # 已有仓位 → 进入趋势失效观察期
        if self.pos != 0:
            self.handle_trend_invalidation(bar, new)

    def handle_trend_invalidation(self, bar: BarData, new_trend):
        """
        趋势失效处理（进入 grace period）
        """
        # 第一次发现趋势冲突
        if not self.trend_invalidated:
            self.trend_invalidated = True
            self.invalidated_long_bar = self.long_bar_count

            self.write_log(
                f"[Trend Invalidated] pos={self.pos}, "
                f"waiting confirmation ({self.trend_invalidated_grace_period} bars)"
            )
            return
        else:
            bars_passed = self.long_bar_count - self.invalidated_long_bar
            # grace period 到期
            if bars_passed >= self.trend_invalidated_grace_period:
                # 趋势仍然与持仓方向冲突 → 确认反转
                if (
                    (self.pos > 0 and new_trend == "short") or
                    (self.pos < 0 and new_trend == "long")
                ):
                    self.write_log("[Trend Confirmed Reverse] force exit")
                    self.close_position(bar.close_price, "Reversed by long-window")
                self.trend_invalidated = False

    # ========= 30m：回调层 =========
    def on_mid_bar(self, bar: BarData):
        self.mid_bar_count += 1
        self.am_mid.update_bar(bar)

        if not self.am_mid.inited:
            return

        if self.long_trend is None:
            return
        if self.trend_invalidated:
            return
        signal = self.detect_mid_pullback(bar, self.long_trend)

        if signal and signal == self.long_trend:
            self.pending_window = PendingWindow(
                direction=signal,
                start_bar=self.mid_bar_count,
                expire_bar=self.short_bar_count + self.max_confirm_5m,
            )

            self.write_log(
                f"[MID] pullback={signal}, "
                f"window expires at short_bar={self.pending_window.expire_bar}"
            )

    def detect_mid_pullback(self, bar, trend) -> Optional[str]:
        """
        你在这里放：
        - Shenlong
        - Bollinger
        - 通道反转
        """
        return None

    # ========= 5m：执行层 =========
    def on_short_bar(self, bar: BarData):
        self.short_bar_count += 1
        self.am_short.update_bar(bar)

        if not self.am_short.inited:
            return

        if not self.pending_window:
            return
        if self.trend_invalidated:
            return        
        # -------- 过期判断 --------
        if self.short_bar_count > self.pending_window.expire_bar:
            self.write_log("[SHORT] pending window expired")
            self.pending_window = None
            return

        # -------- 动量确认 --------
        if self.confirm_short_trigger(bar, self.pending_window.direction):
            self.execute_trade(bar, self.pending_window.direction)
            self.pending_window = None

    def confirm_short_trigger(self, bar, direction) -> bool:
        """
        你在这里放：
        - 5m EMA
        - Momentum
        - Breakout
        """
        return False

    def execute_trade(self, bar, direction):
        if direction == "long":
            self.buy(bar.close_price, self.trade_volume)
        elif direction == "short":
            self.short(bar.close_price, self.trade_volume)

        self.write_log(f"[EXECUTE] {direction} at {bar.close_price}")

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
            else:
                orderid = self.cover(price, vol)
        except:
            orderid = None
