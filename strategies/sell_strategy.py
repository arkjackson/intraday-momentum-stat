from config.backtest_config import SellStrategy, BacktestConfig
from loguru import logger
import time as pytime
import pandas as pd

def find_first_target_or_stoploss(df, buy_price, buy_time):
    """장중 익절(+2%) 또는 손절(-1%) 찾기 - 최적화 버전"""
    target_price = buy_price * BacktestConfig.TARGET_PROFIT_RATE
    stop_loss_price = buy_price * BacktestConfig.STOP_LOSS_RATE

    # 시간 필터링 (벡터화)
    df = df.copy()
    df['시간_obj'] = pd.to_datetime(df['시간'], format='%H:%M:%S').dt.time
    after_buy_df = df[df['시간_obj'] > buy_time]

    if after_buy_df.empty:
        return 0

    # 익절/손절 조건 확인
    for idx, row in after_buy_df.iterrows():
        current_price = row['현재가']
        if current_price >= target_price:
            logger.info(f"익절 도달! 가격: {current_price:,.0f}원")
            return 2
        elif current_price <= stop_loss_price:
            logger.info(f"손절 도달! 가격: {current_price:,.0f}원")
            return -1

    return 0

def find_stoploss(df, buy_price, buy_time):
    """장중 손절(-1%)만 찾기 - 최적화 버전"""
    stop_loss_price = buy_price * BacktestConfig.STOP_LOSS_RATE

    # 시간 필터링
    df = df.copy()
    df['시간_obj'] = pd.to_datetime(df['시간'], format='%H:%M:%S').dt.time
    after_buy_df = df[df['시간_obj'] > buy_time]

    if after_buy_df.empty:
        return 0

    # 손절 조건 확인
    for idx, row in after_buy_df.iterrows():
        if row['현재가'] <= stop_loss_price:
            logger.info(f"손절 발생! 가격: {row['현재가']:,.0f}원")
            return -1

    return 0

def execute_sell_strategy(strategy, info, data_df, korea_invest_api, current_test_date, balance, transaction_cost):
    """매도 전략 실행"""
    buy_price = info['현재가']
    buy_time = info['시간']
    holding_qty = info['보유수량']
    code = info['종목코드']

    # 종가 가져오기
    close_price = korea_invest_api.get_close_price(code, current_test_date)
    pytime.sleep(0.05)

    if strategy == SellStrategy.INTRADAY_TARGET_STOPLOSS:
        # 1. 장중 익절(+2%) 및 손절(-1%)
        result = find_first_target_or_stoploss(data_df, buy_price, buy_time)

        if result == 2:  # 익절
            sell_price = buy_price * BacktestConfig.TARGET_PROFIT_RATE
            balance += holding_qty * sell_price * (1 - transaction_cost)
            return 2.0, balance
        elif result == -1:  # 손절
            sell_price = buy_price * BacktestConfig.STOP_LOSS_RATE
            balance += holding_qty * sell_price * (1 - transaction_cost)
            return -1.0, balance
        else:  # 종가 매도
            profit_rate = (close_price - buy_price) / buy_price * 100
            balance += holding_qty * close_price * (1 - transaction_cost)
            return profit_rate, balance

    elif strategy == SellStrategy.CLOSE_WITH_STOPLOSS:
        # 2. 종가 매도 + 장중 손절(-1%)
        if find_stoploss(data_df, buy_price, buy_time) == -1:
            sell_price = buy_price * BacktestConfig.STOP_LOSS_RATE
            balance += holding_qty * sell_price * (1 - transaction_cost)
            logger.info(f"{current_test_date} - {code} 손절: -1%")
            return -1.0, balance
        else:
            profit_rate = (close_price - buy_price) / buy_price * 100
            # 종가 기준으로도 -1% 이하면 손절 적용
            if profit_rate < -1:
                profit_rate = -1.0
                sell_price = buy_price * BacktestConfig.STOP_LOSS_RATE
                balance += holding_qty * sell_price * (1 - transaction_cost)
            else:
                balance += holding_qty * close_price * (1 - transaction_cost)

            logger.info(f"{current_test_date} - {code} 수익률: {profit_rate:.2f}%")
            return profit_rate, balance

    else:  # SellStrategy.CLOSE_ONLY
        # 3. 종가 청산만
        profit_rate = (close_price - buy_price) / buy_price * 100
        balance += holding_qty * close_price * (1 - transaction_cost)
        logger.info(f"{current_test_date} - {code} 수익률: {profit_rate:.2f}%")
        return profit_rate, balance