from pydantic import BaseModel, ConfigDict, Field

from app.domain.vehiculo import Vehiculo


class VehiculoEntrada(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    placa: str = Field(min_length=1, max_length=10)
    marca: str = Field(min_length=2, max_length=60)
    modelo: str = Field(min_length=1, max_length=60)
    anio: int = Field(ge=1886)
    tipoVehiculoId: str = Field(min_length=1, max_length=20)
    kilometraje: int = Field(default=0, ge=0)


def vehiculo_a_dict(vehiculo: Vehiculo) -> dict:
    return {
        "vehiculoId": vehiculo.id,
        "placa": vehiculo.placa,
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "tipoVehiculoId": vehiculo.tipo_vehiculo_id,
        "kilometraje": vehiculo.kilometraje,
    }
