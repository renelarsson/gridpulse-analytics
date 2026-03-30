SELECT
  location_name,
  window_start,
  COUNT(*) AS record_count
FROM {{ ref('mrt_hourly_lmp_by_location') }}
GROUP BY 1, 2
HAVING COUNT(*) > 1