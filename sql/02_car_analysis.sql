-- Project 2: CAR Analysis Queries
-- Analyzes cumulative abnormal returns (CAR) around IPF/PF trial milestones
-- for publicly-traded sponsors, sourced from the event study output.
--
-- Note: event_study_results are loaded from CSV into a temporary table
-- for analysis. In production this would be a permanent table; for this
-- portfolio project we run analyses directly against the exported CSV
-- via a staging approach.

-- === Query 1: Mean CAR by event type and phase ===
-- Question: Does the market react differently to trial milestones
-- depending on which phase the trial is in?
SELECT
    event_type,
    phase,
    COUNT(*) AS event_count,
    ROUND(AVG(car)::numeric, 4) AS mean_car,
    ROUND(STDDEV(car)::numeric, 4) AS std_car,
    ROUND(MIN(car)::numeric, 4) AS min_car,
    ROUND(MAX(car)::numeric, 4) AS max_car,
    SUM(CASE WHEN significant_5pct = 'true' THEN 1 ELSE 0 END) AS significant_events,
    ROUND(100.0 * SUM(CASE WHEN significant_5pct = 'true' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_significant
FROM event_study_results
WHERE phase IN ('PHASE1', 'PHASE2', 'PHASE3', 'PHASE4')
GROUP BY event_type, phase
HAVING COUNT(*) >= 3
ORDER BY event_type, phase;

-- === Query 2: CAR by sponsor — large cap vs small cap ===
-- Question: Do small-cap biotech sponsors show larger stock reactions
-- to trial events than large-cap pharma? (The PLRX vs BMY contrast)
SELECT
    ticker_symbol,
    sponsor_name,
    COUNT(*) AS event_count,
    ROUND(AVG(car)::numeric, 4) AS mean_car,
    ROUND(AVG(ABS(car))::numeric, 4) AS mean_abs_car,
    ROUND(MAX(ABS(car))::numeric, 4) AS max_abs_car,
    SUM(CASE WHEN significant_5pct = 'true' THEN 1 ELSE 0 END) AS significant_events
FROM event_study_results
GROUP BY ticker_symbol, sponsor_name
HAVING COUNT(*) >= 3
ORDER BY mean_abs_car DESC;

-- === Query 3: Most significant individual events ===
-- Question: Which specific trial milestones caused the largest
-- statistically significant stock price reactions?
SELECT
    ticker_symbol,
    sponsor_name,
    event_type,
    event_date,
    phase,
    overall_status,
    ROUND(car::numeric, 4) AS car,
    ROUND(t_stat::numeric, 4) AS t_stat,
    ROUND(p_value::numeric, 4) AS p_value,
    CASE WHEN car > 0 THEN 'POSITIVE' ELSE 'NEGATIVE' END AS direction
FROM event_study_results
WHERE significant_5pct = 'true'
ORDER BY ABS(car) DESC
LIMIT 20;