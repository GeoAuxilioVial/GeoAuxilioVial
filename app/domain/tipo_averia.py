from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TipoAveria:
    id: str
    codigo: str
    nombre: str
    activo: bool = True


class UsoTipoAveriaPort(Protocol):
    """Contrato de consulta de dependencias de MOD-05 para aplicar RN-09."""

    def esta_en_uso(self, tipo_averia_id: str) -> bool:
        ...
