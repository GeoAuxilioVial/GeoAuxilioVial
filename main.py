import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import (
	asignacion_router,
	documentos_requeridos_router,
	health,
	parametros_auxilio,
	proveedor_router,
	roles,
	tipos_vehiculo,
	usuario_router,
	zonas_cobertura_router,
)
from app.api.routers.parametros_auxilio import inicializar_parametros_auxilio
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import registrar_manejadores
from app.repositories import tipo_vehiculo_repository  # noqa: F401
from app.services.asignacion_service import expirar_asignaciones_vencidas
from app.services.documentos_requeridos_service import sembrar_documentos_base
from app.services.rol_service import inicializar_catalogo

logger = logging.getLogger(__name__)


def _expirar_asignaciones() -> None:
	with SessionLocal() as db:
		expirar_asignaciones_vencidas(db)


async def _tarea_expiracion_asignaciones() -> None:
	while True:
		await asyncio.sleep(settings.asignacion_expiracion_intervalo_segundos)
		try:
			await asyncio.to_thread(_expirar_asignaciones)
		except SQLAlchemyError:
			logger.exception("Falló la expiración periódica de asignaciones")


def _registrar_fallo_tarea(task: asyncio.Task) -> None:
	if task.cancelled():
		return
	excepcion = task.exception()
	if excepcion is not None:
		logger.error(
			"La tarea periódica de expiración de asignaciones terminó",
			exc_info=(type(excepcion), excepcion, excepcion.__traceback__),
		)


@asynccontextmanager
async def lifespan(app: FastAPI):
	tarea = None
	if settings.asignacion_expiracion_automatica:
		if settings.asignacion_expiracion_intervalo_segundos <= 0:
			raise RuntimeError(
				"ASIGNACION_EXPIRACION_INTERVALO_SEGUNDOS debe ser mayor que cero"
			)
		tarea = asyncio.create_task(_tarea_expiracion_asignaciones())
		tarea.add_done_callback(_registrar_fallo_tarea)
	try:
		yield
	finally:
		if tarea is not None:
			tarea.cancel()
			try:
				await tarea
			except asyncio.CancelledError:
				pass


app = FastAPI(
	title=settings.app_name,
	version=settings.app_version,
	debug=settings.app_debug,
	lifespan=lifespan,
)

registrar_manejadores(app)

app.include_router(health.router)
app.include_router(asignacion_router.router)
app.include_router(roles.router)
app.include_router(parametros_auxilio.router)
app.include_router(documentos_requeridos_router.router)
app.include_router(tipos_vehiculo.router)
app.include_router(usuario_router.router)
app.include_router(usuario_router.perfil_router)
app.include_router(proveedor_router.router)
app.include_router(proveedor_router.backoffice_router)
app.include_router(zonas_cobertura_router.router)

inicializar_catalogo()
inicializar_parametros_auxilio()

with SessionLocal() as db:
	sembrar_documentos_base(db)
