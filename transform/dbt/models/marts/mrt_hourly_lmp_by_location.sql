{{
  config(
    materialized='table',
    partition_by={
      'field': 'window_start',
      'data_type': 'timestamp',
      'granularity': 'day'
    },
    cluster_by=['location_name']
  )
}}

WITH staged_lmp AS (
  SELECT *
  FROM {{ ref('stg_iso_ne_day_ahead_hourly_lmp') }}
),

hourly_lmp AS (
  SELECT
    location_name,
    TIMESTAMP_TRUNC(market_timestamp_utc, HOUR) AS window_start,
    lmp_total
  FROM staged_lmp
)

SELECT
  location_name,
  window_start,
  TIMESTAMP_ADD(window_start, INTERVAL 1 HOUR) AS window_end,
  AVG(lmp_total) AS avg_lmp_total,
  MAX(lmp_total) AS max_lmp_total,
  COUNT(*) AS row_count
FROM hourly_lmp
GROUP BY 1, 2, 3