from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from langdetect import detect
import hashlib
import asyncpg
import os

# Initialize FastAPI app
app = FastAPI()

# PostgreSQL database connection settings
DB_HOST = "your_db_host"
DB_PORT = "5432"
DB_USER = "your_db_user"
DB_PASSWORD = "your_db_password"
DB_NAME = "your_db_name"


# Request Model
class NameRequest(BaseModel):
    type: str = Field(..., regex="^(Entity|Individual)$", description="Type should be either 'Individual' or 'Entity'")
    name: str
    threshold: float = Field(..., description="Float between 0-1 or Integer between 1-100")


# Async function to get DB connection
async def get_db_connection():
    return await asyncpg.connect(
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, host=DB_HOST, port=DB_PORT
    )


@app.post("/process/")
async def process_name(data: NameRequest):
    # Language Detection
    try:
        language = detect(data.name)
        if language not in ["ar", "en"]:
            raise ValueError("Unsupported language detected")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to detect language")

    language_detected = "Arabic" if language == "ar" else "English"

    # Hashing Name
    name_hash = hashlib.sha256(data.name.encode()).hexdigest()

    # Database Query to Find Matching Hashes
    try:
        conn = await get_db_connection()
        query = "SELECT name FROM names WHERE hash_value = $1"
        rows = await conn.fetch(query, name_hash)
        await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Formatting response
    matching_names = [row['name'] for row in rows]

    return {
        "type": data.type,
        "name": data.name,
        "language": language_detected,
        "hash": name_hash,
        "matching_names": matching_names
    }
