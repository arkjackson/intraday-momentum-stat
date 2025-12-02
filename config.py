from datetime import time
from enum import Enum


class SellStrategy(Enum):
    """매도 전략 선택"""
    INTRADAY_TARGET_STOPLOSS = 1  # 장중 익절(+2%) 및 손절(-1%)
    CLOSE_WITH_STOPLOSS = 2  # 종가 매도 + 장중 손절(-1%)
    CLOSE_ONLY = 3  # 종가 청산만

class BacktestConfig:
    # 경로 설정
    DATA_PATH = "../data"
    VOLUME_RATIO_PATH_TEMPLATE = "../data/volume_ratio_data_{window}days.parquet"
    STRENGTH_DATA_PATH = "../data/strength_data.parquet"
    DAILY_VOLUME_PATH = "./data/daily_volume_data.pkl"

    # 백테스트 기간
    TEST_START_DATE = "2025-08-29"
    TEST_END_DATE = "2025-11-28"
    CRITERIA_START_DATE = "2025-08-04"

    # 거래 설정
    VOLUME_WINDOW_SIZE = 20
    INITIAL_BALANCE = 100_000_000
    BUY_PRICE_PER_CODE = 5_000_000
    TRANSACTION_COST = 0.0018

    # 매도 전략 설정
    SELL_STRATEGY = SellStrategy.CLOSE_WITH_STOPLOSS
    TARGET_PROFIT_RATE = 1.02 # +2%
    STOP_LOSS_RATE = 0.99 # -1%

    # 성능 최적화
    MAX_WORKERS = 4
    CACHE_SIZE = 128

    # 시그널 시간
    SIGNAL_TIME_START = time(9, 1, 0)
    SIGNAL_TIME_END = time(9, 59, 0)