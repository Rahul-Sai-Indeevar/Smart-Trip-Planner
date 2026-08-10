import os
import traceback
import itertools
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import GraphDatabase
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import chromadb
from google import genai

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
driver = GraphDatabase.driver(URI, auth=AUTH)

# --- MODELS ---
class TripRequest(BaseModel):
    source: str
    destinations: list[str]
    days: int
    budget: int
    preference: str

# --- GRAPH DSA FUNCTIONS ---
def get_shortest_path(tx, source, dest):
    """Finds the absolute cheapest path between two specific cities"""
    query = """
    MATCH path = (start:Location {name: $source})-[r:TRAVEL_ROUTE*1..3]->(end:Location {name: $dest})
    RETURN path, 
           reduce(cost = 0, rel in relationships(path) | cost + rel.cost) AS total_cost,
           reduce(time = 0, rel in relationships(path) | time + rel.time_mins) AS total_time
    ORDER BY total_cost ASC LIMIT 1
    """
    record = tx.run(query, source=source, dest=dest).single()
    if not record: return None
    
    nodes = record["path"].nodes
    rels = record["path"].relationships
    
    legs = []
    for i in range(len(rels)):
        legs.append({
            "from": nodes[i]["name"],
            "from_lat": nodes[i]["lat"],
            "from_lon": nodes[i]["lon"],
            "to": nodes[i+1]["name"],
            "to_lat": nodes[i+1]["lat"],
            "to_lon": nodes[i+1]["lon"],
            "mode": rels[i]["mode"],
            "cost": rels[i]["cost"],
            "time_mins": rels[i]["time_mins"]
        })
    return {"legs": legs, "cost": record["total_cost"], "time": record["total_time"]}

def get_destination_details(tx, destination, preference):
    query = """
    MATCH (l:Location {name: $destination})
    OPTIONAL MATCH (l)-[:HAS_HOTEL]->(h:Accommodation)
    WITH l, collect(h) AS hotel_nodes
    
    OPTIONAL MATCH (l)-[:HAS_ACTIVITY]->(a:Activity)
    WHERE $preference IN a.tags OR $preference = 'any'
    WITH l, hotel_nodes, collect(a) AS activity_nodes
    
    RETURN l.avg_food_cost_per_day AS food_cost,
           [x IN hotel_nodes WHERE x IS NOT NULL | {name: x.name, type: x.type, cost: x.cost_per_night}] AS hotels,
           [x IN activity_nodes WHERE x IS NOT NULL | {name: x.name, cost: x.cost, tags: x.tags}] AS activities
    """
    record = tx.run(query, destination=destination, preference=preference).single()
    return record.data() if record else None

# --- MAIN ENDPOINT ---
@app.post("/plan-trip")
def plan_trip(req: TripRequest):
    try:
        with driver.session() as session:
            # 1. TSP ALGORITHM: Generate all possible orders of destinations
            possible_orders = list(itertools.permutations(req.destinations))
            best_tsp_route = None
            lowest_travel_cost = float('inf')

            # Evaluate each permutation to find the cheapest logical route
            for order in possible_orders:
                current_cost = 0
                current_legs = []
                valid_path = True
                
                # Build the sequence: Source -> Dest1 -> Dest2 -> ...
                sequence = [req.source] + list(order)
                
                for i in range(len(sequence) - 1):
                    path_segment = session.execute_read(get_shortest_path, sequence[i], sequence[i+1])
                    if not path_segment:
                        valid_path = False
                        break # No path exists between these two nodes
                    current_cost += path_segment["cost"]
                    current_legs.extend(path_segment["legs"])
                
                if valid_path and current_cost < lowest_travel_cost:
                    lowest_travel_cost = current_cost
                    best_tsp_route = current_legs

            if not best_tsp_route:
                raise HTTPException(status_code=404, detail="Could not connect these destinations.")

            # 2. BUDGET ALLOCATION FOR MULTIPLE CITIES
            remaining_budget = req.budget - lowest_travel_cost
            if remaining_budget < 0:
                raise HTTPException(status_code=400, detail="Budget is too low just for travel!")

            days_per_city = max(1, req.days // len(req.destinations))
            budget_per_city = remaining_budget // len(req.destinations)
            
            trip_itinerary = []
            total_trip_cost = lowest_travel_cost

            # 3. KNAPSACK ALLOCATION PER CITY
            for dest in req.destinations:
                details = session.execute_read(get_destination_details, dest, req.preference)
                if not details: continue
                
                food_cost = details["food_cost"] * days_per_city
                
                # Pick the cheapest hotel that fits
                details["hotels"].sort(key=lambda x: x["cost"])
                chosen_hotel = details["hotels"][0] if details["hotels"] else {"name": "No Hotel", "cost": 0}
                hotel_cost = chosen_hotel["cost"] * days_per_city

                city_base_cost = food_cost + hotel_cost
                city_budget_left = budget_per_city - city_base_cost
                
                chosen_activities = []
                if city_budget_left > 0:
                    details["activities"].sort(key=lambda x: x["cost"])
                    for act in details["activities"]:
                        if act["cost"] <= city_budget_left:
                            chosen_activities.append(act)
                            city_budget_left -= act["cost"]

                city_total = city_base_cost + sum(a["cost"] for a in chosen_activities)
                total_trip_cost += city_total

                trip_itinerary.append({
                    "city": dest,
                    "days": days_per_city,
                    "accommodation": chosen_hotel,
                    "activities": chosen_activities,
                    "city_cost": city_total
                })

            return {
                "message": "TSP Optimized Route Generated!",
                "total_cost": total_trip_cost,
                "travel_route": {"legs": best_tsp_route},
                "itinerary": trip_itinerary
            }

    except Exception as e:
        print("\n--- ERROR CAUGHT ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- RAG ENDPOINT (POWERED BY NEW GEMINI SDK) ---
chroma_client = chromadb.PersistentClient(path="./chroma_db")
rag_collection = chroma_client.get_collection(name="travel_knowledge_base")

@app.get("/location-info/{location_name}")
def get_location_info(location_name: str):
    results = rag_collection.query(query_texts=[f"Tell me about {location_name}"], n_results=1)
    context = results['documents'][0][0] if results['documents'][0] else "No specific data found."
    
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"Based on this: '{context}', write a 2-sentence exciting travel pitch for {location_name}."
            
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            ai_description = response.text
        except Exception as e:
            ai_description = f"Error connecting to Gemini: {str(e)}"
    else:
        ai_description = f"✨ (AI Summary) ✨\n{context}\n\nYou will absolutely love exploring {location_name}!"

    return {
        "name": location_name,
        "description": ai_description,
        "image_url": f"https://picsum.photos/seed/{location_name}/400/250"
    }

# --- AI DAY-BY-DAY ITINERARY ENDPOINT (POWERED BY NEW GEMINI SDK) ---
@app.post("/generate-itinerary")
def generate_itinerary(plan: dict):
    api_key = os.getenv("GEMINI_API_KEY")
    
    prompt = f"Act as an expert travel agent. I have a planned trip with a budget of Rs {plan.get('total_cost')}.\n"
    prompt += "Here is the transit route:\n"
    for leg in plan.get("travel_route", {}).get("legs", []):
        prompt += f"- {leg['from']} to {leg['to']} via {leg['mode']} (Takes {leg['time_mins']} mins)\n"
    
    prompt += "\nHere is the city breakdown:\n"
    for city in plan.get("itinerary", []):
        act_names = [a['name'] for a in city['activities']]
        acts = ", ".join(act_names) if act_names else "Relaxation and local sightseeing"
        prompt += f"- {city['city']} for {city['days']} days. Hotel: {city['accommodation']['name']}. Planned Activities: {acts}.\n"

    prompt += "\nWrite a detailed, engaging Day-by-Day itinerary. Include realistic times (e.g., 'Morning', 'Afternoon'), check-ins, and travel times. Format the output using clean HTML (e.g., <h3>Day 1</h3>, <ul><li>...</li></ul>). Do not use markdown backticks like ```html, just return the raw HTML code."

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            html_text = response.text.replace("```html", "").replace("```", "").strip()
            return {"html_itinerary": html_text}
        except Exception as e:
            return {"html_itinerary": f"<p style='color:red;'>Error connecting to Gemini AI: {str(e)}</p>"}
    else:
        return {"html_itinerary": "<p>Please add GEMINI_API_KEY to your .env file.</p>"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)