"""Seed the Neo4j database with the dormitory building model."""

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from db import Neo4jClient


def clear_database(client: Neo4jClient):
    """Remove all nodes and relationships."""
    client.run_query("MATCH (n) DETACH DELETE n")
    print("Cleared existing data")


def create_constraints(client: Neo4jClient):
    """Create uniqueness constraints."""
    client.create_constraints()


def create_rooms(client: Neo4jClient):
    """Create all room nodes."""
    rooms = [
        # Dorm rooms - sun-facing (serviced by AC-1)
        {"room_number": "101", "room_type": "dorm"},
        {"room_number": "102", "room_type": "dorm"},
        {"room_number": "103", "room_type": "dorm"},
        # Dorm rooms - shade-facing (serviced by AC-2)
        {"room_number": "104", "room_type": "dorm"},
        {"room_number": "105", "room_type": "dorm"},
        {"room_number": "106", "room_type": "dorm"},
        # Mechanical rooms
        {"room_number": "M1", "room_type": "mechanical"},
        {"room_number": "M2", "room_type": "mechanical"},
    ]

    for room in rooms:
        client.run_query(
            "CREATE (r:Room {room_number: $room_number, room_type: $room_type})",
            room
        )
    print(f"Created {len(rooms)} rooms")


def create_ac_units(client: Neo4jClient):
    """Create AC unit nodes and link to mechanical rooms."""
    ac_units = [
        {"unit_id": "AC-1", "label": "Air Conditioning Unit 1", "mechanical_room": "M1"},
        {"unit_id": "AC-2", "label": "Air Conditioning Unit 2", "mechanical_room": "M2"},
    ]

    for ac in ac_units:
        # Create AC unit and link to its mechanical room
        client.run_query(
            """
            MATCH (room:Room {room_number: $mechanical_room})
            CREATE (ac:ACUnit {unit_id: $unit_id, label: $label})
            CREATE (ac)-[:LOCATED_IN]->(room)
            """,
            ac
        )
    print(f"Created {len(ac_units)} AC units")


def create_ac_services_relationships(client: Neo4jClient):
    """Create SERVICES relationships between AC units and dorm rooms."""
    # AC-1 services rooms 101, 102, 103 (sun-facing)
    # AC-2 services rooms 104, 105, 106 (shade-facing)
    services = [
        {"ac_id": "AC-1", "room_numbers": ["101", "102", "103"]},
        {"ac_id": "AC-2", "room_numbers": ["104", "105", "106"]},
    ]

    for service in services:
        for room_number in service["room_numbers"]:
            client.run_query(
                """
                MATCH (ac:ACUnit {unit_id: $ac_id})
                MATCH (room:Room {room_number: $room_number})
                CREATE (ac)-[:SERVICES]->(room)
                """,
                {"ac_id": service["ac_id"], "room_number": room_number}
            )
    print("Created AC SERVICES relationships")


def create_sensors(client: Neo4jClient):
    """Create sensor nodes and link to rooms."""
    # Temperature sensors
    temp_sensors = [
        {"sensor_id": "TEMP-101", "label": "Temperature Sensor Room 101", "room": "101"},
        {"sensor_id": "TEMP-102", "label": "Temperature Sensor Room 102", "room": "102"},
        {"sensor_id": "TEMP-103", "label": "Temperature Sensor Room 103", "room": "103"},
        {"sensor_id": "TEMP-104", "label": "Temperature Sensor Room 104", "room": "104"},
        {"sensor_id": "TEMP-105", "label": "Temperature Sensor Room 105", "room": "105"},
        {"sensor_id": "TEMP-106", "label": "Temperature Sensor Room 106", "room": "106"},
    ]

    for sensor in temp_sensors:
        client.run_query(
            """
            MATCH (room:Room {room_number: $room})
            CREATE (s:TemperatureSensor {sensor_id: $sensor_id, label: $label})
            CREATE (s)-[:INSTALLED_IN]->(room)
            """,
            sensor
        )
    print(f"Created {len(temp_sensors)} temperature sensors")

    # Occupancy sensors
    occ_sensors = [
        {"sensor_id": "OCC-101", "label": "Occupancy Sensor Room 101", "room": "101"},
        {"sensor_id": "OCC-102", "label": "Occupancy Sensor Room 102", "room": "102"},
        {"sensor_id": "OCC-103", "label": "Occupancy Sensor Room 103", "room": "103"},
        {"sensor_id": "OCC-104", "label": "Occupancy Sensor Room 104", "room": "104"},
        {"sensor_id": "OCC-105", "label": "Occupancy Sensor Room 105", "room": "105"},
        {"sensor_id": "OCC-106", "label": "Occupancy Sensor Room 106", "room": "106"},
    ]

    for sensor in occ_sensors:
        client.run_query(
            """
            MATCH (room:Room {room_number: $room})
            CREATE (s:OccupancySensor {sensor_id: $sensor_id, label: $label})
            CREATE (s)-[:INSTALLED_IN]->(room)
            """,
            sensor
        )
    print(f"Created {len(occ_sensors)} occupancy sensors")


def verify_graph(client: Neo4jClient):
    """Print summary of created graph."""
    print("\n--- Graph Summary ---")

    # Count nodes
    counts = client.run_query("""
        MATCH (r:Room) WITH count(r) as rooms
        MATCH (ac:ACUnit) WITH rooms, count(ac) as acs
        MATCH (ts:TemperatureSensor) WITH rooms, acs, count(ts) as temp_sensors
        MATCH (os:OccupancySensor) WITH rooms, acs, temp_sensors, count(os) as occ_sensors
        RETURN rooms, acs, temp_sensors, occ_sensors
    """)
    if counts:
        c = counts[0]
        print(f"Rooms: {c['rooms']}")
        print(f"AC Units: {c['acs']}")
        print(f"Temperature Sensors: {c['temp_sensors']}")
        print(f"Occupancy Sensors: {c['occ_sensors']}")

    # Show AC to room relationships
    print("\nAC Unit -> Rooms serviced:")
    ac_rooms = client.run_query("""
        MATCH (ac:ACUnit)-[:SERVICES]->(room:Room)
        RETURN ac.unit_id as ac, collect(room.room_number) as rooms
        ORDER BY ac.unit_id
    """)
    for row in ac_rooms:
        print(f"  {row['ac']}: {', '.join(row['rooms'])}")


def seed():
    """Main function to seed the database."""
    with Neo4jClient() as client:
        print("Seeding Neo4j database...\n")

        clear_database(client)
        create_constraints(client)
        create_rooms(client)
        create_ac_units(client)
        create_ac_services_relationships(client)
        create_sensors(client)
        verify_graph(client)

        print("\nSeeding complete!")


if __name__ == "__main__":
    seed()
