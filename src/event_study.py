"""
Event study: measures stock price reaction around IPF/PF trial milestones.
For each trial event (start, completion, termination), computes:
  - Cumulative Abnormal Return (CAR) over [-2, +2] trading day window
  - Expected return estimated from 60-day pre-event window
  - Statistical significance (t-statistic)

Results written to CSV and Postgres for SQL analysis and Tableau visualization.
"""

import psycopg2
import pandas as pd
import numpy as np
from scipy import stats
import os

DB_CONFIG = {
    "host": "localhost",
    "dbname": "ipf_trial_intelligence",
    "user": "ipf_user",
    "password": "ipf_pass",
    "port": 5432,
}

ESTIMATION_WINDOW = 60
EVENT_WINDOW = 2


def load_prices(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker_symbol, price_date, close_price
        FROM stock_prices
        WHERE close_price IS NOT NULL
        ORDER BY ticker_symbol, price_date
    """)
    rows = cur.fetchall()
    cur.close()
    df = pd.DataFrame(rows, columns=["ticker_symbol", "price_date", "close_price"])
    df["price_date"] = pd.to_datetime(df["price_date"])
    df["close_price"] = df["close_price"].astype(float)
    return df


def load_events(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT event_id, nct_id, ticker_symbol, sponsor_name,
               event_type, event_date, phase, overall_status
        FROM trial_events
        WHERE event_date IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows, columns=[
        "event_id", "nct_id", "ticker_symbol", "sponsor_name",
        "event_type", "event_date", "phase", "overall_status"
    ])


def compute_daily_returns(prices_df):
    prices_df = prices_df.sort_values(["ticker_symbol", "price_date"])
    prices_df["log_return"] = prices_df.groupby("ticker_symbol")["close_price"].transform(
        lambda x: np.log(x / x.shift(1))
    )
    return prices_df


def get_ticker_returns(prices_df, ticker):
    df = prices_df[prices_df["ticker_symbol"] == ticker].copy()
    df = df.set_index("price_date")["log_return"].dropna()
    return df


def compute_car(returns, event_date, estimation_window, event_window):
    event_date = pd.Timestamp(event_date)
    dates = returns.index

    future_dates = dates[dates >= event_date]
    if len(future_dates) == 0:
        return None
    actual_event_date = future_dates[0]
    event_pos = dates.get_loc(actual_event_date)

    est_start = event_pos - estimation_window - event_window
    est_end = event_pos - event_window

    if est_start < 0 or est_end < estimation_window // 2:
        return None

    estimation_returns = returns.iloc[est_start:est_end]
    expected_return = estimation_returns.mean()
    estimation_std = estimation_returns.std()

    if estimation_std == 0 or pd.isna(estimation_std):
        return None

    ew_start = event_pos - event_window
    ew_end = event_pos + event_window + 1

    if ew_end > len(returns):
        return None

    event_returns = returns.iloc[ew_start:ew_end]
    abnormal_returns = event_returns - expected_return
    car = abnormal_returns.sum()

    t_stat = car / (estimation_std * np.sqrt(len(event_returns)))
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=len(estimation_returns) - 1))

    return {
        "car": round(car, 6),
        "expected_daily_return": round(expected_return, 6),
        "estimation_std": round(estimation_std, 6),
        "t_stat": round(t_stat, 4),
        "p_value": round(p_value, 4),
        "significant_5pct": p_value < 0.05,
        "actual_event_date": actual_event_date.date(),
        "event_window_days": len(event_returns),
    }


def create_results_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_study_results (
            event_id INTEGER,
            nct_id TEXT,
            ticker_symbol TEXT,
            sponsor_name TEXT,
            event_type TEXT,
            event_date DATE,
            phase TEXT,
            overall_status TEXT,
            car NUMERIC(10,6),
            expected_daily_return NUMERIC(10,6),
            estimation_std NUMERIC(10,6),
            t_stat NUMERIC(10,4),
            p_value NUMERIC(10,4),
            significant_5pct BOOLEAN,
            actual_event_date DATE,
            event_window_days INTEGER
        )
    """)
    cur.execute("TRUNCATE event_study_results")


def write_results_to_postgres(conn, results_df):
    cur = conn.cursor()
    create_results_table(cur)
    for _, row in results_df.iterrows():
        cur.execute("""
            INSERT INTO event_study_results (
                event_id, nct_id, ticker_symbol, sponsor_name,
                event_type, event_date, phase, overall_status,
                car, expected_daily_return, estimation_std,
                t_stat, p_value, significant_5pct,
                actual_event_date, event_window_days
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            int(row["event_id"]),
            row["nct_id"],
            row["ticker_symbol"],
            row["sponsor_name"],
            row["event_type"],
            row["event_date"],
            row["phase"],
            row["overall_status"],
            float(row["car"]),
            float(row["expected_daily_return"]),
            float(row["estimation_std"]),
            float(row["t_stat"]),
            float(row["p_value"]),
            bool(row["significant_5pct"]),
            row["actual_event_date"],
            int(row["event_window_days"]),
        ))
    conn.commit()
    cur.close()
    print(f"Wrote {len(results_df)} rows to event_study_results table.")


def main():
    conn = psycopg2.connect(**DB_CONFIG)

    print("Loading price data...")
    prices_df = load_prices(conn)
    prices_df = compute_daily_returns(prices_df)
    print(f"Loaded {len(prices_df)} price rows across {prices_df['ticker_symbol'].nunique()} tickers.")

    print("Loading trial events...")
    events_df = load_events(conn)
    print(f"Processing {len(events_df)} events...\n")

    results = []
    for _, event in events_df.iterrows():
        ticker = event["ticker_symbol"]
        returns = get_ticker_returns(prices_df, ticker)

        if returns.empty:
            continue

        car_result = compute_car(
            returns,
            event["event_date"],
            ESTIMATION_WINDOW,
            EVENT_WINDOW
        )

        if car_result is None:
            continue

        results.append({
            "event_id": event["event_id"],
            "nct_id": event["nct_id"],
            "ticker_symbol": ticker,
            "sponsor_name": event["sponsor_name"],
            "event_type": event["event_type"],
            "event_date": event["event_date"],
            "phase": event["phase"],
            "overall_status": event["overall_status"],
            **car_result,
        })

    results_df = pd.DataFrame(results)

    os.makedirs("exports", exist_ok=True)
    output_path = "exports/event_study_results.csv"
    results_df.to_csv(output_path, index=False)
    print(f"Done. {len(results_df)} events processed.")
    print(f"Results saved to {output_path}\n")

    print("--- Summary by event type ---")
    summary = results_df.groupby("event_type").agg(
        event_count=("car", "count"),
        mean_car=("car", "mean"),
        pct_significant=("significant_5pct", "mean")
    ).round(4)
    print(summary)

    print("\n--- Top 10 most significant events ---")
    top_events = results_df.nsmallest(10, "p_value")[
        ["ticker_symbol", "sponsor_name", "event_type", "event_date",
         "phase", "car", "t_stat", "p_value"]
    ]
    print(top_events.to_string(index=False))

    print("\nWriting results to Postgres...")
    write_results_to_postgres(conn, results_df)

    conn.close()


if __name__ == "__main__":
    main()