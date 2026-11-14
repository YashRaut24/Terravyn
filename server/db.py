import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
database_name = os.getenv("MONGODB_DATABASE", "terravyn")

client = MongoClient(mongo_uri)
db = client[database_name]
