from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReglaAuxilio:
    id: str
    codigo: str
    nombre: str
    descripcion: str
    valor: Any
    editable: bool
