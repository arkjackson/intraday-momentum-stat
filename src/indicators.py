from utils import KoreaInvestEnv, KoreaInvestAPI
import FinanceDataReader as fdr
from datetime import timedelta
from typing import List, Dict
from pathlib import Path
from loguru import logger
import time as pytime
import pandas as pd
import yaml

def get_market_open_days(start_date: str, end_date: str, include_prev: bool = False) -> pd.DatetimeIndex:
    """개장일 리스트업"""
    if include_prev:
        # 시작일 이전 거래일도 포함하기 위해 30일 더 일찍부터 조회
        extended_start = (pd.to_datetime(start_date) - timedelta(days=30)).strftime('%Y-%m-%d')
        trading_dates = fdr.DataReader('005930', start=extended_start, end=end_date).index.date
    else:
        trading_dates = fdr.DataReader('005930', start=start_date, end=end_date).index.date
    return trading_dates

def get_previous_trading_day(target_date: pd.Timestamp, all_trading_dates: pd.DatetimeIndex) -> pd.Timestamp:
    """개장일 기준 전일 추출"""
    prev_days = [d for d in all_trading_dates if d < target_date]
    return max(prev_days) if prev_days else None

def get_top_increase_rate(korea_invest_api, target_date: pd.Timestamp,
                          codes: List[str], previous_trading_day: pd.Timestamp) -> List[Dict]:
    """전일 대비 5% 이상 상승 종목 필터링"""
    prev_ratio_5_ranking_stocks = []

    for code in codes:
        prev_ratio = korea_invest_api.get_rate_compared_prev_day(code, target_date, previous_trading_day)
        if prev_ratio >= 5:
            prev_ratio_5_ranking_stocks.append({
                '종목코드': code,
                '일자': target_date,
                '전일대비': prev_ratio
            })
            logger.info(f"{target_date} - 종목코드: {code}, 전일대비: {prev_ratio}")
        pytime.sleep(0.05)

    return prev_ratio_5_ranking_stocks


def calculate_mean_volume(vol_data_df: pd.DataFrame, target_date: pd.Timestamp,
                          window_size: int) -> float:
    """평균 거래량 계산 (DataFrame 조회 최적화)"""
    vol_data_df = vol_data_df.reset_index()
    target_idx = vol_data_df[vol_data_df['Date'] == pd.to_datetime(target_date)].index

    if len(target_idx) == 0:
        raise ValueError(f"해당 날짜 {target_date}의 데이터를 찾을 수 없습니다.")

    target_idx = target_idx[0]
    start_idx = max(0, target_idx - window_size)
    mean_volume = vol_data_df.iloc[start_idx:target_idx]['Volume'].mean()

    return mean_volume


def process_time_column(df: pd.DataFrame) -> pd.DataFrame:
    """시간 컬럼 처리 (중복 제거 및 명확화)"""
    time_col = '현재시간' if '현재시간' in df.columns else '시간'

    if time_col not in df.columns:
        raise KeyError("DataFrame에 '현재시간' 또는 '시간' 컬럼이 없습니다.")

    df['시간변환'] = pd.to_datetime(df[time_col], format='%H:%M:%S').dt.floor('min')
    return df


def process_single_stock(code_info: Dict, data_path: Path, volume_data: pd.DataFrame,
                         window: int, time_index: pd.DatetimeIndex) -> tuple:
    """단일 종목 데이터 처리"""
    code = code_info['종목코드']
    td = code_info['일자']

    try:
        file_path = data_path / td.strftime('%Y%m%d') / f"{code}.csv"
        df = pd.read_csv(file_path)
        df = process_time_column(df)

        # 평균 거래량 계산
        vol_data = volume_data[code]
        mean_volume = calculate_mean_volume(vol_data, td, window)
        df['평균거래량_대비_누적거래량_비율'] = df['누적거래량'] / mean_volume * 100

        logger.info(f"종목코드: {code}, {window}일 평균거래량: {mean_volume}")

        # 거래량 데이터 준비
        volume_minute_df = df[['시간변환', '평균거래량_대비_누적거래량_비율']].copy()
        volume_minute_df.rename(
            columns={'평균거래량_대비_누적거래량_비율': f"{code}_{td.strftime('%Y%m%d')}"},
            inplace=True
        )

        # 강도 데이터 준비
        strength_minute_df = df[['시간변환', '누적강도']].copy()
        strength_minute_df.rename(
            columns={'누적강도': f"{code}_{td.strftime('%Y%m%d')}"},
            inplace=True
        )

        return volume_minute_df, strength_minute_df

    except Exception as e:
        logger.error(f"종목 {code} 처리 중 오류 발생: {e}")
        return None, None


def merge_dataframes(base_df: pd.DataFrame, data_list: List[pd.DataFrame]) -> pd.DataFrame:
    """여러 DataFrame을 효율적으로 병합"""
    for df in data_list:
        if df is not None:
            base_df = pd.merge(base_df, df, on='시간변환', how='left')

    # 중복 제거는 마지막에 한 번만
    base_df.drop_duplicates(subset=['시간변환'], keep='first', inplace=True)
    return base_df


def save_data_file(df: pd.DataFrame, filename: str) -> None:
    """데이터 파일 저장 (공통 함수)"""
    df['시간'] = pd.to_datetime(df['시간변환']).dt.strftime('%H:%M:%S')
    df.drop(columns='시간변환', inplace=True)

    # 시간 컬럼을 맨 앞으로 이동
    cols = df.columns.tolist()
    cols.insert(0, cols.pop(cols.index('시간')))
    df = df[cols]

    output_path = Path(filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"'{output_path}' 파일이 저장 완료!")


def main():
    # 설정 로드
    with open("./config.yaml", encoding='UTF-8') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)

    env_cls = KoreaInvestEnv(cfg)
    base_headers = env_cls.get_base_headers()
    cfg = env_cls.get_full_config()
    korea_invest_api = KoreaInvestAPI(cfg, base_headers=base_headers)

    # 데이터 로드
    volume_data = pd.read_pickle("../data/daily_volume_data.pkl")
    data_path = Path("../data")
    window = 20
    stock_codes = []  # 종목코드 리스트업

    # 기본 시간 인덱스 생성
    time_index = pd.date_range(start='1900-01-01 09:00', end='1900-01-01 09:59', freq='min')
    vol_base_df = pd.DataFrame({'시간변환': time_index})
    strength_base_df = pd.DataFrame({'시간변환': time_index})

    # 거래일 목록 조회 (시작일 이전 거래일도 포함)
    all_trading_dates = get_market_open_days('2025-08-04', '2025-11-28', include_prev=True)
    trading_date_list = [d for d in all_trading_dates if
                         pd.to_datetime('2025-08-04').date() <= d <= pd.to_datetime('2025-11-28').date()]

    # 이전 거래일 매핑
    prev_trading_days = {
        td: get_previous_trading_day(td, all_trading_dates)
        for td in trading_date_list
    }

    # 모든 필터링된 종목 수집
    all_filtered_stocks = []
    for td in trading_date_list:
        prev_day = prev_trading_days[td]
        if prev_day:
            filtered_stocks = get_top_increase_rate(korea_invest_api, td, stock_codes, prev_day)
            all_filtered_stocks.extend(filtered_stocks)

    # 병렬 처리로 종목 데이터 처리
    volume_dfs = []
    strength_dfs = []

    for stock_info in all_filtered_stocks:
        vol_df, str_df = process_single_stock(
            stock_info, data_path, volume_data, window, time_index
        )
        if vol_df is not None:
            volume_dfs.append(vol_df)
        if str_df is not None:
            strength_dfs.append(str_df)

    # DataFrame 병합
    vol_base_df = merge_dataframes(vol_base_df, volume_dfs)
    strength_base_df = merge_dataframes(strength_base_df, strength_dfs)

    # 파일 저장
    save_data_file(vol_base_df, f'../data/volume_ratio_data_{window}days.parquet')
    save_data_file(strength_base_df, '../data/strength_data.parquet')


if __name__ == "__main__":
    main()