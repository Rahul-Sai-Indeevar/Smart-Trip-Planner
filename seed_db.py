import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))

class GraphSeeder:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)
    
    def close(self):
        self.driver.close()
    
    def clear_database(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Database cleared.")
            
    def seed_data(self):
        with self.driver.session() as session:
            # 1. Create Locations (with food costs)
            locations_query = """
            UNWIND $locations AS loc
            CREATE (l:Location {
                name: loc.name, 
                state: loc.state, 
                lat: loc.lat, 
                lon: loc.lon, 
                avg_food_cost_per_day: loc.food_cost
            })
            """
            locations = [
                {"name": "Hyderabad", "state": "Telangana", "lat": 17.385, "lon": 78.486, "food_cost": 800},
                {"name": "Chennai", "state": "Tamil Nadu", "lat": 13.082, "lon": 80.270, "food_cost": 700},
                {"name": "Ooty", "state": "Tamil Nadu", "lat": 11.410, "lon": 76.695, "food_cost": 600},
                {"name": "Port Blair", "state": "Andaman", "lat": 11.623, "lon": 92.726, "food_cost": 1000}
            ]
            session.run(locations_query, locations=locations)

            # 2. Create Transport Edges (Multi-modal)
            transport_query = """
            MATCH (a:Location {name: $from_loc})
            MATCH (b:Location {name: $to_loc})
            CALL apoc.create.relationship(a, $mode, {cost: $cost, time_mins: $time}, b) YIELD rel
            RETURN rel
            """
            
            standard_transport_query = """
            MATCH (a:Location {name: $from_loc})
            MATCH (b:Location {name: $to_loc})
            MERGE (a)-[r:TRAVEL_ROUTE {mode: $mode, cost: $cost, time_mins: $time}]->(b)
            """
            
            routes = [
                {"from_loc": "Hyderabad", "to_loc": "Chennai", "mode": "FLIGHT", "cost": 4500, "time": 90},
                {"from_loc": "Hyderabad", "to_loc": "Chennai", "mode": "TRAIN", "cost": 1200, "time": 840},
                {"from_loc": "Chennai", "to_loc": "Ooty", "mode": "BUS", "cost": 800, "time": 600},
                {"from_loc": "Chennai", "to_loc": "Port Blair", "mode": "FLIGHT", "cost": 7000, "time": 150},
                {"from_loc": "Chennai", "to_loc": "Port Blair", "mode": "FERRY", "cost": 4000, "time": 3600}, # 60 hours
            ]
            for route in routes:
                session.run(standard_transport_query, **route)
                # Create reverse routes too (assuming round trips cost/time roughly the same)
                session.run(standard_transport_query, from_loc=route["to_loc"], to_loc=route["from_loc"], mode=route["mode"], cost=route["cost"], time=route["time"])

            # 3. Create Accommodations
            hotel_query = """
            MATCH (l:Location {name: $loc_name})
            CREATE (h:Accommodation {
                name: $hotel_name, 
                type: $type, 
                cost_per_night: $cost
            })
            MERGE (l)-[:HAS_HOTEL]->(h)
            """
            hotels = [
                {"loc_name": "Ooty", "hotel_name": "Backpacker Hostel Ooty", "type": "Budget", "cost": 500},
                {"loc_name": "Ooty", "hotel_name": "Tea Estate Resort", "type": "Luxury", "cost": 5000},
                {"loc_name": "Port Blair", "hotel_name": "SeaShell Resort", "type": "Luxury", "cost": 8000},
                {"loc_name": "Port Blair", "hotel_name": "Islander Guest House", "type": "Budget", "cost": 1200},
            ]
            for hotel in hotels:
                session.run(hotel_query, **hotel)

            # 4. Create Activities (with Tags for Personalization)
            activity_query = """
            MATCH (l:Location {name: $loc_name})
            CREATE (a:Activity {
                name: $activity_name, 
                tags: $tags, 
                cost: $cost,
                duration_hours: $duration
            })
            MERGE (l)-[:HAS_ACTIVITY]->(a)
            """
            activities = [
                {"loc_name": "Port Blair", "activity_name": "Havelock Scuba Diving", "tags": ["adventure", "water"], "cost": 3500, "duration": 3},
                {"loc_name": "Port Blair", "activity_name": "Cellular Jail Tour", "tags": ["historical", "culture"], "cost": 50, "duration": 2},
                {"loc_name": "Port Blair", "activity_name": "Radhanagar Beach Sunset", "tags": ["scenery", "relaxation"], "cost": 0, "duration": 2},
                {"loc_name": "Ooty", "activity_name": "Botanical Gardens", "tags": ["scenery", "nature"], "cost": 40, "duration": 2},
                {"loc_name": "Ooty", "activity_name": "Nilgiri Mountain Railway", "tags": ["scenery", "historical"], "cost": 300, "duration": 4},
                {"loc_name": "Chennai", "activity_name": "Surfing at Covelong", "tags": ["adventure", "water"], "cost": 1500, "duration": 2},
                {"loc_name": "Chennai", "activity_name": "Marina Beach Walk", "tags": ["relaxation"], "cost": 0, "duration": 2}
            ]
            for act in activities:
                session.run(activity_query, **act)
            
            print("Graph database seeded successfully!")
            
if __name__ == "__main__":
    seeder = GraphSeeder(URI, AUTH)
    seeder.clear_database()
    seeder.seed_data()
    seeder.close()