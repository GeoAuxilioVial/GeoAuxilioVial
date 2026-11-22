"""Sobre estándar de respuesta y manejo de errores."""
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ZONA = timezone(timedelta(hours=-5))


def sobre(exito: bool, mensaje: str, datos=None) -> dict:
	return {
		"exito": exito,
		"mensaje": mensaje,
		"datos": datos,
		"fechaHora": datetime.now(ZONA).isoformat(timespec="seconds"),
	}


class ErrorNegocio(Exception):
	def __init__(self, status_code: int, mensaje: str, datos=None):
		self.status_code = status_code
		self.mensaje = mensaje
		self.datos = datos


def _codigo_error(tipo: str) -> str:
	if tipo == "missing":
		return "CAMPO_OBLIGATORIO"
	if tipo in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
		return "FUERA_DE_RANGO"
	if tipo == "extra_forbidden":
		return "CAMPO_NO_EDITABLE"
	return "FORMATO_INVALIDO"


def registrar_manejadores(app: FastAPI) -> None:
	@app.exception_handler(ErrorNegocio)
	async def _negocio(request: Request, exc: ErrorNegocio):
		return JSONResponse(status_code=exc.status_code, content=sobre(False, exc.mensaje, exc.datos))

	@app.exception_handler(RequestValidationError)
	async def _validacion(request: Request, exc: RequestValidationError):
		if any(e["type"] == "json_invalid" for e in exc.errors()):
			return JSONResponse(status_code=400, content=sobre(False, "Solicitud mal formada"))
		errores = [
			{
				"campo": ".".join(str(p) for p in e["loc"][1:]) or "body",
				"codigo": _codigo_error(e["type"]),
				"mensaje": e["msg"],
			}
			for e in exc.errors()
		]
		return JSONResponse(
			status_code=422,
			content=sobre(False, "Uno o más campos no cumplen las validaciones", {"errores": errores}),
		)

	@app.exception_handler(StarletteHTTPException)
	async def _http(request: Request, exc: StarletteHTTPException):
		mensaje = "Recurso no encontrado" if exc.status_code == 404 else str(exc.detail)
		return JSONResponse(status_code=exc.status_code, content=sobre(False, mensaje))

	@app.exception_handler(Exception)
	async def _interno(request: Request, exc: Exception):
		return JSONResponse(status_code=500, content=sobre(False, "Error interno controlado"))
