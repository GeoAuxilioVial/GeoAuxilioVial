"""Añade de forma segura las columnas operativas de proveedores definidas en HU-17."""
from sqlalchemy import DateTime, Float, String, inspect, text
from sqlalchemy.engine import Engine

from app.core.database import engine


COLUMNAS_HU17 = {
	"estado_habilitacion": String(30),
	"latitud": Float(),
	"longitud": Float(),
	"precision_metros": Float(),
	"actualizada_en": DateTime(timezone=True),
}


def migrar_columnas_hu17(engine_db: Engine) -> list[str]:
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
		for nombre, tipo in COLUMNAS_HU17.items():
			if nombre in columnas_existentes:
				continue
			tipo_sql = tipo.compile(dialect=engine_db.dialect)
			conexion.execute(
				text(f"ALTER TABLE proveedores ADD COLUMN {nombre} {tipo_sql}")
			)
			columnas_existentes.add(nombre)
			agregadas.append(nombre)
	return agregadas


def main() -> None:
	agregadas = migrar_columnas_hu17(engine)
	if agregadas:
		print("Columnas HU-17 agregadas: " + ", ".join(agregadas))
	else:
		print("La tabla proveedores ya contiene todas las columnas HU-17.")


if __name__ == "__main__":
	main()
