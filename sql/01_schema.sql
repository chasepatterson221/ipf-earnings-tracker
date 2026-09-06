-- Project 2: IPF/PF Biopharma Earnings Surprise Tracker
-- Adds market/earnings tables to the existing ipf_trial_intelligence database.
-- Joins back to Project 1's sponsors + trials tables via ticker_symbol and nct_id.

-- Daily stock price data from yfinance
CREATE TABLE IF NOT EXISTS stock_prices (
    price_id SERIAL PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    price_date DATE NOT NULL,
    open_price NUMERIC(12,4),
    high_price NUMERIC(12,4),
    low_price NUMERIC(12,4),
    close_price NUMERIC(12,4),
    adj_close_price NUMERIC(12,4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (ticker_symbol, price_date)
);

-- Trial milestone events derived from Project 1's trials table
CREATE TABLE IF NOT EXISTS trial_events (
    event_id SERIAL PRIMARY KEY,
    nct_id TEXT REFERENCES trials(nct_id),
    ticker_symbol TEXT,
    sponsor_name TEXT,
    event_type TEXT,
    event_date DATE,
    phase TEXT,
    overall_status TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Earnings events: EPS actual vs. estimate per company per quarter
CREATE TABLE IF NOT EXISTS earnings_events (
    earnings_id SERIAL PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    sponsor_name TEXT,
    period_of_report DATE,
    eps_actual NUMERIC(10,4),
    eps_estimate NUMERIC(10,4),
    eps_surprise NUMERIC(10,4),
    eps_surprise_pct NUMERIC(10,4),
    filing_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for join performance
CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(price_date);
CREATE INDEX IF NOT EXISTS idx_trial_events_ticker ON trial_events(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_trial_events_date ON trial_events(event_date);
CREATE INDEX IF NOT EXISTS idx_earnings_ticker ON earnings_events(ticker_symbol);