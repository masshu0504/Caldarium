from fastapi import APIRouter
import psycopg2
import settings  # your settings.py with DATABASE_URL


# Create a router (similar to Flask blueprint)
routes = APIRouter()

@routes.get("/health")
async def health():
    return {"status": "OK"}

@routes.get("/ready")
async def ready():
    try:
        #dbURL = "postgresql://postgres:postgres@localhost:5432/postgres"
        conn = psycopg2.connect(settings.DATABASE_URL)
        #conn = psycopg2.connect(dbURL)
        cur = conn.cursor()
        cur.execute("SELECT 1;")  # simple query
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result == (1,):
            return {"status": "DB connection OK"}
        else:
            return {"status": "DB connection failed"}
    except Exception as e:
        return {"status": "DB connection failed", "error": str(e)}
