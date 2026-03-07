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

        if self.es_postgres:
            query = query.replace("?", "%s")
        else:
            query = query.replace("%s", "?")

        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)

        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        return self.conn.commit()

    def close(self):
        return self.conn.close()


def get_db():

    if DATABASE_URL:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        conn.autocommit = False
        return DBWrapper(conn, es_postgres=True)

    conn = sqlite3.connect("silobolsas.db")
    conn.row_factory = sqlite3.Row
    return DBWrapper(conn)