from utils import KoreaInvestEnv, KoreaInvestAPI
from datetime import datetime, time
from collections import defaultdict
from loguru import logger
import time as pytime
import pandas as pd
import threading
import queue
import yaml
import os

def wait_until_start(start_time):
    now = datetime.now()
    if now >= start_time:
        return
    time_to_wait = (start_time - now).total_seconds()
    logger.info(f"⏳ 장 시작 전입니다. 현재 시간: {datetime.now().time().strftime('%H:%M:%S')}")
    pytime.sleep(time_to_wait)

def calculate_buy_sell_volumes(strength, total_volume):
    total_buy = 0
    total_sell = 0
    # vs가 NaN인 경우 -> 첫번째 데이터의 경우, 계산X
    if strength is None or strength == 0:
        total_buy = 0
        total_sell = 0
    # 그 외 (vs가 정상적인 양수)
    elif strength is not None and total_volume > 0:
        total_buy = round(((strength * total_volume) / (100 + strength)), 0)
        total_sell = total_volume - total_buy

    return total_buy, total_sell

def create_directory(base_path: str="./data"):
    folder_name = datetime.now().strftime('%Y%m%d')
    directory_path = os.path.join(base_path, folder_name)
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        logger.info(f"폴더 '{folder_name}'이 생성되었습니다.")
    else:
        logger.info(f"폴더 '{folder_name}'가 이미 존재합니다.")
    return directory_path

class KISDataLoader:
    def __init__(self):
        self.first_volume_dict = dict()
        self.data_queue = queue.Queue()  # 수신 데이터 보관
        self.stop_event = threading.Event()  # 스레드 종료 신호 관리
        self.first_time_check_data_collected = False # 첫번째 데이터 수집 여부 확인+
        self.collected_data = defaultdict(list)  # 수신한 데이터 전체 관리

    def _get_first_time_data(self, code):
        try:
            return korea_invest_api.get_first_time_hoga_remaining_info(code)
        except Exception as e:
            logger.info(f"종목코드:{code}, 주식현재가 호가/예상체결 수집 실패: {e}")
            return None, None, None, None, None

    def _get_regular_data(self, code):
        try:
            rate_compared_prev_day, cumulative_volume, pr_price, strength = korea_invest_api.get_daily_trades(code)
        except Exception as e:
            logger.info(f"종목코드:{code}, 현재가 정보 수집 실패: {e}")
            rate_compared_prev_day, cumulative_volume, pr_price, strength = None, None, None, None

        try:
            total_ask, total_bid, estimated_change = korea_invest_api.get_hoga_remaining_info(code)
        except Exception as e:
            logger.info(f"종목코드:{code}, 호가 정보 수집 실패: {e}")
            total_ask, total_bid, estimated_change = None, None, None

        return rate_compared_prev_day, cumulative_volume, pr_price, strength, total_ask, total_bid, estimated_change

    def _wait_for_remaining_time(self, start_time, target_time):
        """남은 시간만큼 대기"""
        elapsed = pytime.perf_counter() - start_time
        if elapsed < target_time:
            pytime.sleep(target_time - elapsed)

    def _collect_queue_data(self):
        """큐에서 데이터 수집"""
        try:
            data = self.data_queue.get(timeout=1)
            code_num = data['종목코드']
            self.collected_data[code_num].append(data)
            return True
        except queue.Empty:
            pytime.sleep(0.1)
            return False
        except Exception as e:
            logger.exception(f"조건 체크 중 예외 발생: {e}")
            return False

    def is_program_endtime(self, end_time):
        if datetime.now() > end_time:
            return True
        else:
            return False

    def save_collected_data_to_csv(self, collected_data, folder_path):
        today_date = datetime.now().strftime('%Y%m%d')
        for stock_code, data_list in collected_data.items():
            if not data_list:
                continue
            file_path = os.path.join(folder_path, f"{stock_code}_{today_date}.csv")
            df = pd.DataFrame(data_list)

            df['종목코드'] = 'A' + df['종목코드'].astype(str)
            save_to_cols = ['시간', '종목코드', '시초가', '현재가', '전일대비', '누적거래량', '누적강도', '총매도량', '총매수량', '총매도잔량', '총매수잔량', '잔량비율',]
            df[save_to_cols].to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"종목코드 {stock_code} 저장 완료!")

    def fetch_30s_snapshot(self, stock_codes, data_save_path, program_end_time):
        def collect_data():
            chunk_size = 6
            chunk_time = 1.44  # 1.44 (20250916 테스트 일자) -> 잘 나옴
            while not self.stop_event.is_set():
                cycle_start_time = pytime.perf_counter()
                logger.info(f"{len(stock_codes)} 종목 데이터 수신 시작")

                for i in range(0, len(stock_codes), chunk_size):
                    code_chunk = stock_codes[i:i + chunk_size]
                    chunk_start_time = pytime.perf_counter()

                    for code in code_chunk:
                        tr_request_time = datetime.now().strftime("%H:%M:%S")

                        if not self.first_time_check_data_collected:  # 첫번재 데이터 수신
                            estimated_change, indicative_opening_price, indicative_opening_volume, total_ask, total_bid = self._get_first_time_data(code)  # TR 1회

                            stock_data_dict = {
                                "시간": tr_request_time,
                                "종목코드": code,
                                "시초가": estimated_change,
                                "현재가": indicative_opening_price,
                                "전일대비": estimated_change,
                                "총매도량": 0,
                                "총매수량": 0,
                                "총매도잔량": total_ask,
                                "총매수잔량": total_bid,
                                "잔량비율": round(total_bid / total_ask * 100, 2) if total_ask != 0 else total_bid,
                                "누적거래량": indicative_opening_volume if indicative_opening_volume is not None else 0,
                                "누적강도": 0,
                            }
                            self.first_volume_dict[code] = indicative_opening_volume
                        else:
                            # 두번째~ 데이터 수신
                            rate_compared_prev_day, cumulative_volume, pr_price, strength, total_ask, total_bid, estimated_change = self._get_regular_data(code)  # TR 2회

                            # 총매수량, 총매도량 계산
                            first_volume = self.first_volume_dict.get(code)
                            if first_volume is not None and strength is not None and cumulative_volume is not None:
                                cumulative_buy_volume, cumulative_sell_volume = calculate_buy_sell_volumes(strength, cumulative_volume - first_volume)
                            else:
                                cumulative_buy_volume, cumulative_sell_volume = None, None

                            stock_data_dict = {
                                "시간": tr_request_time,
                                "종목코드": code,
                                "시초가": estimated_change,
                                "현재가": pr_price,
                                "전일대비": rate_compared_prev_day,
                                "총매도량": cumulative_sell_volume,
                                "총매수량": cumulative_buy_volume,
                                "총매도잔량": total_ask,
                                "총매수잔량": total_bid,
                                "잔량비율": round(total_bid / total_ask * 100, 2) if total_ask != 0 else total_bid,
                                "누적거래량": cumulative_volume,
                                "누적강도": strength
                            }
                        self.data_queue.put(stock_data_dict)
                        pytime.sleep(0.05)

                    # 청크 간격 조정 (18TR/1.44sec)
                    self._wait_for_remaining_time(chunk_start_time, chunk_time)

                logger.info(f"{len(stock_codes)} 종목 데이터 수신 완료")

                if not self.first_time_check_data_collected:
                    self.first_time_check_data_collected = True

                # 종목당 텀 관리 (30sec)
                self._wait_for_remaining_time(cycle_start_time, 30)

            logger.info(f"Thread 1 (collect_data) 활성시간이 종료되었습니다.")

        def set_data():
            while not self.stop_event.is_set():
                if not self._collect_queue_data():
                    continue

        threads = [
            threading.Thread(target=collect_data, daemon=True),
            threading.Thread(target=set_data, daemon=True),
        ]

        for t in threads:
            t.start()

        # 종료 시간 감시 루프
        while not self.stop_event.is_set():
            if self.is_program_endtime(program_end_time):
                logger.info("⏰ 종료 시간 도달. 프로그램 종료 중...")
                self.stop_event.set()
            pytime.sleep(1)

        for t in threads:
            t.join()

        self.save_collected_data_to_csv(self.collected_data, data_save_path)

        logger.info(f"✅ 프로그램 정상 종료")

if __name__ == "__main__":
    with open("./config.yaml", encoding='UTF-8') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
    env_cls = KoreaInvestEnv(cfg)
    base_headers = env_cls.get_base_headers()
    cfg = env_cls.get_full_config()
    korea_invest_api = KoreaInvestAPI(cfg, base_headers=base_headers)

    program_start_time = datetime.combine(datetime.today(), time(9, 0, 30))  # 09:00:30 시작
    program_end_time = datetime.combine(datetime.today(), time(10, 0, 0))

    stock_codes = [] # 종목코드 리스트업

    data_save_path = create_directory(base_path='./data')
    stream_processor = KISDataLoader()
    wait_until_start(program_start_time)  # 프로그램 실행 시작 시간까지 대기

    stream_processor.fetch_30s_snapshot(stock_codes, data_save_path, program_end_time)