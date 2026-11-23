import uuid

from sqlalchemy import Boolean, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.core.errors import ErrorNegocio
from app.domain.tipo_vehiculo import TipoVehiculo


class TipoVehiculoModel(Base):
    __tablename__ = "tipos_vehiculo"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


def _a_dominio(modelo: TipoVehiculoModel) -> TipoVehiculo:
    return TipoVehiculo(
        id=modelo.id,
        codigo=modelo.codigo,
        nombre=modelo.nombre,
        categoria=modelo.categoria,
        activo=modelo.activo,
    )


class TipoVehiculoRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar(self, activo: bool | None = None) -> list[TipoVehiculo]:
        consulta = select(TipoVehiculoModel).order_by(TipoVehiculoModel.codigo)
        if activo is not None:
            consulta = consulta.where(TipoVehiculoModel.activo.is_(activo))
        return [_a_dominio(m) for m in self.db.scalars(consulta).all()]

    def obtener_modelo(self, tipo_id: str) -> TipoVehiculoModel | None:
        return self.db.get(TipoVehiculoModel, tipo_id)

    def obtener(self, tipo_id: str) -> TipoVehiculo | None:
        modelo = self.obtener_modelo(tipo_id)
        return _a_dominio(modelo) if modelo else None

    def obtener_por_codigo(self, codigo: str) -> TipoVehiculo | None:
        modelo = self.db.scalar(
            select(TipoVehiculoModel).where(TipoVehiculoModel.codigo == codigo)
        )
        return _a_dominio(modelo) if modelo else None

    def crear(self, codigo: str, nombre: str, categoria: str, activo: bool) -> TipoVehiculo:
        modelo = TipoVehiculoModel(
            id=f"tv_{uuid.uuid4().hex[:8]}",
            codigo=codigo,
            nombre=nombre,
            categoria=categoria,
            activo=activo,
        )
        self.db.add(modelo)
        return self._guardar(modelo)

    def actualizar(
        self, tipo_id: str, codigo: str, nombre: str, categoria: str, activo: bool
    ) -> TipoVehiculo:
        modelo = self.obtener_modelo(tipo_id)
        if modelo is None:
            raise ErrorNegocio(404, "Tipo de vehículo no encontrado")
        modelo.codigo = codigo
        modelo.nombre = nombre
        modelo.categoria = categoria
        modelo.activo = activo
        return self._guardar(modelo)

    def eliminar(self, tipo_id: str) -> None:
        modelo = self.obtener_modelo(tipo_id)
        if modelo is None:
            raise ErrorNegocio(404, "Tipo de vehículo no encontrado")
        try:
            self.db.delete(modelo)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ErrorNegocio(409, "No se puede eliminar el tipo de vehículo porque tiene registros relacionados")

    def _guardar(self, modelo: TipoVehiculoModel) -> TipoVehiculo:
        try:
            self.db.commit()
            self.db.refresh(modelo)
            return _a_dominio(modelo)
        except IntegrityError:
            self.db.rollback()
            raise ErrorNegocio(409, "Ya existe un tipo de vehículo con ese código")
