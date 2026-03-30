SELECT *
FROM {{ ref('mrt_hourly_lmp_by_location') }}
WHERE row_count <= 0