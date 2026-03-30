SELECT *
FROM {{ ref('stg_iso_ne_day_ahead_hourly_lmp') }}
WHERE hour_ending NOT BETWEEN 1 AND 24