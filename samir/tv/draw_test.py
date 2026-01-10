import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

# 读取 Excel
df = pd.read_excel(
    "etf_rotation_backtest_L20_forced_close.xlsx",
    sheet_name="EquityCurve"
)

df["Date"] = pd.to_datetime(df["Date"])

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(12, 6), sharex=True,
    gridspec_kw={"height_ratios": [2, 1]}
)

# ===== 净值曲线 =====
ax1.plot(df["Date"], df["Equity"], color="#3da5ff", lw=2)
ax1.axhline(1.0, color="gray", ls="--", lw=1)
ax1.set_ylabel("净值")
ax1.set_title("策略净值曲线")

# ===== 回撤曲线 =====
ax2.fill_between(
    df["Date"], df["Drawdown"], 0,
    color="red", alpha=0.35
)
ax2.set_ylabel("回撤 (%)")
ax2.set_xlabel("日期")

plt.tight_layout()
plt.show()
