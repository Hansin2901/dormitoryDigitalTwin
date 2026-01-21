import os
from influxdb_client_3 import InfluxDBClient3
from dotenv import load_dotenv

load_dotenv()


class InfluxClient:
    def __init__(self):
        self.host = os.getenv("INFLUXDB_HOST", "localhost")
        self.port = os.getenv("INFLUXDB_PORT", "8181")
        self.token = os.getenv("INFLUXDB_TOKEN", "")
        self.database = os.getenv("INFLUXDB_DATABASE", "sensor_data")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = InfluxDBClient3(
                host=f"http://{self.host}:{self.port}",
                token=self.token,
                database=self.database,
            )
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def verify(self):
        """Verify connection to InfluxDB by running a simple query."""
        try:
            result = self.client.query("SELECT 1")
            print("InfluxDB connection successful")
            return True
        except Exception as e:
            print(f"InfluxDB connection failed: {e}")
            return False

    def write_reading(self, sensor_id: str, sensor_type: str, reading: float, timestamp=None):
        """Write a single sensor reading."""
        record = {
            "measurement": "sensor_readings",
            "tags": {
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
            },
            "fields": {
                "reading": float(reading),
            },
        }
        if timestamp:
            record["time"] = timestamp
        self.client.write(record=record)

    def write_readings(self, records: list):
        """Write multiple sensor readings at once."""
        self.client.write(record=records)

    def query(self, sql: str):
        """Run a SQL query and return results as a pandas DataFrame."""
        return self.client.query(sql)

    def get_data_time_range(self) -> dict:
        """
        Get the time range of data in the sensor_readings table.

        Returns:
            dict with 'min_time', 'max_time', and 'latest_time_str' keys,
            or None values if query fails.
        """
        try:
            result = self.query("""
                SELECT MIN(time) as min_time, MAX(time) as max_time
                FROM sensor_readings
            """)
            df = result.to_pandas()
            if not df.empty:
                min_time = df['min_time'].iloc[0]
                max_time = df['max_time'].iloc[0]
                return {
                    'min_time': min_time,
                    'max_time': max_time,
                    'latest_time_str': str(max_time) if max_time else None
                }
        except Exception as e:
            print(f"Failed to get data time range: {e}")
        return {'min_time': None, 'max_time': None, 'latest_time_str': None}


if __name__ == "__main__":
    with InfluxClient() as client:
        client.verify()
