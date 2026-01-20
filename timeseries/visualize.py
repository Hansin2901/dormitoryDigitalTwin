"""Visualize time-series sensor data from InfluxDB."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib.pyplot as plt
import pandas as pd

from db import InfluxClient


def get_temperature_data(client: InfluxClient) -> pd.DataFrame:
    """Query temperature sensor data from InfluxDB."""
    query = """
        SELECT time, sensor_id, reading
        FROM sensor_readings
        WHERE sensor_type = 'temperature'
        ORDER BY time
    """
    result = client.query(query)
    return result.to_pandas() if hasattr(result, "to_pandas") else pd.DataFrame(result)


def get_occupancy_data(client: InfluxClient) -> pd.DataFrame:
    """Query occupancy sensor data from InfluxDB."""
    query = """
        SELECT time, sensor_id, reading
        FROM sensor_readings
        WHERE sensor_type = 'occupancy'
        ORDER BY time
    """
    result = client.query(query)
    return result.to_pandas() if hasattr(result, "to_pandas") else pd.DataFrame(result)


def plot_temperature_comparison(client: InfluxClient):
    """Plot temperature readings comparing sun-facing vs shade rooms."""
    df = get_temperature_data(client)

    fig, ax = plt.subplots(figsize=(14, 6))

    # Sun-facing rooms: 101, 102, 103
    sun_facing = ["TEMP-101", "TEMP-102", "TEMP-103"]
    shade = ["TEMP-104", "TEMP-105", "TEMP-106"]

    for sensor_id in sun_facing:
        sensor_data = df[df["sensor_id"] == sensor_id]
        ax.plot(
            sensor_data["time"],
            sensor_data["reading"],
            label=f"{sensor_id} (Sun-facing)",
            alpha=0.7,
        )

    for sensor_id in shade:
        sensor_data = df[df["sensor_id"] == sensor_id]
        ax.plot(
            sensor_data["time"],
            sensor_data["reading"],
            label=f"{sensor_id} (Shade)",
            linestyle="--",
            alpha=0.7,
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Temperature Readings: Sun-facing vs Shade Rooms")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def plot_occupancy_patterns(client: InfluxClient):
    """Plot occupancy patterns for all rooms."""
    df = get_occupancy_data(client)

    sensors = sorted(df["sensor_id"].unique())
    fig, axes = plt.subplots(len(sensors), 1, figsize=(14, 2 * len(sensors)), sharex=True)

    if len(sensors) == 1:
        axes = [axes]

    # Profile mapping based on SENSOR_CONFIG
    profiles = {
        "OCC-101": "full_time",
        "OCC-102": "full_time",
        "OCC-103": "night_worker",
        "OCC-104": "full_time",
        "OCC-105": "night_worker",
        "OCC-106": "full_time",
    }

    for ax, sensor_id in zip(axes, sensors):
        sensor_data = df[df["sensor_id"] == sensor_id]
        profile = profiles.get(sensor_id, "unknown")
        color = "green" if profile == "full_time" else "purple"

        ax.fill_between(
            sensor_data["time"],
            sensor_data["reading"],
            alpha=0.7,
            color=color,
            step="post",
        )
        ax.set_ylabel("Occupied")
        ax.set_title(f"{sensor_id} ({profile})")
        ax.set_ylim(-0.1, 1.1)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Empty", "Occupied"])
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("Time")
    plt.tight_layout()
    return fig


def plot_sensor_heatmap(client: InfluxClient):
    """Plot heatmaps of sensor readings."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))

    # Temperature heatmap
    temp_df = get_temperature_data(client)
    temp_pivot = temp_df.pivot_table(
        index="sensor_id", columns="time", values="reading", aggfunc="mean"
    )

    im1 = axes[0].imshow(
        temp_pivot.values,
        aspect="auto",
        cmap="RdYlBu_r",
    )
    axes[0].set_yticks(range(len(temp_pivot.index)))
    axes[0].set_yticklabels(temp_pivot.index)
    axes[0].set_xlabel("Time")
    axes[0].set_title("Temperature Sensors Heatmap")
    plt.colorbar(im1, ax=axes[0], label="Temperature (°C)")

    # Occupancy heatmap
    occ_df = get_occupancy_data(client)
    occ_pivot = occ_df.pivot_table(
        index="sensor_id", columns="time", values="reading", aggfunc="mean"
    )

    im2 = axes[1].imshow(
        occ_pivot.values,
        aspect="auto",
        cmap="Greens",
    )
    axes[1].set_yticks(range(len(occ_pivot.index)))
    axes[1].set_yticklabels(occ_pivot.index)
    axes[1].set_xlabel("Time")
    axes[1].set_title("Occupancy Sensors Heatmap")
    plt.colorbar(im2, ax=axes[1], label="Occupancy")

    plt.tight_layout()
    return fig


def plot_daily_summary(client: InfluxClient):
    """Plot daily summary statistics."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Temperature averages
    temp_df = get_temperature_data(client)
    temp_avg = temp_df.groupby("sensor_id")["reading"].mean().sort_index()

    sun_facing = ["TEMP-101", "TEMP-102", "TEMP-103"]
    colors = ["orange" if s in sun_facing else "blue" for s in temp_avg.index]
    axes[0].bar(temp_avg.index, temp_avg.values, color=colors)
    axes[0].set_xlabel("Sensor")
    axes[0].set_ylabel("Average Temperature (°C)")
    axes[0].set_title("Average Temperature by Sensor")
    axes[0].tick_params(axis="x", rotation=45)

    # Occupancy rates
    occ_df = get_occupancy_data(client)
    occ_rate = occ_df.groupby("sensor_id")["reading"].mean() * 100
    occ_rate = occ_rate.sort_index()

    night_workers = ["OCC-103", "OCC-105"]
    colors = ["purple" if s in night_workers else "green" for s in occ_rate.index]
    axes[1].bar(occ_rate.index, occ_rate.values, color=colors)
    axes[1].set_xlabel("Sensor")
    axes[1].set_ylabel("Occupancy Rate (%)")
    axes[1].set_title("Average Occupancy Rate by Sensor")
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    return fig


def plot_temperature_single_day(client: InfluxClient):
    """Plot temperature readings for a single day (first day in the dataset)."""
    df = get_temperature_data(client)

    # Get the first day's data
    df["date"] = pd.to_datetime(df["time"]).dt.date
    first_day = df["date"].min()
    day_data = df[df["date"] == first_day].copy()
    day_data["hour"] = pd.to_datetime(day_data["time"]).dt.hour + pd.to_datetime(day_data["time"]).dt.minute / 60

    fig, ax = plt.subplots(figsize=(12, 6))

    sun_facing = ["TEMP-101", "TEMP-102", "TEMP-103"]
    shade = ["TEMP-104", "TEMP-105", "TEMP-106"]

    # Plot sun-facing rooms in warm colors
    warm_colors = ["#FF6B6B", "#FF8E53", "#FFA726"]
    for sensor_id, color in zip(sun_facing, warm_colors):
        sensor_data = day_data[day_data["sensor_id"] == sensor_id].sort_values("hour")
        ax.plot(
            sensor_data["hour"],
            sensor_data["reading"],
            label=f"{sensor_id} (Sun-facing)",
            color=color,
            linewidth=2,
        )

    # Plot shade rooms in cool colors
    cool_colors = ["#42A5F5", "#5C6BC0", "#7E57C2"]
    for sensor_id, color in zip(shade, cool_colors):
        sensor_data = day_data[day_data["sensor_id"] == sensor_id].sort_values("hour")
        ax.plot(
            sensor_data["hour"],
            sensor_data["reading"],
            label=f"{sensor_id} (Shade)",
            color=color,
            linewidth=2,
            linestyle="--",
        )

    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title(f"Temperature Readings - {first_day}")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # Add vertical lines for key times
    ax.axvline(6, color="gray", linestyle=":", alpha=0.5, label="6am")
    ax.axvline(12, color="gray", linestyle=":", alpha=0.5, label="12pm")
    ax.axvline(18, color="gray", linestyle=":", alpha=0.5, label="6pm")

    plt.tight_layout()
    return fig


def main():
    """Generate and display all visualizations."""
    with InfluxClient() as client:
        print("Connecting to InfluxDB...")
        if not client.verify():
            print("Failed to connect to InfluxDB. Make sure the database is running.")
            return

        print("\nGenerating single day temperature plot...")
        fig0 = plot_temperature_single_day(client)
        fig0.savefig("temperature_single_day.png", dpi=150)
        print("  Saved: temperature_single_day.png")

        print("Generating temperature comparison plot...")
        fig1 = plot_temperature_comparison(client)
        fig1.savefig("temperature_comparison.png", dpi=150)
        print("  Saved: temperature_comparison.png")

        print("Generating occupancy patterns plot...")
        fig2 = plot_occupancy_patterns(client)
        fig2.savefig("occupancy_patterns.png", dpi=150)
        print("  Saved: occupancy_patterns.png")

        print("Generating sensor heatmap...")
        fig3 = plot_sensor_heatmap(client)
        fig3.savefig("sensor_heatmap.png", dpi=150)
        print("  Saved: sensor_heatmap.png")

        print("Generating daily summary...")
        fig4 = plot_daily_summary(client)
        fig4.savefig("daily_summary.png", dpi=150)
        print("  Saved: daily_summary.png")

        print("\nAll visualizations generated!")
        plt.show()


if __name__ == "__main__":
    main()
