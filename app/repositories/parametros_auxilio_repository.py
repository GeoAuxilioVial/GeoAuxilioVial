import uuid

from sqlalchemy import Boolean, JSON, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.core.errors import ErrorNegocio
from app.domain.regla_auxilio import ReglaAuxilio
from app.domain.tipo_averia import TipoAveria


class TipoAveriaModel(Base):
    __tablename__ = "tipos_averia"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReglaAuxilioModel(Base):
    __tablename__ = "reglas_auxilio"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    valor: Mapped[object] = mapped_column(JSON, nullable=False)
    editable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


def _tipo_a_dominio(modelo: TipoAveriaModel) -> TipoAveria:
    return TipoAveria(modelo.id, modelo.codigo, modelo.nombre, modelo.activo)


def _regla_a_dominio(modelo: ReglaAuxilioModel) -> ReglaAuxilio:
    return ReglaAuxilio(
        modelo.id, modelo.codigo, modelo.nombre, modelo.descripcion, modelo.valor, modelo.editable
    )


class ParametrosAuxilioRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar_tipos(self, activo: bool | None = None) -> list[TipoAveria]:
        consulta = select(TipoAveriaModel).order_by(TipoAveriaModel.codigo)
        if activo is not None:
            consulta = consulta.where(TipoAveriaModel.activo.is_(activo))
        return [_tipo_a_dominio(m) for m in self.db.scalars(consulta).all()]

    def obtener_tipo_modelo(self, tipo_id: str) -> TipoAveriaModel | None:
        return self.db.get(TipoAveriaModel, tipo_id)

    def obtener_tipo(self, tipo_id: str) -> TipoAveria | None:
        modelo = self.obtener_tipo_modelo(tipo_id)
        return _tipo_a_dominio(modelo) if modelo else None

    def obtener_tipo_por_codigo(self, codigo: str) -> TipoAveria | None:
        modelo = self.db.scalar(select(TipoAveriaModel).where(TipoAveriaModel.codigo == codigo))
        return _tipo_a_dominio(modelo) if modelo else None

    def crear_tipo(self, codigo: str, nombre: str, activo: bool) -> TipoAveria:
        modelo = TipoAveriaModel(
            id=f"ave_{uuid.uuid4().hex[:10]}", codigo=codigo, nombre=nombre, activo=activo
        )
        self.db.add(modelo)
        return self._guardar_tipo(modelo)

    def actualizar_tipo(self, tipo_id: str, codigo: str, nombre: str, activo: bool) -> TipoAveria:
        modelo = self.obtener_tipo_modelo(tipo_id)
        if modelo is None:
            raise ErrorNegocio(404, "Tipo de avería no encontrado")
        modelo.codigo, modelo.nombre, modelo.activo = codigo, nombre, activo
        return self._guardar_tipo(modelo)

    def eliminar_tipo(self, tipo_id: str) -> None:
        modelo = self.obtener_tipo_modelo(tipo_id)
        if modelo is None:
            raise ErrorNegocio(404, "Tipo de avería no encontrado")
        try:
            self.db.delete(modelo)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ErrorNegocio(409, "No se puede eliminar el tipo de avería porque tiene registros relacionados")

    def _guardar_tipo(self, modelo: TipoAveriaModel) -> TipoAveria:
        try:
            self.db.commit()
            self.db.refresh(modelo)
            return _tipo_a_dominio(modelo)
        except IntegrityError:
            self.db.rollback()
            raise ErrorNegocio(409, "Ya existe un tipo de avería con ese código")

    def listar_reglas(self) -> list[ReglaAuxilio]:
        consulta = select(ReglaAuxilioModel).order_by(ReglaAuxilioModel.codigo)
        return [_regla_a_dominio(m) for m in self.db.scalars(consulta).all()]

    def obtener_regla_modelo(self, regla_id: str) -> ReglaAuxilioModel | None:
        return self.db.get(ReglaAuxilioModel, regla_id)

    def actualizar_regla(self, regla_id: str, valor: object) -> ReglaAuxilio:
        modelo = self.obtener_regla_modelo(regla_id)
        if modelo is None:
            raise ErrorNegocio(404, "Regla de auxilio no encontrada")
        if not modelo.editable:
            raise ErrorNegocio(422, "La regla es un invariante del dominio y no puede modificarse")
        modelo.valor = valor
        try:
            self.db.commit()
            self.db.refresh(modelo)
            return _regla_a_dominio(modelo)
        except IntegrityError:
            self.db.rollback()
            raise ErrorNegocio(422, "El valor de la regla no cumple las restricciones")

    def inicializar_catalogos(self) -> None:
        tipos_base = [
            ("PONCHADURA", "Ponchadura"),
            ("DESCARGA_BATERIA", "Descarga de batería"),
            ("FALTA_COMBUSTIBLE", "Falta de combustible"),
            ("RECALENTAMIENTO", "Recalentamiento"),
            ("REMOLQUE", "Remolque"),
        ]
        for codigo, nombre in tipos_base:
            if self.obtener_tipo_por_codigo(codigo) is None:
                self.db.add(TipoAveriaModel(
                    id=f"ave_{uuid.uuid4().hex[:10]}", codigo=codigo, nombre=nombre, activo=True
                ))
        # Estos valores son invariantes expresos del dominio: no son editables por HU-04.
        reglas_fijas = [
            ("UBICACION_ANTIGUEDAD_MAX_MIN", "Antigüedad máxima de ubicación", "Frescura máxima de ubicación GPS en minutos", 2),
            ("VENTANA_CALIFICACION_HORAS", "Ventana de calificación", "Ventana de tiempo para calificar un auxilio en horas", 48),
        ]
        for codigo, nombre, descripcion, valor in reglas_fijas:
            existente = self.db.scalar(select(ReglaAuxilioModel).where(ReglaAuxilioModel.codigo == codigo))
            if existente is None:
                self.db.add(ReglaAuxilioModel(
                    id=codigo.lower(), codigo=codigo, nombre=nombre,
                    descripcion=descripcion, valor=valor, editable=False,
                ))
        self.db.commit()
