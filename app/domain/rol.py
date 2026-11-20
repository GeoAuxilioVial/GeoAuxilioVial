"""Modelo del catálogo de roles."""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Rol(Base):
	__tablename__ = "roles"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	codigo: Mapped[str] = mapped_column(String(50), unique=True, index=True)
	nombre: Mapped[str] = mapped_column(String(100))
	descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
	activo: Mapped[bool] = mapped_column(Boolean, default=True)

	@property
	def rol_id(self) -> str:
		return f"rol_{self.id:02d}"
