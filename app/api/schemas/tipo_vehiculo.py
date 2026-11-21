import re

from pydantic import BaseModel, Field, field_validator


class TipoVehiculoEntrada(BaseModel):
    codigo: str = Field(min_length=2, max_length=30)
    nombre: str = Field(min_length=2, max_length=80)
    categoria: str = Field(min_length=2, max_length=40)
    activo: bool = True

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, valor: str) -> str:
        valor = valor.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_]{2,30}", valor):
            raise ValueError("Use entre 2 y 30 letras, números o guiones bajos")
        return valor

    @field_validator("nombre", "categoria")
    @classmethod
    def quitar_espacios(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 2:
            raise ValueError("Debe contener al menos 2 caracteres")
        return valor


def tipo_vehiculo_a_dict(tipo) -> dict:
    return {
        "tipoVehiculoId": tipo.id,
        "codigo": tipo.codigo,
        "nombre": tipo.nombre,
        "categoria": tipo.categoria,
        "activo": tipo.activo,
    }
