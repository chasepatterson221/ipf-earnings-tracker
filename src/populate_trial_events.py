"""
Populate trial_events table from Project 1's trials + sponsors data.
key milestone dates (start, primary completion, termination)
for publicly-traded sponsors only, since those are the ones we can
match against stock price data.
"""

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "dbname": "ipf_trial_intelligence",
    "user": "ipf_user",
    "password": "ipf_pass",
    "port": 5432,
}


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Pull all trials for publicly-traded sponsors with at least one date
    cur.execute("""
        SELECT
            t.nct_id,
            s.ticker_symbol,
            s.sponsor_name,
            t.phase,
            t.overall_status,
            t.start_date,
            t.primary_completion_date,
            t.completion_date,
            t.why_stopped
        FROM trials t
        JOIN sponsors s ON t.sponsor_id = s.sponsor_id
        WHERE s.publicly_traded = TRUE
          AND s.ticker_symbol IS NOT NULL
    """)
    trials = cur.fetchall()
    print(f"Found {len(trials)} trials from publicly-traded sponsors.\n")

    inserted = 0
    for row in trials:
        (nct_id, ticker, sponsor_name, phase, status,
         start_date, primary_completion_date, completion_date, why_stopped) = row

        # One row per meaningful event type per trial
        events = []

        if start_date:
            events.append(("TRIAL_START", start_date))

        if primary_completion_date:
            events.append(("PRIMARY_COMPLETION", primary_completion_date))

        if completion_date and status == "TERMINATED":
            events.append(("TERMINATION", completion_date))
        elif completion_date and status == "COMPLETED":
            events.append(("COMPLETION", completion_date))

        for event_type, event_date in events:
            try:
                cur.execute("""
                    INSERT INTO trial_events (
                        nct_id, ticker_symbol, sponsor_name,
                        event_type, event_date, phase, overall_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (nct_id, ticker, sponsor_name,
                      event_type, event_date, phase, status))
                inserted += 1
            except Exception as e:
                print(f"  Error inserting event for {nct_id}: {e}")
                conn.rollback()
                continue

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Inserted {inserted} trial events.")


if __name__ == "__main__":
    main()