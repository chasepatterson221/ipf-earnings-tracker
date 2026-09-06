"""
Ingest historical stock price data from yfinance for all publicly-traded
IPF/PF sponsors identified in Project 1's sponsors table.
Populates: stock_prices table.
"""

import yfinance as yf
import psycopg2
import pandas as pd
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "dbname": "ipf_trial_intelligence",
    "user": "ipf_user",
    "password": "ipf_pass",
    "port": 5432,
}

# How far back to pull price history
START_DATE = "2010-01-01"
END_DATE = datetime.today().strftime("%Y-%m-%d")


def get_public_sponsors(cur):
    """Pull all publicly-traded sponsors and their tickers from Project 1."""
    cur.execute("""
        SELECT DISTINCT sponsor_name, ticker_symbol
        FROM sponsors
        WHERE publicly_traded = TRUE
          AND ticker_symbol IS NOT NULL
        ORDER BY sponsor_name
    """)
    return cur.fetchall()


def fetch_prices(ticker):
    """Download historical OHLCV data for one ticker via yfinance."""
    try:
        data = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)
        if data.empty:
            return None
        data = data.reset_index()
        data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]
        return data
    except Exception as e:
        print(f"  Error fetching {ticker}: {e}")
        return None


def insert_prices(cur, ticker, df):
    """Insert price rows, skipping duplicates via ON CONFLICT."""
    inserted = 0
    for _, row in df.iterrows():
        try:
            cur.execute("""
                INSERT INTO stock_prices (
                    ticker_symbol, price_date, open_price, high_price,
                    low_price, close_price, adj_close_price, volume
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker_symbol, price_date) DO NOTHING
            """, (
                ticker,
                row["Date"].date() if hasattr(row["Date"], "date") else row["Date"],
                float(row["Open"]) if pd.notna(row["Open"]) else None,
                float(row["High"]) if pd.notna(row["High"]) else None,
                float(row["Low"]) if pd.notna(row["Low"]) else None,
                float(row["Close"]) if pd.notna(row["Close"]) else None,
                float(row["Close"]) if pd.notna(row["Close"]) else None,
                int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            ))
            inserted += 1
        except Exception as e:
            print(f"  Row error for {ticker} on {row['Date']}: {e}")
            continue
    return inserted


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    sponsors = get_public_sponsors(cur)
    print(f"Found {len(sponsors)} publicly-traded sponsors to pull prices for.\n")

    total_rows = 0
    for sponsor_name, ticker in sponsors:
        print(f"  Fetching {ticker} ({sponsor_name})...")
        df = fetch_prices(ticker)

        if df is None or df.empty:
            print(f"  No data returned for {ticker} — skipping")
            continue

        inserted = insert_prices(cur, ticker, df)
        conn.commit()
        total_rows += inserted
        print(f"  {ticker}: {inserted} price rows inserted")

    cur.close()
    conn.close()
    print(f"\nDone. Total price rows inserted: {total_rows}")


if __name__ == "__main__":
    main()