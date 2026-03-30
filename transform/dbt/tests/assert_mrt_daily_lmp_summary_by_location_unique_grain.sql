SELECT
  market_date,
  location_name,
  COUNT(*) AS record_count
FROM {{ ref('mrt_daily_lmp_summary_by_location') }}
GROUP BY 1, 2
HAVING COUNT(*) > 1