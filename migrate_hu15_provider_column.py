"""Agrega la fecha de cambio de disponibilidad de HU-15."""
from sqlalchemy import DateTime, inspect, text
from sqlalchemy.engine import Engine

from app.core.database import engine


def migrar_columna_hu15(engine_db: Engine) -> bool:
	inspector = inspect(engine_db)
	if not inspector.has_table("proveedores"):
		raise RuntimeError(
			"No existe la tabla proveedores; inicialice primero la base de datos del microservicio"
		)
	if "estado_operativo_actualizado_en" in {
		columna["name"] for columna in inspector.get_columns("proveedores")
	}:
		return False

	tipo_sql = DateTime(timezone=True).compile(dialect=engine_db.dialect)
	with engine_db.begin() as conexion:
		conexion.execute(
			text(
				"ALTER TABLE proveedores ADD COLUMN "
				f"estado_operativo_actualizado_en {tipo_sql}"
			)
		)
	return True


def main() -> None:
	if migrar_columna_hu15(engine):
		print("Columna HU-15 agregada: estado_operativo_actualizado_en")
	else:
		print("La tabla proveedores ya contiene la columna de actualización HU-15.")


if __name__ == "__main__":
	main()
