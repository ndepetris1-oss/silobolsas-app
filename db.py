import os
import sqlite3
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL")

class DBWrapper:

    def __init__(self, conn, es_postgres=False):
        self.conn = conn
        self.cursor = conn.cursor()
        self.es_postgres = es_postgres

    def execute(self, query, params=None):

        # SQLite usa ?
        # PostgreSQL usa %s
        if self.es_postgres:
            query = query.replace("?", "%s")
        else:
            query = query.replace("%s", "?")

        if params:
            return self.cursor.execute(query, params)
        else:
            return self.cursor.execute(query)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        return self.conn.commit()

    def close(self):
        return self.conn.close()


def get_db():

    # PRODUCCIÓN (Render)
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return DBWrapper(conn, es_postgres=True)

    # LOCAL (SQLite)
    conn = sqlite3.connect("silobolsas.db")
    conn.row_factory = sqlite3.Row
    return DBWrapper(conn)