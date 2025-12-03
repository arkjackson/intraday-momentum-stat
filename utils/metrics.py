import numpy as np

def calculate_mdd(balance_history):
    """최대 낙폭(MDD) 계산"""
    balance_array = np.array(balance_history)
    cumulative_max = np.maximum.accumulate(balance_array)
    drawdowns = (balance_array - cumulative_max) / cumulative_max
    return drawdowns.min() * 100

def calculate_sharpe_ratio(daily_returns, risk_free_rate=0.0):
    """샤프 비율 계산 (연율화)"""
    excess_returns = daily_returns - risk_free_rate
    if daily_returns.std() == 0: # 변동성이 0인 경우
        return 0
    return (excess_returns.mean() / daily_returns.std()) * np.sqrt(252)