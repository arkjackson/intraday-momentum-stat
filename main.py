from strategies.buy_strategy import process_single_stock, load_stock_file_cached
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.metrics import calculate_mdd, calculate_sharpe_ratio
from strategies.sell_strategy import execute_sell_strategy
from src.utils import KoreaInvestEnv, KoreaInvestAPI
from config.backtest_config import BacktestConfig
import FinanceDataReader as fdr
from loguru import logger
import pandas as pd
import yaml

def set_criteria_df(parquet_path, start_date, end_date):
    """기준 데이터프레임 생성 (중위수, 3분위수) - 최적화 버전"""
    df = pd.read_parquet(parquet_path)

    # 날짜 범위 컬럼 필터링 (벡터화)
    target_columns = []
    for col in df.columns:
        try:
            date_part_str = col.split('_')[1]
            col_date = pd.to_datetime(date_part_str, format='%Y%m%d')
            if start_date <= col_date <= end_date:
                target_columns.append(col)
        except (IndexError, ValueError):
            continue

    if not target_columns:
        return df[['시간']].assign(median=0, q3=0)

    # 분위수 계산
    quantiles = df[target_columns].quantile(q=[0.5, 0.75], axis=1)
    df['median'] = quantiles.loc[0.5]
    df['q3'] = quantiles.loc[0.75]

    return df[['시간', 'median', 'q3']].drop_duplicates(subset=['시간'], keep='first')

def main(korea_invest_api, stock_codes):
    logger.info(f"백테스트 시작 - 매도 전략: {BacktestConfig.SELL_STRATEGY.name}")

    # 초기화
    balance = BacktestConfig.INITIAL_BALANCE
    balance_history = []
    total_trade_result = {}
    total_stock_nums = 0

    # 테스트 날짜 리스트
    test_date_lst = fdr.DataReader('005930', start=BacktestConfig.TEST_START_DATE, end=BacktestConfig.TEST_END_DATE).index.date

    # 거래량 데이터 로드
    volume_data_df = pd.read_pickle(BacktestConfig.DAILY_VOLUME_PATH)

    # 백테스트 루프
    for idx in range(1, len(test_date_lst)):
        start_date = pd.to_datetime(BacktestConfig.CRITERIA_START_DATE) # 훈련 날짜 시작일
        end_date = pd.to_datetime(test_date_lst[idx - 1].strftime('%Y-%m-%d')) # 훈련 날짜 마지막일
        current_test_date = test_date_lst[idx] # 테스트 날짜

        logger.info(f"처리 중: {current_test_date} ({idx}/{len(test_date_lst) - 1})")

        volume_ratio_df = set_criteria_df(BacktestConfig.VOLUME_RATIO_PATH_TEMPLATE.format(window=BacktestConfig.VOLUME_WINDOW_SIZE), start_date, end_date)
        strength_df = set_criteria_df(BacktestConfig.STRENGTH_DATA_PATH, start_date, end_date)
        criteria_df = pd.merge(
            volume_ratio_df, strength_df,
            on="시간", suffixes=('_volume', '_strength')
        )
        criteria_df['시간'] = pd.to_datetime(criteria_df['시간'], format='%H:%M:%S').dt.time

        # 멀티스레딩으로 종목 처리
        result_watchlist = []
        with ThreadPoolExecutor(max_workers=BacktestConfig.MAX_WORKERS) as executor:
            # 매수 처리
            futures = {
                executor.submit(
                    process_single_stock,
                    code, current_test_date, criteria_df, volume_data_df,
                    BacktestConfig.VOLUME_WINDOW_SIZE, BacktestConfig.BUY_PRICE_PER_CODE
                ): code for code in stock_codes
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    result_watchlist.append(result)
                    balance -= result['보유수량'] * result['현재가']

            # 매도 처리
            trade_result = {}
            for info in result_watchlist:
                try:
                    date_path = f"{BacktestConfig.TIMESERIES_DATA_PATH}/{current_test_date.strftime('%Y%m%d')}"
                    data_df = load_stock_file_cached(info['종목코드'], date_path)

                    if data_df is None:
                        continue

                    # 매도 전략 실행
                    profit_rate, balance = execute_sell_strategy(
                        BacktestConfig.SELL_STRATEGY,
                        info, data_df, korea_invest_api, current_test_date,
                        balance, BacktestConfig.TRANSACTION_COST
                    )

                    trade_result[info['종목코드']] = profit_rate

                except Exception as e:
                    logger.error(f"매도 처리 오류 ({info['종목코드']}): {e}")

            total_trade_result[current_test_date.strftime('%Y%m%d')] = trade_result
            total_stock_nums += len(result_watchlist)
            balance_history.append(balance)

            logger.info(f"발견 종목수: {len(result_watchlist)}, 잔고: {balance:,.0f}원")

    print(f"\n{'=' * 60}")
    print(f"매도 전략: {BacktestConfig.SELL_STRATEGY.name}")
    print(f"{'=' * 60}")
    print(f"일 평균 거래 종목수: {total_stock_nums / (len(test_date_lst) - 1):.2f}개")

    # 성과 지표
    mdd = calculate_mdd(balance_history)
    daily_returns = pd.Series(balance_history).pct_change().dropna()
    sharpe_ratio = calculate_sharpe_ratio(daily_returns)
    total_return = (balance - BacktestConfig.INITIAL_BALANCE) / BacktestConfig.INITIAL_BALANCE * 100

    print(f"\n{'=' * 60}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Maximum Drawdown (MDD): {mdd:.2f}%")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Final Balance: {balance:,.0f}원")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    with open("./config.yaml", encoding='UTF-8') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)

    env_cls = KoreaInvestEnv(cfg)
    base_headers = env_cls.get_base_headers()
    cfg = env_cls.get_full_config()
    korea_invest_api = KoreaInvestAPI(cfg, base_headers=base_headers)

    stock_codes = [] # 종목코드 리스트업

    main(korea_invest_api, stock_codes)