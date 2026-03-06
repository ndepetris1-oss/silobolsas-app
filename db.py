import sqlite3
import os
import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "silobolsas.db")


class CursorAdapter:

    def __init__(self, cursor, es_postgres):
        self.cursor = cursor
        self.es_postgres = es_postgres

    def execute(self, query, params=None):

        if self.es_postgres:
            query = query.replace("?", "%s")

        if params is None:
            return self.cursor.execute(query)

        return self.cursor.execute(query, params)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class ConnectionAdapter:

    def __init__(self, conn, es_postgres):
        self.conn = conn
        self.es_postgres = es_postgres

    def cursor(self):
        return CursorAdapter(self.conn.cursor(), self.es_postgres)

    def execute(self, query, params=None):
        cur = self.cursor()

        if params is None:
            cur.execute(query)
        else:
            cur.execute(query, params)

        return cur

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def get_db():

    database_url = os.environ.get("DATABASE_URL")

    # PostgreSQL (Render)
    if database_url:

        conn = psycopg2.connect(
            database_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        return ConnectionAdapter(conn, True)

    # SQLite (local)
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    return ConnectionAdapter(conn, False)
