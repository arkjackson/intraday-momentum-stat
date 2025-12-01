# 📈 Statistical Analysis of Intraday Price Persistence
### 장중 수급 불균형과 주가 지속성의 상관관계 분석: 체결강도 및 거래량 이상치를 중심으로

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Pandas](https://img.shields.io/badge/Pandas-Data_Analysis-150458) ![Backtrader](https://img.shields.io/badge/Backtrader-Backtesting-green) ![Status](https://img.shields.io/badge/Status-Completed-success)

## 📌 1. Project Overview (연구 배경 및 목적)

### Background
주식 시장 미시구조(Market Microstructure) 관점에서, 장 초반(**09:00~10:00**) 발생하는 비정상적인 거래량(Volume)과 체결강도(Order Aggressiveness)가 당일 주가 방향성을 선행하는지 검증하고자 합니다.

### Objective
전일 대비 **5% 이상 상승한 모멘텀 종목군**을 대상으로, 통계적 임계치(Quartiles)를 활용한 진입 전략의 유효성을 정량적으로 분석하고 최적의 청산(Exit) 전략을 도출합니다.

---

## ⚙️ 2. Methodology (방법론)

### 2.1 Data Pipeline
* **Source:** 한국투자증권(KIS) Open API
* **Data Spec:** 09:00 ~ 10:00 구간의 **30초 간격 고빈도 시계열 데이터(High-frequency Time Series)**
* **Process:** 실시간 스냅샷 수집 → 결측치 처리 → 파생변수 생성 → **CSV 파일 적재**

### 2.2 Feature Engineering (Signal Thresholds)
단순 급등이 아닌 '유의미한 수급'을 판단하기 위해 두 가지 방식의 임계치(Threshold)를 적용하여 비교했습니다.

| Threshold Type | Definition | Applied Scenario |
| :--- | :--- | :--- |
| **A. Static Threshold**<br>(전체 시간 기준) | 09:00~10:00 **전체 데이터 분포**의 Top 25% (3분위수) | 09:01 ~ 09:59 (Full Range) 실험 시 사용 |
| **B. Dynamic Threshold**<br>(시간별 기준) | **각 분(Minute)별 과거 데이터 분포**의 Top 25% (3분위수) | 09:05, 09:10 등 세부 구간 실험 시 사용 |
| **Volume Ratio** | 20일 이동평균 거래량 대비 비율 (Top 25%) | 공통 적용 |

> **Note:** 장 초반(09:00)의 거래량은 평소보다 압도적으로 많기 때문에, 시간대별 특성을 반영하기 위해 **Dynamic Threshold**를 별도로 고안했습니다.

### 2.3 Experimental Design
* **Period:** 2025.09.01 ~ 2025.11.28
* **Variables:**
    1.  **Signal Logic:** Static Quantile vs. Dynamic Quantile
    2.  **Time Window:** 09:01~09:59, 09:01~09:05, 09:05~09:10
    3.  **Exit Strategy:** Fixed TP/SL, Time-cut Mix, Full Time-cut

---

## 📊 3. Results & Discussion (실험 결과 및 고찰)

### 3.1 Performance by Signal & Time (진입 시점 및 기준별 성과)
*가장 성과가 우수했던 청산 전략(익절: 종가 / 손절: -1%) 기준 비교*

시간별 특성을 반영한 동적 기준(Dynamic Threshold)을 적용하여 장 초반(09:05 이전)에 진입했을 때 가장 안정적인 성과(Sharpe 3.44)를 보였습니다.

| Time Window | Threshold Type | Return (%) | MDD (%) | Sharpe Ratio | Avg Tickers | Note |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **09:01 ~ 09:05** | **Dynamic (Time-specific)** | 4.40% | **-1.05%** | **3.44** | 5.13 | **Best Stability** |
| 09:01 ~ 09:59 | Static (Global) | **5.18%** | -1.22% | 3.30 | 7.74 | Highest Return |
| 09:01 ~ 09:10 | Dynamic (Time-specific) | 3.72% | -1.10% | 2.79 | 5.72 | - |
| 09:05 ~ 09:10 | Dynamic (Time-specific) | 0.31% | -1.67% | 0.42 | 3.62 | Alpha Decay |

### 3.2 Performance by Exit Strategy (청산 전략별 성과)
*가장 안정적이었던 '09:01 ~ 09:05 (Dynamic)' 진입 전략 기준 비교*

단순 승률보다는 **손익비(R/R Ratio)** 관리가 핵심임을 입증했습니다.

| Strategy Type | Take Profit | Stop Loss | Return (%) | MDD (%) | Sharpe Ratio | Insight |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 🥇 **Time-cut Mix** | **Market Close** | **-1%** | **4.40%** | **-1.05%** | **3.44** | **Best Risk-Adjusted Return** |
| 🥈 Full Time-cut | Market Close | Market Close | 3.09% | -3.17% | 1.68 | High MDD (No Risk Mgmt) |
| 🥉 Fixed Target | 2% | -1% | -0.89% | -1.80% | -1.36 | Upside Limited |

### 3.3 Key Insights

1.  **Importance of Dynamic Thresholds (동적 기준의 중요성)**
    * 전체 시간(Static) 기준으로 잡을 경우(09:59까지), 수익률은 높으나(5.18%) 거래 종목 수가 많고(7.74개) MDD가 다소 높습니다.
    * 반면, 시간별 유동성 변화를 반영한 **Dynamic Threshold**를 적용하여 09:05 이전에 짧게 끊어칠 때 샤프 지수(3.44)가 개선됨을 확인했습니다.
2.  **Alpha Decay in 5 Minutes**
    * 09:05 이후 진입 전략(0.31% 수익)은 성과가 현저히 떨어집니다. 이는 장 초반의 수급 불균형(Inefficiency)이 **약 5분 이내에 해소**됨을 의미합니다.
3.  **Let Profits Run & Cut Losses Short**
    * 익절을 제한한 전략(2%)은 실패했고, 손절을 타이트하게(-1%) 잡되 상방을 열어둔(종가 청산) 전략이 성공했습니다.

---

## 🛠 Tech Stack

* **Language:** Python 3.10
* **Data Analysis:** Pandas, NumPy
* **Financial Library:** FinanceDataReader
* **API:** Korea Investment Securities (KIS) Open API

---

## 📂 Project Structure

```bash
├── data/                  # Raw Data (30s snapshots)
├── src/            
│   ├── data_loader.py      # Data Pipeline Logic
│   ├── indicators.py       # Stat Calculation (Thresholds)
│   ├── strategies.py       # Backtrader Strategy Classes
│   └── analysis_result.py  # Result Analysis
├── main.py                # Execution Script
├── requirements.txt
└── README.md              # Project Documentation