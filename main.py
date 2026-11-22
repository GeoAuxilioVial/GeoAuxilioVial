from fastapi import FastAPI

from app.api.routers import health, roles, usuario_router
from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.services.rol_service import inicializar_catalogo

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.app_debug)

registrar_manejadores(app)
app.include_router(health.router)
app.include_router(roles.router)
app.include_router(usuario_router.router)
inicializar_catalogo()