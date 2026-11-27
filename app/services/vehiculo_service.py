
import re
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ErrorNegocio
from app.domain.usuario_domain import Usuario
from app.repositories.tipo_vehiculo_repository import TipoVehiculoRepository
from app.repositories.vehiculo_repository import VehiculoRepository


def normalizar_placa(placa: str) -> str:
    return re.sub(r"[\s-]+", "", placa).upper()


def validar_placa(placa: str) -> bool:
    return bool(
        re.fullmatch(r"[A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z]", placa)
    )


class VehiculoService:
    def __init__(self, db: Session):
        self.db = db
        self.vehiculos = VehiculoRepository(db)
        self.tipos = TipoVehiculoRepository(db)

    def _obtener_propietario(self, payload: dict) -> Usuario:
        identificador = payload.get("sub", "")

        if not isinstance(identificador, str):
            raise ErrorNegocio(401, "Identidad de usuario inválida")

        coincidencia = re.fullmatch(r"usr_(\d+)", identificador)
        if not coincidencia:
            raise ErrorNegocio(401, "Identidad de usuario inválida")

        usuario = self.db.get(Usuario, int(coincidencia.group(1)))
        if usuario is None:
            raise ErrorNegocio(401, "El usuario autenticado no existe")

        return usuario

    def _validar_tipo(self, tipo_vehiculo_id: str) -> None:
        tipo = self.tipos.obtener(tipo_vehiculo_id)

        if tipo is None:
            raise ErrorNegocio(404, "Tipo de vehículo no encontrado")

        if not tipo.activo:
            raise ErrorNegocio(422, "El tipo de vehículo está inactivo")

    def _validar_datos(self, datos) -> str:
        placa = normalizar_placa(datos.placa)

        if not validar_placa(placa):
            raise ErrorNegocio(
                422,
                "La placa debe tener formato ABC123 o ABC12D",
            )

        if datos.anio < 1886 or datos.anio > date.today().year + 1:
            raise ErrorNegocio(422, "El año del vehículo no es válido")

        if datos.kilometraje < 0:
            raise ErrorNegocio(422, "El kilometraje no puede ser negativo")

        self._validar_tipo(datos.tipoVehiculoId)

        return placa

    def registrar(self, datos, payload: dict):
        propietario = self._obtener_propietario(payload)
        placa = self._validar_datos(datos)

        existente = self.vehiculos.obtener_por_placa_activa(placa)
        if existente is not None:
            raise ErrorNegocio(
                409,
                "La placa ya está registrada en otro vehículo activo",
            )

        return self.vehiculos.crear(
            placa=placa,
            marca=datos.marca.strip(),
            modelo=datos.modelo.strip(),
            anio=datos.anio,
            kilometraje=datos.kilometraje,
            tipo_vehiculo_id=datos.tipoVehiculoId,
            propietario_id=propietario.id,
        )

    def actualizar(self, vehiculo_id: str, datos, payload: dict):
        propietario = self._obtener_propietario(payload)

        vehiculo = self.vehiculos.obtener_del_propietario(
            vehiculo_id,
            propietario.id,
        )

        if vehiculo is None or not vehiculo.activo:
            raise ErrorNegocio(404, "Vehículo no encontrado")

        placa = self._validar_datos(datos)

        existente = self.vehiculos.obtener_por_placa_activa(placa)
        if existente is not None and existente.id != vehiculo.id:
            raise ErrorNegocio(
                409,
                "La placa ya está registrada en otro vehículo activo",
            )

        return self.vehiculos.actualizar(
            vehiculo=vehiculo,
            placa=placa,
            marca=datos.marca.strip(),
            modelo=datos.modelo.strip(),
            anio=datos.anio,
            kilometraje=datos.kilometraje,
            tipo_vehiculo_id=datos.tipoVehiculoId,
        )
