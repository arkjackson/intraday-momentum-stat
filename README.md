# 📈 Statistical Analysis of Intraday Price Persistence
### 장중 수급 불균형과 주가 지속성의 상관관계 분석: 체결강도 및 거래량 이상치를 중심으로

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Pandas](https://img.shields.io/badge/Pandas-Data_Analysis-150458) ![FinanceDataReader](https://img.shields.io/badge/FinanceDataReader-Market_Data-orange) ![KoreaInvestAPI](https://img.shields.io/badge/KIS_Open_API-Stock_Trading_API-green) ![Status](https://img.shields.io/badge/Status-Completed-success)

---

## 🔎 Research Question & Hypothesis

**RQ1.** 장 초반(09:00~10:00) 거래량 이상치(Volume Ratio)와 체결강도(Order Aggressiveness)가 당일 가격 지속성(Price Persistence)을 선행하는가?  

**RQ2.** 시간대별 유동성 구조를 반영한 **Dynamic Threshold**가 전체 분포 기반 **Static Threshold** 대비 리스크-조정 성과(Sharpe, MDD)를 개선하는가?

**H1.** 장 초반에 거래량 이상치 + 매수 주도 체결강도가 나타난 종목은, 당일(또는 단기) 가격이 **상승 방향으로 지속**될 확률이 증가한다.  

**H2.** 위 신호의 효력은 장 초반에 가장 크며, 시간이 지나면 빠르게 소멸한다(예: 5~10분 내).

---

## 📌 1. Project Overview (연구 배경 및 목적)

### Background
주식 시장 미시구조(Market Microstructure) 관점에서, 장 초반(**09:00~10:00**) 발생하는 비정상적인 거래량(Volume)과 체결강도(Order Aggressiveness)가 당일 주가 방향성을 선행하는지 검증하고자 한다.

### Objective
전일 대비 **5% 이상 상승한 모멘텀 종목군**을 대상으로, 통계적 임계치(Quartiles)를 활용한 진입 전략의 유효성을 정량적으로 분석하고 최적의 청산(Exit) 전략을 도출한다.

---

## ⚙️ 2. Methodology (방법론)

### 2.1 Data Pipeline
* **Source:** 한국투자증권(KIS) Open API
* **Data Spec:** 09:00 ~ 10:00 구간의 **30초 간격 고빈도 시계열 데이터(High-frequency Time Series)**
* **Data Duration:** 2025.08.04 ~ 2025.11.28
* **Process:** 실시간 스냅샷 수집 → 결측치 처리 → 파생변수 생성 → **CSV 파일 적재**

### 2.2 Feature Engineering (Signal Thresholds)
본 연구는 “의미있는 수급”을 포착하기 위해 아래 지표를 사용했다.

- **Strength (체결강도):** 총매수량 / 총매도량
- **Volume Ratio:** 당일 시간별 누적거래량 / 과거 20일 이동평균 거래량 (Top 25% 사용)

### 2.3 Feature Engineering (Signal Thresholds)
| Threshold Type | Definition | Applied Scenario             |
| :--- | :--- |:-----------------------------|
| **A. Static Threshold** (전체 시간 기준) | 09:00~10:00 **전체 분포**의 Top 25% (Q3) | 09:01\~ 09:59 (Full Range)   |
| **B. Dynamic Threshold** (시간별 기준) | **각 분(Minute)별 과거 분포**의 Top 25% (Q3) | 09:01\~09:05, 09:05\~09:10 등 |
| **Volume Ratio** | 20일 이동평균 대비 거래량 비율 (Top 25%) | 공통 적용                        |

> **Note:** 장 초반(09:00)의 거래량은 평소보다 압도적으로 많기 때문에, 시간대별 특성을 반영하기 위해 **Dynamic Threshold**를 별도로 고안했다.

### 2.4 Experimental Design
- **Backtest Period:** 2025.09.01 ~ 2025.11.28  
- **Factors (Ablation):**
  1) **Signal Logic:** Static Quantile vs Dynamic Quantile  
  2) **Time Window:** 09:01\~09:59, 09:01\~09:05, 09:01\~09:10, 09:05\~09:10  
  3) **Exit Strategy:** Fixed TP/SL, Time-cut Mix, Full Time-cut  

---

## 🧪 3. Backtest Assumptions

- **Universe:** 전일 대비 +5% 이상 상승 종목군
- **Execution:** 체결강도, 거래량 비율 시그널 만족시 진입
- **Transaction Costs:** 0.18%
- **Data Leakage Control:** Dynamic threshold 계산 시 **과거 데이터만 사용** 
- **Survivorship Bias:** 시가총액 상위 200 종목

---

## 📊 4. Results & Discussion (실험 결과 및 고찰)

### 4.1 Performance by Signal & Time (진입 시점 및 기준별 성과)
*청산 전략: 익절=종가 / 손절=-1% 기준 비교*

Dynamic Threshold를 적용하여 **09:05 이전**에 진입했을 때 가장 안정적인 성과(Sharpe 3.44)를 보였다.

| Time Window | Threshold Type | Return (%) | MDD (%) | Sharpe | Avg Tickers | Note |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **09:01 ~ 09:05** | **Dynamic** | 4.40 | **-1.05** | **3.44** | 5.13 | **Best Stability** |
| 09:01 ~ 09:59 | Static | **5.18** | -1.22 | 3.30 | 7.74 | Highest Return |
| 09:01 ~ 09:10 | Dynamic | 3.72 | -1.10 | 2.79 | 5.72 | - |
| 09:05 ~ 09:10 | Dynamic | 0.31 | -1.67 | 0.42 | 3.62 | Alpha Decay |

### 4.2 Performance by Exit Strategy
*기준 진입: 09:01~09:05 (Dynamic)*

| Strategy Type | Take Profit | Stop Loss | Return (%) | MDD (%) | Sharpe | Insight |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 🥇 **Time-cut Mix** | Market Close | **-1%** | **4.40** | **-1.05** | **3.44** | **Best Risk-Adjusted** |
| 🥈 Full Time-cut | Market Close | Market Close | 3.09 | -3.17 | 1.68 | High MDD |
| 🥉 Fixed Target | 2% | -1% | -0.89 | -1.80 | -1.36 | Upside Limited |

### 4.3 Key Insights

1.  **Importance of Dynamic Thresholds (동적 기준의 중요성)**
    * 전체 시간(Static) 기준으로 잡을 경우(09:59까지), 수익률은 높으나(5.18%) 거래 종목 수가 많고(7.74개) MDD가 다소 높다.
    * 반면, 시간별 유동성 변화를 반영한 **Dynamic Threshold**를 적용하여 09:05 이전에 짧게 끊어칠 때 샤프 지수(3.44)가 개선됨을 확인했다.
2.  **Alpha Decay in 5 Minutes**
    * 09:05 이후 진입 전략(0.31% 수익)은 성과가 현저히 떨어진다. 이는 장 초반의 수급 불균형(Inefficiency)이 **약 5분 이내에 해소**됨을 의미한다.
3.  **Let Profits Run & Cut Losses Short**
    * 익절을 제한한 전략(2%)은 실패했고, 손절을 타이트하게(-1%) 잡되 상방을 열어둔(종가 청산) 전략이 성공했다.

---

## 🛠 Tech Stack

* **Language:** Python 3.10+
* **Data Analysis:** Pandas, NumPy
* **Financial Library:** FinanceDataReader
* **API:** Korea Investment Securities (KIS) Open API

---

## 📂 Project Structure

```bash
├── config/                
│   └── backtest_config.py  # Backtest setting
├── data/                  # Raw Data (30s snapshots)
├── src/            
│   ├── data_loader.py      # Data Pipeline Logic
│   ├── indicators.py       # Stat Calculation (Thresholds)
│   └── utils.py            # API method
├── strategies/                
│   ├── buy_strategy.py    # Buy Strategy
│   └── sell_strategy.py   # Sell Strategy
├── utils/                
│   └── metrics.py         # Calculate Sharpe, MDD
├── main.py                # Execution Backtesting Script
├── requirements.txt       
└── README.md              # Project Documentation