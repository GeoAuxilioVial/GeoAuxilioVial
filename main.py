
from fastapi import FastAPI

from app.api.routers import health, roles, parametros_auxilio
from app.api.routers.parametros_auxilio import inicializar_parametros_auxilio
from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.services.rol_service import inicializar_catalogo

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.app_debug)

registrar_manejadores(app)

app.include_router(health.router)
app.include_router(roles.router)
app.include_router(parametros_auxilio.router)

inicializar_catalogo()
inicializar_parametros_auxilio()
