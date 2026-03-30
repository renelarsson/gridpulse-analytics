-- Source data selection
WITH source_data AS (
  SELECT *
  FROM {{ source('iso_ne_raw', 'day_ahead_hourly_lmp_raw') }} -- Raw source table
)

-- Transformations and column selection
SELECT
  -- Parse market_date into a DATE type
  PARSE_DATE('%m/%d/%Y', market_date) AS market_date,
  
  -- Cast hour_ending to an integer
  SAFE_CAST(hour_ending AS INT64) AS hour_ending,

  -- Derive market_timestamp_utc from market_date and hour_ending
  TIMESTAMP(
    PARSE_DATETIME(
      '%m/%d/%Y %H',
      CONCAT(
        market_date,
        ' ',
        LPAD(CAST(SAFE_CAST(hour_ending AS INT64) - 1 AS STRING), 2, '0')
      )
    ),
    'America/New_York' -- Convert to UTC
  ) AS market_timestamp_utc,

  -- Add a constant market_type column
  'day-ahead' AS market_type,

  -- Include location details
  location_id,
  location_name,
  location_type,

  -- Rename and cast price components to NUMERIC
  SAFE_CAST(locational_marginal_price AS NUMERIC) AS lmp_total,
  SAFE_CAST(energy_component AS NUMERIC) AS energy_component,
  SAFE_CAST(congestion_component AS NUMERIC) AS congestion_component,
  SAFE_CAST(marginal_loss_component AS NUMERIC) AS marginal_loss_component,

  -- Preserve lineage and metadata fields
  source_file,
  SAFE_CAST(source_row_number AS INT64) AS source_row_number,
  _dlt_load_id,
  _dlt_id
FROM source_data