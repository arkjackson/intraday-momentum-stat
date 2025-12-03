from config.backtest_config import BacktestConfig
from functools import lru_cache
from loguru import logger
import pandas as pd
import os, glob

@lru_cache(maxsize=BacktestConfig.CACHE_SIZE)
def load_stock_file_cached(stock_code: str, directory_path: str):
    """파일 로딩 (캐싱 적용)"""
    # 1순위: 종목코드.csv
    file_path_1 = os.path.join(directory_path, f"{stock_code}.csv")
    if os.path.exists(file_path_1):
        try:
            return pd.read_csv(file_path_1)
        except Exception as e:
            logger.warning(f"파일 로드 오류 ({file_path_1}): {e}")

    # 2순위: 종목코드_*.csv
    search_pattern = os.path.join(directory_path, f"{stock_code}_*.csv")
    file_list = glob.glob(search_pattern)

    if file_list:
        try:
            return pd.read_csv(file_list[0])
        except Exception as e:
            logger.warning(f"파일 로드 오류 ({file_list[0]}): {e}")

    return None

def process_minute_data(df: pd.DataFrame) -> pd.DataFrame:
    """분 단위 데이터 리샘플링 - 최적화 버전"""
    time_col = '현재시간' if '현재시간' in df.columns else '시간'
    if time_col not in df.columns:
        raise KeyError("DataFrame에 '현재시간' 또는 '시간' 컬럼이 없습니다.")

    df = df.copy()
    df['시간'] = pd.to_datetime(df[time_col], format='%H:%M:%S')
    result = df.set_index('시간').resample('min').first().reset_index()

    return result

def process_single_stock(code, current_test_date, criteria_df, volume_data_df, volume_window_size, buy_price_by_code):
    try:
        # 데이터 로드
        date_path = f"{BacktestConfig.TIMESERIES_DATA_PATH}/{current_test_date.strftime('%Y%m%d')}"
        test_df = load_stock_file_cached(code, date_path)
        if test_df is None:
            return None
        test_df = process_minute_data(test_df)

        prev_volumes = volume_data_df[code].loc[:pd.to_datetime(current_test_date)].iloc[:-1].tail(volume_window_size)
        average_mean_vol = prev_volumes.mean()

        if average_mean_vol == 0:
            return None

        test_df['volume_ratio'] = test_df['누적거래량'] / average_mean_vol * 100

        test_df['시간'] = pd.to_datetime(test_df['시간']).dt.time

        final_df = pd.merge(
            criteria_df,
            test_df[['시간', 'volume_ratio', '누적강도', '현재가', '전일대비']],
            on="시간"
        )

        time_limit_df = final_df[
            final_df['시간'].between(
                BacktestConfig.SIGNAL_TIME_START,
                BacktestConfig.SIGNAL_TIME_END
            )
        ]

        if time_limit_df.empty:
            return None

            # 매수 조건 확인
            """누적체결강도 조건: 시간별 3분위수"""
            # condition = (
            #         (time_limit_df['q3_volume'] <= time_limit_df['volume_ratio']) &
            #         (time_limit_df['q3_strength'] <= time_limit_df['누적강도']) &
            #         (time_limit_df['전일대비'] > 0)
            # )

            q3_strength_q3 = criteria_df['q3_strength'].quantile(q=[0.5, 0.75]).loc[0.75]
            """누적체결강도 조건: 전체 시간의 3분위수"""
            condition = (time_limit_df['q3_volume'] <= time_limit_df[f'volume_ratio']) & \
                        (q3_strength_q3 <= time_limit_df['누적강도']) & \
                        (0 < time_limit_df['전일대비'])

            if condition.any():
                satisfying_row = time_limit_df[condition].iloc[0]
                buy_nums = buy_price_by_code // satisfying_row['현재가']

                return {
                    '종목코드': code,
                    '시간': satisfying_row['시간'],
                    '현재가': satisfying_row['현재가'],
                    '전일대비': satisfying_row['전일대비'],
                    '보유수량': buy_nums
                }

    except Exception as e:
        logger.warning(f"종목 {code} 처리 중 오류: {e}")

    return None