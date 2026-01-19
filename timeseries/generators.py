"""Generate time-series sensor data for the dormitory."""

import math
import random
from datetime import datetime, timedelta
from typing import Generator


def generate_temperature_readings(
    sensor_id: str,
    start_time: datetime,
    end_time: datetime,
    interval_minutes: int = 5,
    is_sun_facing: bool = False,
) -> Generator[dict, None, None]:
    """
    Generate temperature readings for a sensor.

    Uses a sine wave for diurnal pattern:
    - Peak temperature around 3pm (15:00)
    - Lowest temperature around 3am (03:00)
    - Base temperature: 22°C (shade) or 24°C (sun-facing)
    - Amplitude: ±3°C
    - Random noise: ±0.5°C
    """
    base_temp = 24.0 if is_sun_facing else 22.0
    amplitude = 3.0

    current = start_time
    while current <= end_time:
        # Hour of day as fraction (0-24)
        hour = current.hour + current.minute / 60

        # Sine wave: peak at 15:00 (3pm), trough at 3:00 (3am)
        # Shift by -9 hours to align peak with 15:00
        phase = (hour - 9) * (2 * math.pi / 24)
        temp = base_temp + amplitude * math.sin(phase)

        # Add random noise
        noise = random.uniform(-0.5, 0.5)
        temp += noise

        yield {
            "sensor_id": sensor_id,
            "sensor_type": "temperature",
            "reading": round(temp, 2),
            "timestamp": current,
        }

        current += timedelta(minutes=interval_minutes)


def generate_occupancy_readings(
    sensor_id: str,
    start_time: datetime,
    end_time: datetime,
    interval_minutes: int = 5,
    profile: str = "full_time",
) -> Generator[dict, None, None]:
    """
    Generate occupancy readings for a sensor.

    Profiles:
    - full_time: in room 7-9am, 1-3pm, 8-10pm, night (10pm-7am)
    - night_worker: in room 6-8am, 4-6pm, 9-11pm, night (11pm-6am)

    Returns 0 (unoccupied) or 1 (occupied).
    """
    if profile == "full_time":
        # Full-time student schedule
        occupied_hours = [
            (7, 9),    # Morning routine
            (13, 15),  # Afternoon break
            (20, 22),  # Evening
            (22, 24),  # Night (first part)
            (0, 7),    # Night (second part)
        ]
    else:  # night_worker
        # Working night student schedule
        occupied_hours = [
            (6, 8),    # Morning after night shift
            (16, 18),  # Afternoon break
            (21, 23),  # Evening
            (23, 24),  # Night (first part)
            (0, 6),    # Night (second part, sleeping during day)
        ]

    def is_occupied(dt: datetime) -> int:
        hour = dt.hour + dt.minute / 60
        for start, end in occupied_hours:
            if start <= hour < end:
                # Add some randomness at boundaries (10% chance of opposite)
                if random.random() < 0.1:
                    return 0
                return 1
        # Not in occupied hours - small chance of being there anyway (5%)
        if random.random() < 0.05:
            return 1
        return 0

    current = start_time
    while current <= end_time:
        yield {
            "sensor_id": sensor_id,
            "sensor_type": "occupancy",
            "reading": float(is_occupied(current)),
            "timestamp": current,
        }

        current += timedelta(minutes=interval_minutes)


# Sensor configurations
SENSOR_CONFIG = {
    # Temperature sensors - rooms 101-103 are sun-facing
    "TEMP-101": {"type": "temperature", "is_sun_facing": True},
    "TEMP-102": {"type": "temperature", "is_sun_facing": True},
    "TEMP-103": {"type": "temperature", "is_sun_facing": True},
    "TEMP-104": {"type": "temperature", "is_sun_facing": False},
    "TEMP-105": {"type": "temperature", "is_sun_facing": False},
    "TEMP-106": {"type": "temperature", "is_sun_facing": False},
    # Occupancy sensors - mix of profiles
    "OCC-101": {"type": "occupancy", "profile": "full_time"},
    "OCC-102": {"type": "occupancy", "profile": "full_time"},
    "OCC-103": {"type": "occupancy", "profile": "night_worker"},
    "OCC-104": {"type": "occupancy", "profile": "full_time"},
    "OCC-105": {"type": "occupancy", "profile": "night_worker"},
    "OCC-106": {"type": "occupancy", "profile": "full_time"},
}


def generate_all_readings(
    start_time: datetime,
    end_time: datetime,
    interval_minutes: int = 5,
) -> Generator[dict, None, None]:
    """Generate readings for all sensors."""
    for sensor_id, config in SENSOR_CONFIG.items():
        if config["type"] == "temperature":
            yield from generate_temperature_readings(
                sensor_id=sensor_id,
                start_time=start_time,
                end_time=end_time,
                interval_minutes=interval_minutes,
                is_sun_facing=config["is_sun_facing"],
            )
        else:  # occupancy
            yield from generate_occupancy_readings(
                sensor_id=sensor_id,
                start_time=start_time,
                end_time=end_time,
                interval_minutes=interval_minutes,
                profile=config["profile"],
            )
