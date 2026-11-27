"""Endpoints de administración del tarifario y métodos de pago (HU-06)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.tarifario import (
    MetodoPagoActualizacion,
    TarifarioActualizacion,
    metodo_pago_a_dict,
    tarifario_a_dict,
)
from app.core.database import SessionLocal, get_db
from app.core.errors import sobre
from app.core.security import requiere_admin, requiere_autenticacion
from app.repositories.tarifario_repository import TarifarioRepository
from app.services.tarifario_service import TarifarioService

router = APIRouter(tags=["Parámetros financieros - HU-06"])


def get_service(db: Session = Depends(get_db)) -> TarifarioService:
    return TarifarioService(TarifarioRepository(db))


@router.get("/api/v1/parametros/tarifario")
def consultar_tarifario(
    _: dict = Depends(requiere_autenticacion),
    servicio: TarifarioService = Depends(get_service),
):
    tarifario = servicio.consultar_tarifario()
    return sobre(True, "Tarifario vigente consultado", tarifario_a_dict(tarifario))


@router.put("/api/v1/parametros/tarifario")
def actualizar_tarifario(
    body: TarifarioActualizacion,
    _: dict = Depends(requiere_admin),
    servicio: TarifarioService = Depends(get_service),
):
    tarifario = servicio.actualizar_tarifario(body)
    return sobre(True, "Tarifario actualizado", tarifario_a_dict(tarifario))


@router.get("/api/v1/parametros/metodos-pago")
def listar_metodos_pago(
    _: dict = Depends(requiere_autenticacion),
    servicio: TarifarioService = Depends(get_service),
):
    metodos = [metodo_pago_a_dict(item) for item in servicio.listar_metodos_pago()]
    return sobre(True, "Métodos de pago consultados", {"metodosPago": metodos})


@router.put("/api/v1/parametros/metodos-pago/{metodoPagoId}")
def actualizar_metodo_pago(
    metodoPagoId: str,
    body: MetodoPagoActualizacion,
    _: dict = Depends(requiere_admin),
    servicio: TarifarioService = Depends(get_service),
):
    metodo = servicio.actualizar_metodo_pago(metodoPagoId, body.habilitado)
    return sobre(True, "Método de pago actualizado", metodo_pago_a_dict(metodo))


def inicializar_hu06() -> None:
    """Crea las tablas HU-06 y siembra datos iniciales sin duplicarlos."""
    from app.core.database import Base, engine

    # Importar modelos antes de create_all para registrarlos en metadata.
    from app.repositories import tarifario_repository  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        TarifarioRepository(db).inicializar_catalogos()
