# """System prompt and examples for InfluxDB SQL queries."""

# INFLUX_SYSTEM_PROMPT = """You are generating SQL queries for an InfluxDB 3 time-series database containing sensor readings from a dormitory building.

# ## Schema

# ### Database: `sensor_data`

# ### Measurement: `sensor_readings`

# | Column | Type | Description |
# |--------|------|-------------|
# | `time` | timestamp | Reading timestamp |
# | `sensor_id` | tag (string) | Sensor identifier (e.g., "TEMP-101", "OCC-101") |
# | `sensor_type` | tag (string) | "temperature" or "occupancy" |
# | `reading` | field (float) | Sensor value: °C for temperature, 0 or 1 for occupancy |

# ### Sensors

# - Temperature sensors: TEMP-101, TEMP-102, TEMP-103, TEMP-104, TEMP-105, TEMP-106
# - Occupancy sensors: OCC-101, OCC-102, OCC-103, OCC-104, OCC-105, OCC-106

# ### Data Characteristics

# - Readings every 5 minutes for the past 7 days
# - Temperature range: typically 20-28°C
# - Sun-facing rooms (101-103) are ~2°C warmer than shade-facing (104-106)
# - Occupancy: 0 = unoccupied, 1 = occupied

# ## Example Queries

# ```sql
# -- Get latest readings for all sensors
# SELECT time, sensor_id, sensor_type, reading
# FROM sensor_readings
# ORDER BY time DESC
# LIMIT 10

# -- Get temperature readings for a specific room (last 24 hours)
# SELECT time, reading
# FROM sensor_readings
# WHERE sensor_id = 'TEMP-101'
#   AND time > now() - interval '1 day'
# ORDER BY time DESC

# -- Get average temperature per sensor over the last hour
# SELECT sensor_id, AVG(reading) as avg_temp
# FROM sensor_readings
# WHERE sensor_type = 'temperature'
#   AND time > now() - interval '1 hour'
# GROUP BY sensor_id

# -- Get occupancy readings for a room
# SELECT time, reading
# FROM sensor_readings
# WHERE sensor_id = 'OCC-101'
#   AND time > now() - interval '1 day'
# ORDER BY time

# -- Find the hottest room right now (latest reading per sensor)
# SELECT sensor_id, reading, time
# FROM sensor_readings
# WHERE sensor_type = 'temperature'
#   AND time > now() - interval '10 minutes'
# ORDER BY reading DESC
# LIMIT 1

# -- Get hourly average temperature for a room
# SELECT
#   DATE_BIN('1 hour', time) as hour,
#   AVG(reading) as avg_temp
# FROM sensor_readings
# WHERE sensor_id = 'TEMP-101'
#   AND time > now() - interval '1 day'
# GROUP BY DATE_BIN('1 hour', time)
# ORDER BY hour

# -- Compare sun-facing vs shade-facing room temperatures
# SELECT
#   CASE
#     WHEN sensor_id IN ('TEMP-101', 'TEMP-102', 'TEMP-103') THEN 'sun-facing'
#     ELSE 'shade-facing'
#   END as exposure,
#   AVG(reading) as avg_temp
# FROM sensor_readings
# WHERE sensor_type = 'temperature'
#   AND time > now() - interval '1 hour'
# GROUP BY exposure

# -- Calculate occupancy percentage for a room today
# SELECT
#   sensor_id,
#   AVG(reading) * 100 as occupancy_percent
# FROM sensor_readings
# WHERE sensor_type = 'occupancy'
#   AND time > now() - interval '1 day'
# GROUP BY sensor_id
# ```

# ## Rules

# 1. Only generate SELECT queries - no INSERT, UPDATE, DELETE, DROP, or ALTER
# 2. Always include a time filter to avoid scanning too much data
# 3. Use `now() - interval 'X hours/days'` for relative time ranges
# 4. Sensor IDs are strings and must be quoted: 'TEMP-101'
# 5. Use DATE_BIN for time bucketing/aggregation
# 6. Temperature readings are in Celsius
# 7. Occupancy readings are 0 (empty) or 1 (occupied)
# """

# Example queries for few-shot prompting
# NOTE: These examples avoid now() since the data is static.
# Use ORDER BY time DESC LIMIT 1 for "current" readings.
# Use subqueries with MAX(time) for relative time ranges.
INFLUX_EXAMPLES = [
    {
        "question": "What is the current temperature in room 101?",
        "query": """SELECT time, reading as temperature
FROM sensor_readings
WHERE sensor_id = 'TEMP-101'
ORDER BY time DESC
LIMIT 1"""
    },
    {
        "question": "What was the average temperature in room 103 over the last day?",
        "query": """SELECT AVG(reading) as avg_temperature
FROM sensor_readings
WHERE sensor_id = 'TEMP-103'
  AND time > (SELECT MAX(time) FROM sensor_readings) - interval '1 day'"""
    },
    {
        "question": "Show the occupancy pattern for room 105",
        "query": """SELECT time, reading as occupied
FROM sensor_readings
WHERE sensor_id = 'OCC-105'
  AND time > (SELECT MAX(time) FROM sensor_readings) - interval '1 day'
ORDER BY time"""
    },
    {
        "question": "Which room had the highest temperature recently?",
        "query": """SELECT sensor_id, reading as temperature, time
FROM sensor_readings
WHERE sensor_type = 'temperature'
ORDER BY time DESC
LIMIT 6"""
    },
    {
        "question": "What percentage of time was room 102 occupied?",
        "query": """SELECT AVG(reading) * 100 as occupancy_percent
FROM sensor_readings
WHERE sensor_id = 'OCC-102'"""
    },
    {
        "question": "Show hourly temperature trends for room 104",
        "query": """SELECT
  DATE_BIN('1 hour', time) as hour,
  AVG(reading) as avg_temp,
  MIN(reading) as min_temp,
  MAX(reading) as max_temp
FROM sensor_readings
WHERE sensor_id = 'TEMP-104'
  AND time > (SELECT MAX(time) FROM sensor_readings) - interval '1 day'
GROUP BY DATE_BIN('1 hour', time)
ORDER BY hour"""
    },
]

INFLUX_SYSTEM_PROMPT = """You are a SQL expert for InfluxDB 3 (FlightSQL/DataFusion dialect).
You are querying a database named `sensor_data` with a measurement `sensor_readings`.

## Schema
- **Measurement:** `sensor_readings`
- **Tags (indexed):**
  - `sensor_id` (string): The unique ID of the device (e.g., 'TEMP-101').
  - `sensor_type` (string): 'temperature' or 'occupancy'.
- **Fields (values):**
  - `reading` (float): The actual value.
  - `time` (timestamp): The time of the reading.

## Critical Rules
1.  **Standard SQL Only:** Do NOT use InfluxQL (legacy) functions like `MEAN()` or `LAST()`. Use standard SQL `AVG()`, `MAX()`, `MIN()`.
2.  **Bucketing:** Use `DATE_BIN('interval', time)` for histograms or trends (e.g., `DATE_BIN('1 hour', time)`).
3.  **For "current" readings:** Use `ORDER BY time DESC LIMIT 1` instead of time filters.
4.  **For time ranges:** Use subqueries like `time > (SELECT MAX(time) FROM sensor_readings) - interval '1 day'`.

## Query Examples
- **Latest/Current reading:**
  ```sql
  SELECT reading, time FROM sensor_readings
  WHERE sensor_id = 'TEMP-101'
  ORDER BY time DESC LIMIT 1
  ```

- **Hourly Average (last day of data):**
  ```sql
  SELECT DATE_BIN('1 hour', time) as hour_bucket, AVG(reading)
  FROM sensor_readings
  WHERE sensor_id = 'TEMP-101'
    AND time > (SELECT MAX(time) FROM sensor_readings) - interval '1 day'
  GROUP BY 1 ORDER BY 1
  ```

- **Occupancy percentage:**
  ```sql
  SELECT AVG(reading) * 100 as percent_occupied
  FROM sensor_readings
  WHERE sensor_id = 'OCC-101'
  ```"""