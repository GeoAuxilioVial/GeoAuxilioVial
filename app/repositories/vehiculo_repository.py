from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorNegocio
from app.domain.vehiculo import Vehiculo


class VehiculoRepository:
    def __init__(self, db: Session):
        self.db = db

    def obtener(self, vehiculo_id: str) -> Vehiculo | None:
        return self.db.get(Vehiculo, vehiculo_id)

    def obtener_por_placa_activa(self, placa: str) -> Vehiculo | None:
        consulta = select(Vehiculo).where(
            Vehiculo.placa == placa,
            Vehiculo.activo.is_(True),
        )
        return self.db.scalar(consulta)

    def obtener_del_propietario(
        self,
        vehiculo_id: str,
        propietario_id: int,
    ) -> Vehiculo | None:
        consulta = select(Vehiculo).where(
            Vehiculo.id == vehiculo_id,
            Vehiculo.propietario_id == propietario_id,
        )
        return self.db.scalar(consulta)

    def crear(
        self,
        placa: str,
        marca: str,
        modelo: str,
        anio: int,
        kilometraje: int,
        tipo_vehiculo_id: str,
        propietario_id: int,
    ) -> Vehiculo:
        vehiculo = Vehiculo(
            placa=placa,
            marca=marca,
            modelo=modelo,
            anio=anio,
            kilometraje=kilometraje,
            tipo_vehiculo_id=tipo_vehiculo_id,
            propietario_id=propietario_id,
            activo=True,
        )
        self.db.add(vehiculo)
        return self._guardar(vehiculo)

    def actualizar(
        self,
        vehiculo: Vehiculo,
        placa: str,
        marca: str,
        modelo: str,
        anio: int,
        kilometraje: int,
        tipo_vehiculo_id: str,
    ) -> Vehiculo:
        vehiculo.placa = placa
        vehiculo.marca = marca
        vehiculo.modelo = modelo
        vehiculo.anio = anio
        vehiculo.kilometraje = kilometraje
        vehiculo.tipo_vehiculo_id = tipo_vehiculo_id
        return self._guardar(vehiculo)

    def _guardar(self, vehiculo: Vehiculo) -> Vehiculo:
        try:
            self.db.commit()
            self.db.refresh(vehiculo)
            return vehiculo
        except IntegrityError as exc:
            self.db.rollback()

            if "UNIQUE constraint failed: vehiculos.placa" in str(exc.orig):
                raise ErrorNegocio(
                    409,
                    "La placa ya está registrada en otro vehículo activo",
                ) from exc

            raise
