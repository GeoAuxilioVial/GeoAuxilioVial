"""Añade columnas de estado documental de HU-16 sin reconstruir datos."""
from sqlalchemy import String, inspect, text
from sqlalchemy.engine import Engine

from app.core.database import engine


COLUMNAS_HU16 = {
	"estado_operativo": (String(30), " DEFAULT 'NO_DISPONIBLE' NOT NULL"),
	"motivo_habilitacion": (String(500), ""),
}


def migrar_columnas_hu16(engine_db: Engine) -> list[str]:
	inspector = inspect(engine_db)
	if not inspector.has_table("proveedores"):
		raise RuntimeError(
			"No existe la tabla proveedores; inicialice primero la base de datos del microservicio"
		)

	columnas_existentes = {
		columna["name"] for columna in inspector.get_columns("proveedores")
	}
	agregadas = []
	with engine_db.begin() as conexion:
		for nombre, (tipo, restriccion) in COLUMNAS_HU16.items():
			if nombre in columnas_existentes:
				continue
			tipo_sql = tipo.compile(dialect=engine_db.dialect)
			conexion.execute(
				text(
					f"ALTER TABLE proveedores ADD COLUMN "
					f"{nombre} {tipo_sql}{restriccion}"
				)
			)
			agregadas.append(nombre)
	return agregadas


def main() -> None:
	agregadas = migrar_columnas_hu16(engine)
	if agregadas:
		print("Columnas HU-16 agregadas: " + ", ".join(agregadas))
	else:
		print("La tabla proveedores ya contiene todas las columnas HU-16.")


if __name__ == "__main__":
	main()
