"""Configuración leída desde variables de entorno (.env)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "GeoAuxilio Vial")
    app_version: str = "1.0.0"
    app_env: str = os.getenv("APP_ENV", "development")
    app_debug: bool = os.getenv("APP_DEBUG", "False").lower() == "true"
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
    secret_key: str = os.getenv("SECRET_KEY", "")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    radio_busqueda_max_km: float = float(os.getenv("RADIO_BUSQUEDA_MAX_KM", "50"))
    ubicacion_frescura_minutos: int = int(
        os.getenv("UBICACION_FRESCURA_MINUTOS", "15")
    )
    asignacion_plazo_respuesta_segundos: int = int(
        os.getenv("ASIGNACION_PLAZO_RESPUESTA_SEGUNDOS", "120")
    )
    asignacion_expiracion_intervalo_segundos: int = int(
        os.getenv("ASIGNACION_EXPIRACION_INTERVALO_SEGUNDOS", "15")
    )
    asignacion_expiracion_automatica: bool = (
        os.getenv("ASIGNACION_EXPIRACION_AUTOMATICA", "true").lower() == "true"
    )


settings = Settings()
