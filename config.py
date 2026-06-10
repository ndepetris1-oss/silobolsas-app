import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "silobolsas.db")

SECRET_KEY = "super_clave_cambiar_en_produccion"
