import os
import requests
import time
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Connect to Databases
URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
driver = GraphDatabase.driver(URI, auth=AUTH)

geolocator = Nominatim(user_agent="ai_travel_planner")

def scrape_wikipedia(city_name):
    """Scrapes the first paragraph of a Wikipedia article for RAG context."""
    print(f"Scraping Wikipedia for {city_name}...")
    url = f"https://en.wikipedia.org/wiki/{city_name}"
    response = requests.get(url)
    
    if response.status_code != 200:
        return f"{city_name} is a beautiful travel destination."
    
    soup = BeautifulSoup(response.text, 'html.parser')
    paragraphs = soup.find_all('p')
    
    # Get the first meaningful paragraph
    for p in paragraphs:
        text = p.get_text().strip()
        if len(text) > 100:
            return text
    return f"{city_name} is a wonderful place to visit."

def get_coordinates(city_name):
    """Gets real Lat/Lon for the Map UI."""
    try:
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
    except:
        pass
    return 0.0, 0.0

def add_to_databases(city, state, food_cost):
    print(f"\n--- Processing {city} ---")
    
    # 1. EXTRACT DATA
    lat, lon = get_coordinates(city)
    description = scrape_wikipedia(city)
    time.sleep(1) # Be polite to APIs
    
    # 3. LOAD INTO NEO4J (For Graph Routing)
    with driver.session() as session:
        # Create City
        session.run("""
            MERGE (l:Location {name: $city})
            SET l.state = $state, l.lat = $lat, l.lon = $lon, l.avg_food_cost_per_day = $food_cost
        """, city=city, state=state, lat=lat, lon=lon, food_cost=food_cost)
        
        # Create Dummy Hotels
        session.run("""
            MATCH (l:Location {name: $city})
            MERGE (h1:Accommodation {name: 'Budget Stay ' + $city, type: 'Budget', cost_per_night: 800})
            MERGE (h2:Accommodation {name: 'Luxury Resort ' + $city, type: 'Luxury', cost_per_night: 4500})
            MERGE (l)-[:HAS_HOTEL]->(h1)
            MERGE (l)-[:HAS_HOTEL]->(h2)
        """, city=city)
        
        # Create a generic Activity
        session.run("""
            MATCH (l:Location {name: $city})
            MERGE (a:Activity {name: 'City Sightseeing ' + $city, cost: 500, duration_hours: 4, tags: ['scenery', 'historical']})
            MERGE (l)-[:HAS_ACTIVITY]->(a)
        """, city=city)
        
        # Connect to existing Graph
        session.run("""
            MATCH (new_city:Location {name: $city})
            MATCH (hub:Location {name: 'Hyderabad'})
            MERGE (hub)-[:TRAVEL_ROUTE {mode: 'FLIGHT', cost: 3500, time_mins: 120}]->(new_city)
            MERGE (new_city)-[:TRAVEL_ROUTE {mode: 'FLIGHT', cost: 3500, time_mins: 120}]->(hub)
        """, city=city)
        
    print(f"Added to Neo4j Graph")

if __name__ == "__main__":
    new_cities = [
        # North
        {"city": "Delhi", "state": "Delhi", "food_cost": 1000},
        {"city": "Agra", "state": "Uttar Pradesh", "food_cost": 800},
        {"city": "Jaipur", "state": "Rajasthan", "food_cost": 900},
        {"city": "Shimla", "state": "Himachal Pradesh", "food_cost": 1200},
        # West
        {"city": "Goa", "state": "Goa", "food_cost": 1500},
        {"city": "Mumbai", "state": "Maharashtra", "food_cost": 1600},
        {"city": "Pune", "state": "Maharashtra", "food_cost": 1100},
        # South
        {"city": "Bangalore", "state": "Karnataka", "food_cost": 1200},
        {"city": "Mysore", "state": "Karnataka", "food_cost": 800},
        {"city": "Kochi", "state": "Kerala", "food_cost": 900},
        {"city": "Munnar", "state": "Kerala", "food_cost": 700}
    ]
    
    for c in new_cities:
        add_to_databases(c["city"], c["state"], c["food_cost"])
        
    # --- ADD MASS TRANSPORT EDGES TO CONNECT THE GRAPH ---
    print("\nConnecting the National Graph Network...")
    with driver.session() as session:
        routes = [
            # Golden Triangle
            ("Delhi", "Agra", "TRAIN", 500, 180),
            ("Agra", "Jaipur", "BUS", 600, 240),
            ("Jaipur", "Delhi", "ROAD", 800, 300),
            ("Delhi", "Shimla", "BUS", 1200, 600),
            
            # West Coast Connections
            ("Mumbai", "Pune", "ROAD", 400, 180),
            ("Mumbai", "Goa", "TRAIN", 1500, 600),
            ("Pune", "Goa", "BUS", 1200, 500),
            
            # South Connections
            ("Bangalore", "Mysore", "TRAIN", 300, 150),
            ("Mysore", "Kochi", "BUS", 1000, 480),
            ("Kochi", "Munnar", "ROAD", 400, 240),
            
            # Major Flight Hubs (Connecting North, West, South)
            ("Delhi", "Mumbai", "FLIGHT", 4500, 130),
            ("Mumbai", "Bangalore", "FLIGHT", 3500, 110),
            ("Delhi", "Bangalore", "FLIGHT", 5500, 160),
            ("Hyderabad", "Bangalore", "FLIGHT", 3000, 90),
            ("Hyderabad", "Delhi", "FLIGHT", 4500, 140),
            ("Hyderabad", "Mumbai", "FLIGHT", 3800, 100),
            ("Chennai", "Bangalore", "TRAIN", 800, 360)
        ]
        
        for r in routes:
            session.run("""
                MATCH (a:Location {name: $from_city})
                MATCH (b:Location {name: $to_city})
                MERGE (a)-[:TRAVEL_ROUTE {mode: $mode, cost: $cost, time_mins: $time}]->(b)
                MERGE (b)-[:TRAVEL_ROUTE {mode: $mode, cost: $cost, time_mins: $time}]->(a)
            """, from_city=r[0], to_city=r[1], mode=r[2], cost=r[3], time=r[4])
            
    print("Pipeline Execution Complete! Your system just got smarter.")