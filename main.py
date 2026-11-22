from fastapi import FastAPI

from app.api.routers import documentos_requeridos_router, health, roles, zonas_cobertura_router
from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.services.rol_service import inicializar_catalogo

app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.app_debug)

registrar_manejadores(app)
app.include_router(documentos_requeridos_router.router)
app.include_router(health.router)
app.include_router(roles.router)
app.include_router(zonas_cobertura_router.router)
inicializar_catalogo()
from app.core.database import SessionLocal
from app.services.documentos_requeridos_service import sembrar_documentos_base

with SessionLocal() as db:
	sembrar_documentos_base(db)