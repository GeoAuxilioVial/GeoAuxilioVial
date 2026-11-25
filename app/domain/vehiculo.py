import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    __table_args__ = (
        Index(
            "uq_vehiculos_placa_activa",
            "placa",
            unique=True,
            sqlite_where=text("activo = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        default=lambda: f"veh_{uuid.uuid4().hex[:8]}",
    )
    placa: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    marca: Mapped[str] = mapped_column(String(60), nullable=False)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    kilometraje: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tipo_vehiculo_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("tipos_vehiculo.id"),
        nullable=False,
    )
    propietario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
