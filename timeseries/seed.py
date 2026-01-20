"""Seed the InfluxDB database with time-series sensor data."""

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from datetime import datetime, timedelta
from timeseries.generators import generate_all_readings, SENSOR_CONFIG
from db import InfluxClient


def seed(days: int = 7):
    """
    Seed InfluxDB with sensor readings.

    Args:
        days: Number of days of data to generate (default: 7)

    """
    # Time range: start from midnight, N days ago
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = today - timedelta(days=days - 1)  # Start from midnight N-1 days ago
    end_time = today + timedelta(days=1) - timedelta(minutes=5)  # End at 23:55 today

    print(f"Generating {days} days of sensor data...")
    print(f"  Start: {start_time}")
    print(f"  End: {end_time}")
    print(f"  Interval: 5 minutes")
    print(f"  Sensors: {len(SENSOR_CONFIG)}")

    # Calculate expected number of readings
    total_minutes = days * 24 * 60
    readings_per_sensor = total_minutes // 5
    total_readings = readings_per_sensor * len(SENSOR_CONFIG)
    print(f"  Expected readings: ~{total_readings:,}")

    with InfluxClient() as client:
        # Batch writes for efficiency
        batch = []
        batch_size = 1000
        count = 0

        print("\nWriting to InfluxDB...")

        for reading in generate_all_readings(start_time, end_time):
            # Convert to line protocol format
            point = {
                "measurement": "sensor_readings",
                "tags": {
                    "sensor_id": reading["sensor_id"],
                    "sensor_type": reading["sensor_type"],
                },
                "fields": {
                    "reading": reading["reading"],
                },
                "time": reading["timestamp"],
            }
            batch.append(point)
            count += 1

            # Write in batches
            if len(batch) >= batch_size:
                client.client.write(record=batch)
                batch = []
                if count % 10000 == 0:
                    print(f"  Written {count:,} readings...")

        # Write remaining batch
        if batch:
            client.client.write(record=batch)

        print(f"\nSeeding complete! Total readings: {count:,}")


def verify():
    """Verify the seeded data by running some queries."""
    print("\n--- Verification ---")

    with InfluxClient() as client:
        # Count total readings
        result = client.query("SELECT COUNT(*) as count FROM sensor_readings")
        print(f"Total readings: {result.to_pandas()['count'].iloc[0]:,}")

        # Sample temperature readings
        print("\nSample temperature readings (last 5):")
        result = client.query("""
            SELECT time, sensor_id, reading
            FROM sensor_readings
            WHERE sensor_type = 'temperature'
            ORDER BY time DESC
            LIMIT 5
        """)
        print(result.to_pandas().to_string(index=False))

        # Sample occupancy readings
        print("\nSample occupancy readings (last 5):")
        result = client.query("""
            SELECT time, sensor_id, reading
            FROM sensor_readings
            WHERE sensor_type = 'occupancy'
            ORDER BY time DESC
            LIMIT 5
        """)
        print(result.to_pandas().to_string(index=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed InfluxDB with sensor data")
    parser.add_argument("--days", type=int, default=7, help="Number of days of data")
    args = parser.parse_args()

    seed(days=args.days, clear=args.clear)
    verify()
