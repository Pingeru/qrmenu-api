import os

from pymongo import MongoClient
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "qrmb")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
