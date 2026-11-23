"""Modelo de usuarios para registro e inicio de sesion."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Usuario(Base):
	__tablename__ = "usuarios"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	nombre: Mapped[str] = mapped_column(String(100))
	correo: Mapped[str] = mapped_column(String(255), unique=True, index=True)
	password_hash: Mapped[str] = mapped_column(String(255))
	telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
	roles: Mapped[str] = mapped_column(String(255), default="CLIENTE")

	@property
	def usuario_id(self) -> str:
		return f"usr_{self.id:03d}"

	def lista_roles(self) -> list[str]:
		return [rol for rol in self.roles.split(",") if rol]
