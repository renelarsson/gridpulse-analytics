SELECT *
FROM {{ ref('mrt_daily_lmp_summary_by_location') }}
WHERE hours_included NOT BETWEEN 1 AND 24