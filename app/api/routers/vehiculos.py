from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas.vehiculo import VehiculoEntrada, vehiculo_a_dict
from app.core.database import get_db
from app.core.errors import sobre
from app.core.security import requiere_autenticacion
from app.services.vehiculo_service import VehiculoService


router = APIRouter(
    prefix="/api/v1/vehiculos",
    tags=["Vehículos"],
)


@router.post("", status_code=201)
def registrar_vehiculo(
    datos: VehiculoEntrada,
    payload: dict = Depends(requiere_autenticacion),
    db: Session = Depends(get_db),
):
    vehiculo = VehiculoService(db).registrar(datos, payload)

    return sobre(
        True,
        "Vehículo registrado correctamente",
        vehiculo_a_dict(vehiculo),
    )


@router.put("/{vehiculoId}")
def actualizar_vehiculo(
    vehiculoId: str,
    datos: VehiculoEntrada,
    payload: dict = Depends(requiere_autenticacion),
    db: Session = Depends(get_db),
):
    vehiculo = VehiculoService(db).actualizar(
        vehiculoId,
        datos,
        payload,
    )

    return sobre(
        True,
        "Vehículo actualizado correctamente",
        vehiculo_a_dict(vehiculo),
    )
