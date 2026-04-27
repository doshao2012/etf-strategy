# 克隆自聚宽文章：https://www.joinquant.com/post/64948
# 标题：【策略分享】ETF轮动策略-四季发财组合-十年13倍
# 作者：屌丝逆袭量化

# 策略名称：ETF收益率稳定性轮动策略 - Huber回归版
# 策略作者：屌丝逆袭量化（基于原策略修改）
# 修改说明：使用Huber回归替代OLS，增强对异常值的鲁棒性

# 添加必要的导入
import numpy as np
import math
import pandas as pd
from scipy.optimize import least_squares

# ==================== Huber回归函数 ====================
def huber_objective(params, x, y, weights, delta=1.35):
    """
    Huber损失函数
    
    参数:
        params: [slope, intercept]
        x: 自变量
        y: 因变量
        weights: 权重
        delta: Huber阈值，默认1.35
    
    返回:
        加权Huber损失
    """
    slope, intercept = params
    residuals = y - (slope * x + intercept)
    # Huber损失：小残差(|r|<=delta)用平方，大残差用线性
    huber_loss = np.where(
        np.abs(residuals) <= delta,
        0.5 * residuals ** 2,
        delta * (np.abs(residuals) - 0.5 * delta)
    )
    return np.sqrt(weights) * huber_loss


def huber_regression(x, y, weights, delta=1.35):
    """
    Huber回归主函数
    
    参数:
        x: 自变量
        y: 因变量
        weights: 权重
        delta: Huber阈值
    
    返回:
        slope, intercept
    """
    # 初始值：OLS估计
    slope_init, intercept_init = np.polyfit(x, y, 1, w=weights)
    
    # 使用least_squares求解
    result = least_squares(
        huber_objective,
        x0=[slope_init, intercept_init],
        args=(x, y, weights, delta),
        bounds=([-np.inf, -np.inf], [np.inf, np.inf])
    )
    
    return result.x[0], result.x[1]


def calculate_r_squared_huber(x, y, weights, slope, intercept):
    """
    计算Huber回归的R²
    
    参数:
        x, y, weights: 数据
        slope, intercept: 回归系数
    
    返回:
        r_squared
    """
    ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    return 1 - ss_res / ss_tot if ss_tot else 0


# ==================== 策略主代码 ====================

def initialize(context):
    # ==================== 实盘交易设置 ====================
    set_option("avoid_future_data", True)  # 打开防未来函数
    set_option("use_real_price", True)     # 开启动态复权模式(真实价格)
    
    # 设置滑点
    set_slippage(FixedSlippage(0.0001), type="fund")
    set_slippage(FixedSlippage(0.003), type="stock")
    
    # 设置交易成本（ETF交易成本较低）
    set_order_cost(
        OrderCost(
            open_tax=0,               # 买入印花税
            close_tax=0.001,          # 卖出印花税
            open_commission=0.0003,   # 买入佣金
            close_commission=0.0003,  # 卖出佣金
            close_today_commission=0, # 今平佣金
            min_commission=5,         # 最低佣金
        ),
        type="fund",
    )
    
    # 设置货币ETF交易佣金为0
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )
    
    # 设置日志级别
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    
    log.info("策略初始化完成 - Huber回归版")

    # ==================== 策略参数设置 ====================
    g.etf_pool = [
        "159915.XSHE",  # 创业板ETF
        '588120.XSHG',  # 科创50ETF
        "518880.XSHG",  # 黄金ETF
        "513100.XSHG",  # 纳指ETF
        "511220.XSHG",  # 城投债ETF
    ]

    g.money_fund = "511880.XSHG"  # 银华日利

    # 策略参数
    g.lookback_days = 25  # 动量计算周期
    g.holdings_num = 1    # 只持有1只ETF
    g.stop_loss = 0.95    # 止损线
    g.loss = 0.97         # 近3日跌幅止损线
    g.defensive_etf = "511880.XSHG"  # 防御性ETF（货币ETF）
    g.min_score_threshold = 0  # 最低得分阈值
    g.max_score_threshold = 6.0  # 最高得分阈值
    g.min_money = 5000  # 最小交易金额
    g.huber_delta = 1.35  # Huber回归的delta参数
    
    # 持仓管理
    g.positions = {}

    # ==================== 交易调度 ====================
    run_daily(etf_trade, time='14:20')
    run_daily(check_positions, time='09:30')


def check_positions(context):
    """每日开盘后检查持仓状态"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")


def calculate_momentum_metrics(etf):
    """
    计算ETF动量得分 - Huber回归版
    
    【修改点】使用Huber回归替代OLS回归，增强对异常值的鲁棒性
    """
    try:
        # 获取历史价格数据
        prices = attribute_history(etf, g.lookback_days, '1d', ['close', 'high'])
        current_data = get_current_data()
        
        # 检查数据是否足够
        if len(prices) < g.lookback_days:
            return None
            
        # 获取当前价格并添加到价格序列中
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # 准备回归数据
        y = np.log(price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))  # 线性权重1-2，近期权重更高

        # ==================== 【核心修改】Huber回归 ====================
        # 替代原来的 np.polyfit(x, y, 1, w=weights)
        slope, intercept = huber_regression(x, y, weights, delta=g.huber_delta)
        # ==================== 修改结束 ====================
        
        # 计算年化收益率
        annualized_returns = math.exp(slope * 250) - 1

        # 计算R²（使用Huber回归的系数）
        r_squared = calculate_r_squared_huber(x, y, weights, slope, intercept)

        # 综合得分 = 年化收益率 * 趋势稳定性
        score = annualized_returns * r_squared

        # 短期风控：过滤近3日跌幅超过3%的ETF
        if len(price_series) >= 4:
            day1_ratio = price_series[-1] / price_series[-2]
            day2_ratio = price_series[-2] / price_series[-3]
            day3_ratio = price_series[-3] / price_series[-4]
            
            if min(day1_ratio, day2_ratio, day3_ratio) < g.loss:
                score = 0
                log.info(f"⚠️ {etf} {get_security_name(etf)} 近3日有单日跌幅超3%，已排除")
                

        return {
            'etf': etf,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'slope': slope,
            'current_price': current_price
        }
    except Exception as e:
        log.warn(f"计算{etf}动量指标时出错: {e}")
        return None


def get_ranked_etfs():
    """获取ETF排名"""
    etf_metrics = []
    for etf in g.etf_pool:
        metrics = calculate_momentum_metrics(etf)
        if metrics is not None:
            if 0 < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.info(f"排除异常值ETF: {etf} {get_security_name(etf)}，得分: {metrics['score']:.4f}")
    
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def get_security_name(security):
    """获取证券名称"""
    current_data = get_current_data()
    return current_data[security].name if security in current_data else security


def smart_order_target_value(security, target_value, context):
    """智能下单函数"""
    current_data = get_current_data()
    
    if current_data[security].paused:
        log.info(f"{security} {get_security_name(security)}: 今日停牌，跳过交易")
        return False

    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {get_security_name(security)}: 当前涨停，跳过买入")
        return False

    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {get_security_name(security)}: 当前跌停，跳过卖出")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {get_security_name(security)}: 当前价格为0，跳过交易")
        return False

    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {get_security_name(security)}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过交易")
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {get_security_name(security)}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            if security not in g.positions:
                g.positions[security] = 0
            g.positions[security] = target_amount
            
            security_name = get_security_name(security)
            if amount_diff > 0:
                log.info(f"📥 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                log.info(f"📤 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        else:
            log.warn(f"下单失败: {security} {get_security_name(security)}")
            return False
    
    return False


def is_defensive_etf_available():
    """检查防御性ETF是否可交易"""
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    
    if defensive_etf not in g.etf_pool:
        return False
        
    if current_data[defensive_etf].paused:
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        return False
        
    return True


def buy_money_fund(context):
    """尾盘买入货币基金"""
    available_cash = context.portfolio.available_cash
    
    if available_cash > g.min_money:
        success = smart_order_target_value(g.money_fund, available_cash, context)
        if success:
            log.info(f"💰 尾盘买入货币基金 {g.money_fund}")
    elif available_cash > 0:
        log.info(f"💵 闲置资金不足: {available_cash:.2f}")


def etf_trade(context):
    """ETF轮动交易主函数"""
    ranked_etfs = get_ranked_etfs()
    
    log.info("=== ETF趋势指标分析 (Huber回归) ===")
    for metrics in ranked_etfs:
        etf_name = get_security_name(metrics['etf'])
        log.info(f"{metrics['etf']} {etf_name}: 年化={metrics['annualized_returns']:.4f}, R²={metrics['r_squared']:.4f}, 得分={metrics['score']:.4f}")

    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= g.min_score_threshold:
        target_etf = ranked_etfs[0]['etf']
        top_metrics = ranked_etfs[0]
        etf_name = get_security_name(target_etf)
        log.info(f"🎯 正常模式，选择: {target_etf} {etf_name}，得分: {top_metrics['score']:.4f}")
    else:
        if is_defensive_etf_available():
            target_etf = g.defensive_etf
            log.info(f"🛡️ 进入防御模式")
        else:
            log.info("💤 进入空仓模式")
    
    target_etfs = [target_etf] if target_etf else []
    
    # 止损检查
    for security in list(context.portfolio.positions.keys()):
        if security in g.etf_pool and security in context.portfolio.positions:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                current_price = position.price
                cost_price = position.avg_cost
                if current_price <= cost_price * g.stop_loss:
                    success = smart_order_target_value(security, 0, context)
                    if success:
                        loss_percent = (current_price/cost_price-1)*100
                        log.info(f"🚨 止损卖出: {security}，亏损: {loss_percent:.2f}%")

    total_value = context.portfolio.total_value
    target_value = total_value if target_etfs else 0
    
    current_positions = set(context.portfolio.positions.keys())
    target_etfs_set = set(target_etfs)
    
    # 卖出不在目标列表中的ETF
    for security in current_positions:
        if security in g.etf_pool and security not in target_etfs_set:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                success = smart_order_target_value(security, 0, context)
                if success:
                    log.info(f"📤 卖出: {security}")

    # 调整目标ETF的仓位
    for etf in target_etfs:
        current_value = 0
        if etf in context.portfolio.positions:
            position = context.portfolio.positions[etf]
            if position.total_amount > 0:
                current_value = position.total_amount * position.price
        
        if abs(current_value - target_value) > target_value * 0.05 or current_value == 0:
            success = smart_order_target_value(etf, target_value, context)
            if success:
                etf_metrics = next((m for m in ranked_etfs if m['etf'] == etf), None)
                if etf_metrics:
                    log.info(f"📦 {'买入' if current_value < target_value else '调仓'}: {etf}，得分: {etf_metrics['score']:.4f}")


def trade(context):
    """主交易函数"""
    etf_trade(context)
