import chromadb

# 1. Initialize local ChromaDB (It will create a folder named 'chroma_db' in your project)
client = chromadb.PersistentClient(path="./chroma_db")

# 2. Create a collection (our vector table)
collection = client.get_or_create_collection(name="travel_knowledge_base")

# 3. Our raw knowledge (In a real app, you'd scrape Wikipedia or travel blogs)
documents = [
    "Hyderabad is the capital of Telangana, known as the City of Pearls. It is famous for its rich history, the iconic Charminar, and delicious Biryani. A perfect blend of traditional and modern IT culture.",
    "Chennai, on the Bay of Bengal, is the capital of Tamil Nadu. It is famous for Marina Beach, beautiful Hindu temples, and a vibrant surfing culture at Covelong.",
    "Ooty is a stunning hill station in the Nilgiri Hills. Known for its rolling tea gardens, colonial architecture, and the historic Nilgiri Mountain Railway.",
    "Port Blair is the gateway to the Andaman and Nicobar Islands. It is a tropical paradise featuring the historic Cellular Jail, crystal clear waters, and world-class scuba diving at nearby islands."
]
metadatas = [{"location": "Hyderabad"}, {"location": "Chennai"}, {"location": "Ooty"}, {"location": "Port Blair"}]
ids = ["loc_1", "loc_2", "loc_3", "loc_4"]

# 4. Add to Vector DB (Chroma automatically embeds the text into vectors for free)
print("Embedding documents into Vector DB...")
collection.add(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)
print("RAG Knowledge Base Seeded Successfully!")