import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class Neo4jClient:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "neo4j")
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def verify(self):
        """Verify connection to Neo4j."""
        with self.driver.session() as session:
            result = session.run("RETURN 1 AS num")
            record = result.single()
            if record and record["num"] == 1:
                print("Neo4j connection successful")
                return True
        return False

    def run_query(self, query: str, parameters: dict = None):
        """Run a Cypher query and return results."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def create_constraints(self):
        """Create uniqueness constraints for node properties."""
        constraints = [
            "CREATE CONSTRAINT room_number IF NOT EXISTS FOR (r:Room) REQUIRE r.room_number IS UNIQUE",
            "CREATE CONSTRAINT ac_unit_id IF NOT EXISTS FOR (a:ACUnit) REQUIRE a.unit_id IS UNIQUE",
            "CREATE CONSTRAINT temp_sensor_id IF NOT EXISTS FOR (t:TemperatureSensor) REQUIRE t.sensor_id IS UNIQUE",
            "CREATE CONSTRAINT occ_sensor_id IF NOT EXISTS FOR (o:OccupancySensor) REQUIRE o.sensor_id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
        print("Neo4j constraints created")


if __name__ == "__main__":
    with Neo4jClient() as client:
        client.verify()
