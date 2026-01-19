# Database Schema Documentation

## Neo4j Graph Database

### Node Types

| Label | Properties | Description |
|-------|------------|-------------|
| `Room` | `room_number` (string), `room_type` ("dorm" \| "mechanical") | Physical rooms in the building |
| `ACUnit` | `unit_id` (string), `label` (string) | Air conditioning units |
| `TemperatureSensor` | `sensor_id` (string), `label` (string) | Temperature sensors in dorm rooms |
| `OccupancySensor` | `sensor_id` (string), `label` (string) | Occupancy sensors in dorm rooms |

### Relationships

| Type | From | To | Description |
|------|------|-----|-------------|
| `SERVICES` | ACUnit | Room | AC unit provides cooling to this dorm room |
| `LOCATED_IN` | ACUnit | Room | AC unit is physically located in this mechanical room |
| `INSTALLED_IN` | TemperatureSensor | Room | Sensor is installed in this dorm room |
| `INSTALLED_IN` | OccupancySensor | Room | Sensor is installed in this dorm room |

### Building Layout

```
Mechanical Room M1          Mechanical Room M2
    [AC-1]                      [AC-2]
      |                           |
      +-- Room 101 (sun-facing)   +-- Room 104 (shade-facing)
      +-- Room 102 (sun-facing)   +-- Room 105 (shade-facing)
      +-- Room 103 (sun-facing)   +-- Room 106 (shade-facing)
```

### Example Cypher Queries

```cypher
-- Get all rooms serviced by a specific AC unit
MATCH (ac:ACUnit {unit_id: "AC-1"})-[:SERVICES]->(room:Room)
RETURN room.room_number, room.room_type

-- Get all sensors in a room
MATCH (sensor)-[:INSTALLED_IN]->(room:Room {room_number: "101"})
RETURN sensor.sensor_id, labels(sensor)[0] AS sensor_type

-- Find which AC unit services a room
MATCH (room:Room {room_number: "101"})<-[:SERVICES]-(ac:ACUnit)
RETURN ac.unit_id, ac.label

-- Get all temperature sensors in rooms serviced by an AC unit
MATCH (ac:ACUnit {unit_id: "AC-1"})-[:SERVICES]->(room:Room)<-[:INSTALLED_IN]-(sensor:TemperatureSensor)
RETURN sensor.sensor_id, room.room_number
```

---

## InfluxDB 3 Time Series Database

### Database
- **Name**: `sensor_data`

### Measurement: `sensor_readings`

| Column | Type | Description |
|--------|------|-------------|
| `time` | timestamp | Reading timestamp (automatic) |
| `sensor_id` | tag (string) | Sensor identifier (e.g., "TEMP-101", "OCC-101") |
| `sensor_type` | tag (string) | "temperature" or "occupancy" |
| `reading` | field (float) | Sensor value: °C for temperature, 0/1 for occupancy |

### Tags vs Fields
- **Tags** (indexed, for filtering): `sensor_id`, `sensor_type`
- **Fields** (not indexed, actual data): `reading`

### Example Queries (SQL)

```sql
-- Get latest readings for all sensors
SELECT * FROM sensor_readings
ORDER BY time DESC
LIMIT 10

-- Get temperature readings for a specific room
SELECT time, reading
FROM sensor_readings
WHERE sensor_id = 'TEMP-101'
  AND time > now() - interval '1 day'

-- Get average temperature per sensor over the last hour
SELECT sensor_id, avg(reading) as avg_temp
FROM sensor_readings
WHERE sensor_type = 'temperature'
  AND time > now() - interval '1 hour'
GROUP BY sensor_id

-- Get occupancy readings for a room
SELECT time, reading
FROM sensor_readings
WHERE sensor_id = 'OCC-101'
  AND time > now() - interval '1 day'
```
