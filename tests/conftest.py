import os

os.environ.setdefault("SECRET_KEY", "secreto-de-pruebas-para-jwt-minimo-32-caracteres")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_geoauxilio.db")
