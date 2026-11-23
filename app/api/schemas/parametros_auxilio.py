import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TipoAveriaEntrada(BaseModel):
    codigo: str = Field(min_length=2, max_length=40)
    nombre: str = Field(min_length=2, max_length=100)
    activo: bool = True

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, valor: str) -> str:
        valor = valor.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_]{2,40}", valor):
            raise ValueError("Use letras sin tildes, números o guion bajo")
        return valor

    @field_validator("nombre")
    @classmethod
    def normalizar_nombre(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 2:
            raise ValueError("Debe contener al menos 2 caracteres")
        return valor


class ReglaAuxilioActualizacion(BaseModel):
    valor: Any


def tipo_averia_a_dict(tipo) -> dict:
    return {
        "tipoAveriaId": tipo.id,
        "codigo": tipo.codigo,
        "nombre": tipo.nombre,
        "activo": tipo.activo,
    }


def regla_auxilio_a_dict(regla) -> dict:
    return {
        "reglaId": regla.id,
        "codigo": regla.codigo,
        "nombre": regla.nombre,
        "descripcion": regla.descripcion,
        "valor": regla.valor,
        "editable": regla.editable,
    }
