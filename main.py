from fastapi import FastAPI

# Importar modelos antes de inicializar el catálogo para registrar sus tablas
# en el mismo Base.metadata compartido por todo el proyecto.
from app.api.routers import health, roles, tipos_vehiculo
from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.repositories import tipo_vehiculo_repository  # noqa: F401
from app.services.rol_service import inicializar_catalogo

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.app_debug)

registrar_manejadores(app)
app.include_router(health.router)
app.include_router(roles.router)
app.include_router(tipos_vehiculo.router)

inicializar_catalogo()
