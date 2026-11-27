from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas.parametros_auxilio import (
    ReglaAuxilioActualizacion,
    TipoAveriaEntrada,
    regla_auxilio_a_dict,
    tipo_averia_a_dict,
)
from app.core.database import SessionLocal, get_db
from app.core.errors import sobre
from app.core.security import requiere_admin, requiere_autenticacion
from app.domain.tipo_averia import UsoTipoAveriaPort
from app.repositories.parametros_auxilio_repository import ParametrosAuxilioRepository
from app.services.parametros_auxilio_service import (
    ConsultaUsoTipoAveriaNoConfigurada,
    ParametrosAuxilioService,
)

router = APIRouter(tags=["Parámetros de auxilio vial"])


def get_uso_tipo_averia() -> UsoTipoAveriaPort:
    return ConsultaUsoTipoAveriaNoConfigurada()


def get_service(
    db: Session = Depends(get_db),
    uso: UsoTipoAveriaPort = Depends(get_uso_tipo_averia),
) -> ParametrosAuxilioService:
    return ParametrosAuxilioService(ParametrosAuxilioRepository(db), uso)


@router.get("/api/v1/parametros/tipos-averia")
def listar_tipos_averia(
    activo: bool | None = Query(default=None),
    _: dict = Depends(requiere_autenticacion),
    servicio: ParametrosAuxilioService = Depends(get_service),
):
    tipos = [tipo_averia_a_dict(t) for t in servicio.listar_tipos(activo)]
    return sobre(True, "Catálogo de tipos de avería consultado", {"tiposAveria": tipos})


@router.post("/api/v1/parametros/tipos-averia", status_code=201)
def crear_tipo_averia(
    body: TipoAveriaEntrada,
    _: dict = Depends(requiere_admin),
    servicio: ParametrosAuxilioService = Depends(get_service),
):
    tipo = servicio.crear_tipo(**body.model_dump())
    return sobre(True, "Tipo de avería registrado", tipo_averia_a_dict(tipo))


@router.put("/api/v1/parametros/tipos-averia/{tipoAveriaId}")
def actualizar_tipo_averia(
    tipoAveriaId: str,
    body: TipoAveriaEntrada,
    _: dict = Depends(requiere_admin),
    servicio: ParametrosAuxilioService = Depends(get_service),
):
    tipo = servicio.actualizar_tipo(tipoAveriaId, **body.model_dump())
    return sobre(True, "Tipo de avería actualizado", tipo_averia_a_dict(tipo))


@router.delete("/api/v1/parametros/tipos-averia/{tipoAveriaId}")
def eliminar_tipo_averia(
    tipoAveriaId: str,
    _: dict = Depends(requiere_admin),
    servicio: ParametrosAuxilioService = Depends(get_service),
):
    servicio.eliminar_tipo(tipoAveriaId)
    return sobre(True, "Tipo de avería eliminado")


@router.get("/api/v1/parametros/reglas-auxilio")
def listar_reglas_auxilio(
    _: dict = Depends(requiere_autenticacion),
    servicio: ParametrosAuxilioService = Depends(get_service),
):
    reglas = [regla_auxilio_a_dict(r) for r in servicio.listar_reglas()]
    return sobre(True, "Reglas de auxilio consultadas", {"reglasAuxilio": reglas})


@router.put("/api/v1/parametros/reglas-auxilio/{reglaId}")
def actualizar_regla_auxilio(
    reglaId: str,
    body: ReglaAuxilioActualizacion,
    _: dict = Depends(requiere_admin),
    servicio: ParametrosAuxilioService = Depends(get_service),
):
    regla = servicio.actualizar_regla(reglaId, body.valor)
    return sobre(True, "Regla de auxilio actualizada", regla_auxilio_a_dict(regla))


def inicializar_parametros_auxilio() -> None:
    """Crea tablas y catálogos base al iniciar la aplicación."""
    from app.core.database import Base, engine
    from app.repositories import parametros_auxilio_repository  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ParametrosAuxilioRepository(db).inicializar_catalogos()
