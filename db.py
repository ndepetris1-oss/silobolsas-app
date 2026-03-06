import sqlite3
import os
import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "silobolsas.db")


def get_db():

    database_url = os.environ.get("DATABASE_URL")

    # Si estamos en Render → usar PostgreSQL
    if database_url:
        conn = psycopg2.connect(
            database_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return conn

    # Si estamos local → usar SQLite
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn