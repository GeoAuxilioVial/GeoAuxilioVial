from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas.tipo_vehiculo import TipoVehiculoEntrada, tipo_vehiculo_a_dict
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_admin, requiere_autenticacion
from app.domain.tipo_vehiculo import UsoTipoVehiculoPort
from app.repositories.tipo_vehiculo_repository import TipoVehiculoRepository
from app.services.tipo_vehiculo_service import ConsultaUsoNoConfigurada, TipoVehiculoService

router = APIRouter(
    prefix="/api/v1/parametros/tipos-vehiculo",
    tags=["Tipos de vehículo"],
)


def get_uso() -> UsoTipoVehiculoPort:
    return ConsultaUsoNoConfigurada()


def get_service(
    db: Session = Depends(get_db),
    uso: UsoTipoVehiculoPort = Depends(get_uso),
) -> TipoVehiculoService:
    return TipoVehiculoService(TipoVehiculoRepository(db), uso)


@router.get("")
def listar(
    activo: bool | None = Query(default=None),
    _: dict = Depends(requiere_autenticacion),
    servicio: TipoVehiculoService = Depends(get_service),
):
    tipos = [tipo_vehiculo_a_dict(t) for t in servicio.listar(activo)]
    return sobre(True, "Catálogo de tipos de vehículo consultado", {"tiposVehiculo": tipos})


@router.post("", status_code=201)
def crear(
    body: TipoVehiculoEntrada,
    _: dict = Depends(requiere_admin),
    servicio: TipoVehiculoService = Depends(get_service),
):
    tipo = servicio.crear(**body.model_dump())
    return sobre(True, "Tipo de vehículo registrado", tipo_vehiculo_a_dict(tipo))


@router.put("/{tipo_vehiculo_id}")
def actualizar(
    tipo_vehiculo_id: str,
    body: TipoVehiculoEntrada,
    _: dict = Depends(requiere_admin),
    servicio: TipoVehiculoService = Depends(get_service),
):
    tipo = servicio.actualizar(tipo_vehiculo_id, **body.model_dump())
    return sobre(True, "Tipo de vehículo actualizado", tipo_vehiculo_a_dict(tipo))


@router.delete("/{tipo_vehiculo_id}")
def eliminar(
    tipo_vehiculo_id: str,
    _: dict = Depends(requiere_admin),
    servicio: TipoVehiculoService = Depends(get_service),
):
    servicio.eliminar(tipo_vehiculo_id)
    return sobre(True, "Tipo de vehículo eliminado")
