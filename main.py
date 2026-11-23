
from fastapi import FastAPI

from app.api.routers import health, roles, parametros_auxilio
from app.api.routers.parametros_auxilio import inicializar_parametros_auxilio
# Importar modelos antes de inicializar el catálogo para registrar sus tablas
# en el mismo Base.metadata compartido por todo el proyecto.
from app.api.routers import health, roles, tipos_vehiculo
from app.api.routers import health, proveedor_router, roles, usuario_router
from app.api.routers import documentos_requeridos_router, health, roles, usuario_router, zonas_cobertura_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import registrar_manejadores
from app.repositories import tipo_vehiculo_repository  # noqa: F401
from app.services.documentos_requeridos_service import sembrar_documentos_base
from app.services.rol_service import inicializar_catalogo

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.app_debug)

registrar_manejadores(app)

app.include_router(health.router)
app.include_router(roles.router)
app.include_router(parametros_auxilio.router)

inicializar_catalogo()
inicializar_parametros_auxilio()
app.include_router(documentos_requeridos_router.router)
app.include_router(health.router)
app.include_router(roles.router)
app.include_router(tipos_vehiculo.router)

inicializar_catalogo()
app.include_router(usuario_router.router)
app.include_router(usuario_router.perfil_router)
inicializar_catalogo()
app.include_router(proveedor_router.router)
inicializar_catalogo()
app.include_router(zonas_cobertura_router.router)
inicializar_catalogo()

with SessionLocal() as db:
    sembrar_documentos_base(db)
