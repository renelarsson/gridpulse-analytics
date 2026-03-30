{{
  config(
    materialized='table',
    partition_by={
      'field': 'market_date',
      'data_type': 'date'
    },
    cluster_by=['location_name']
  )
}}

WITH hourly_lmp AS (
  SELECT *
  FROM {{ ref('mrt_hourly_lmp_by_location') }}
),

daily_summary AS (
  SELECT
    DATE(DATETIME(window_start, 'America/New_York')) AS market_date,
    location_name,
    SAFE_DIVIDE(SUM(avg_lmp_total * row_count), SUM(row_count)) AS avg_lmp_total_day,
    MAX(max_lmp_total) AS peak_hourly_lmp_total,
    COUNT(*) AS hours_included,
    SUM(row_count) AS source_rows_included
  FROM hourly_lmp
  GROUP BY 1, 2
),

peak_hour AS (
  SELECT
    DATE(DATETIME(window_start, 'America/New_York')) AS market_date,
    location_name,
    window_start AS peak_window_start,
    TIMESTAMP_ADD(window_start, INTERVAL 1 HOUR) AS peak_window_end,
    ROW_NUMBER() OVER (
      PARTITION BY DATE(DATETIME(window_start, 'America/New_York')), location_name
      ORDER BY max_lmp_total DESC, window_start ASC
    ) AS peak_hour_rank
  FROM hourly_lmp
)

SELECT
  daily_summary.market_date,
  daily_summary.location_name,
  daily_summary.avg_lmp_total_day,
  daily_summary.peak_hourly_lmp_total,
  peak_hour.peak_window_start,
  peak_hour.peak_window_end,
  daily_summary.hours_included,
  daily_summary.source_rows_included
FROM daily_summary
JOIN peak_hour
  ON daily_summary.market_date = peak_hour.market_date
 AND daily_summary.location_name = peak_hour.location_name
WHERE peak_hour.peak_hour_rank = 1