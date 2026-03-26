SELECT
  *
FROM {{ source('iso_ne_raw', 'day_ahead_hourly_lmp_raw') }}