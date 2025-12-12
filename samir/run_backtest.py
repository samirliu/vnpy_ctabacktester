from enum import Enum
import sys
import os
import numpy as np
import json
from datetime import date, datetime
from vnpy_ctabacktester.engine import BacktestingEngine
from vnpy.trader.constant import Interval
# from dragen_channel_strategy_1128 import DragenStrategyExact as Strategy
from dual_timeframe_strategy import DualStrategy as Strategy

# from vnpy_ctastrategy.strategies.atr_rsi_strategy import AtrRsiStrategy as Strategy
# 添加当前目录到Python路径，确保可以导入自定义策略
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def run_backtest():
    """运行回测的完整示例"""

    print("=== vn.py 回测脚本 ===")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.executable}")

    try:
        # 创建回测引擎
        engine = BacktestingEngine()

        # 设置回测参数
        engine.set_parameters(
            vt_symbol="XAUUSD.COMEX",  # 确保这个品种的数据已导入
            interval=Interval.MINUTE,
            start=datetime(2023, 11, 21),
            end=datetime(2025, 11, 28),
            rate=2.5e-03,  # 手续费
            slippage=0.2,  # 滑点
            size=1000,  # 合约乘数
            pricetick=0.2,  # 最小价格变动
            capital=1000000,  # 初始资金
        )
        # 策略参数
        # setting = {
        #     "fixed_size": 1,
        #     "xma_n_3": 25,
        #     "xma_n_3_1": 25,
        #     "xma_n_2_1": 25,
        #     "xma_n_2": 25,
        #     "belt_weights_len": 20,
        #     "belt_smooth_period": 90,
        #     "target_intervals": "4H"
        # }
        # setting = {
        #     "long_kline": "4h",
        #     "short_kline": "30m",
        #     "signal_window": 4,
        #     "atr_window": 14,
        #     "sl_multiplier": 3,
        #     "tp_multiplier": 3,
        #     "max_trades_per_window": 1,
        #     "trade_volume": 1,
        #     "short_fast_ema": 2,
        #     "short_slow_ema": 30
        # }
        setting = {
            "long_kline": 1,
            "short_kline": 3,
            "signal_window": 4,
            "atr_window": 14,
            "sl_multiplier": 3,
            "tp_multiplier": 3,
            "short_fast_ema": 2,
            "short_slow_ema": 30,
            "init_bar_size": 300
        }
        # 添加策略
        engine.add_strategy(Strategy, setting)
        # 导入您的策略（确保策略文件在同一目录）

        print("成功导入策略: LlmStrategyExact")
    except ImportError as e:
        print(f"导入策略失败: {e}")
        print("请确保 dragen_channel_strategy.py 文件在当前目录")
        return

    try:
        # 加载数据
        print("正在加载数据...")
        engine.load_data()
        print("数据加载完成")

        # 运行回测
        print("开始回测...")
        engine.run_backtesting()
        print("回测完成")

        # 计算结果
        # df = engine.calculate_result()
        # # 输出统计结果
        # statistics = engine.calculate_statistics()
        # print("\n=== 回测统计结果 ===")
        # for key, value in statistics.items():
        #     print(f"{key}: {value}")
        # 显示图表
        engine.show_chart()

        # 保存结果
        # save_results_fixed(engine, statistics)
        return engine
    except Exception as e:
        print(f"回测过程中出错: {e}")
        import traceback

        traceback.print_exc()



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

# 在您的回测脚本中调用：
# save_results_fixed(engine, statistics)


if __name__ == "__main__":
    run_backtest()
