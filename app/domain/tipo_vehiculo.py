from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TipoVehiculo:
    id: str
    codigo: str
    nombre: str
    categoria: str
    activo: bool = True


class UsoTipoVehiculoPort(Protocol):
    """Contrato de integración con MOD-02 para validar RN-09.

    La implementación concreta debe consultar si existen vehículos activos
    asociados al tipo. No se debe asumir que el tipo está libre si MOD-02
    todavía no está conectado.
    """

    def esta_en_uso(self, tipo_vehiculo_id: str) -> bool:
        ...


def normalizar_codigo(codigo: str) -> str:
    return codigo.strip().upper()
