# AI-Powered Multi-Modal Travel Planner

A full-stack, AI-driven travel routing application that plans multi-city vacations. It calculates optimal multi-modal travel routes (Flights, Trains, Ferries), allocates budget dynamically, and uses Retrieval-Augmented Generation (RAG) to generate personalized day-by-day itineraries.

## Tech Stack
* **Frontend:** HTML5, CSS3, Vanilla JavaScript, Leaflet.js (Map UI), Font Awesome.
* **Backend:** Python, FastAPI, Uvicorn.
* **Graph Database:** Neo4j (Nodes representing Cities, Hotels, Activities; Edges representing transport modes).
* **Vector Database:** ChromaDB (for local RAG document embeddings).
* **AI / LLMs:** Google Gemini API (`gemini-1.5-flash`), Local Embedding models.
* **Data Pipeline:** Python `requests`, `BeautifulSoup` (Web Scraping), `geopy` (Geocoding).

---

## Core Algorithms & Architecture (Interview Cheat Sheet)

This project heavily relies on Data Structures and Algorithms (DSA) combined with modern AI patterns.

### 1. The Graph Routing Algorithm (Shortest Path)
* **Problem:** Finding the cheapest way to travel between two cities using mixed transport (e.g., Flight + Ferry).
* **Implementation:** The backend queries Neo4j to perform a traversal (similar to **Dijkstra's Algorithm**) evaluating paths up to 3 edges deep. 
* **Edge Weights:** The cost is dynamically evaluated by summing `edge.cost` across `TRAVEL_ROUTE` relationships.

### 2. Multi-City Optimization (Traveling Salesperson Problem - TSP)
* **Problem:** Given a source and multiple destinations, what is the best order to visit them to minimize total cost?
* **Implementation:** Since the number of destinations `N` is usually small (N < 8), I implemented a **Brute Force Permutation** approach (`itertools.permutations`). It calculates the valid shortest path for every combination (N! time complexity) and selects the mathematically cheapest sequence. 

### 3. Dynamic Budget Allocation (Greedy / Knapsack Variant)
* **Problem:** After paying for transport and hotels, fit as many activities into the remaining budget as possible based on user preferences (e.g., 'Adventure', 'History').
* **Implementation:** I used a **Greedy Algorithm**. Activities are filtered by tags, sorted by cost (cheapest first), and incrementally added to the itinerary until the `city_budget_left` drops below 0. 

### 4. Retrieval-Augmented Generation (RAG)
* **Problem:** Providing accurate, hallucinatory-free context about cities when a user clicks a map marker.
* **Implementation:** 
  1. Scraped Wikipedia data is chunked and stored in **ChromaDB**.
  2. Clicking a marker triggers a vector similarity search (Retrieval).
  3. The resulting factual context is passed to **Google Gemini** alongside a prompt (Augmentation & Generation) to create a custom pitch.

---

## How to Run Locally

### 1. Prerequisites
* Python 3.9+
* Neo4j Database (Local Desktop or AuraDB Cloud)

### 2. Environment Setup
Create a `.env` file in the root directory:
```env
NEO4J_URI=bolt://localhost:7687  # or your AuraDB URI
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
GEMINI_API_KEY=your_google_gemini_key
```
### 3. Installation
```bash
python -m venv venv
# Activate venv
pip install fastapi uvicorn pydantic neo4j python-dotenv chromadb google-genai beautifulsoup4 requests geopy
```
### 4. Database Initialization (Data Pipeline)
To populate Neo4j and ChromaDB with initial city data, coordinates, and transport routes:
```bash
python data_pipeline.py
```
### 5. Start the Server
```bash
python main.py
```
* The backend will run on http://127.0.0.1:8000.
* Open index.html in any modern web browser to use the application.

---

# Future Enhancements
* Real-Time Pricing: Replace static Neo4j edge weights with live API calls to Amadeus/Skyscanner for real flight prices.
* A Search Algorithm:* Upgrade the Neo4j routing traversal to use A* search with geographical heuristics (Lat/Lon distance) for faster large-scale routing.
* User Authentication: Allow users to save their AI-generated itineraries to a Postgres database.

*"I built this because standard maps only show A to B. I wanted to apply Graph Theory and the TSP algorithm to solve multi-city vacation routing, and then use LLMs to automate the manual work of planning daily schedules."*