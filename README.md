# GeoAuxilioVial
GeoAuxilio Vial brinda asistencia vial inmediata (ponchaduras, batería, grúa) y resuelve la falta de seguimiento preventivo. Cotiza solicitudes, asigna al proveedor más cercano, rastrea rutas en tiempo real y programa mantenimientos. Gestiona usuarios, vehículos, ubicaciones, historial, pagos y calificaciones con geolocalización y pagos seguros.

## Refinamiento del backlog

[![Portada del refinamiento del backlog](docs/refinamiento/portada.png)](docs/refinamiento/Refinamiento_Backlog_GeoAuxilioVial_final.pdf)

📄 **[Abrir el PDF del refinamiento del backlog](docs/refinamiento/Refinamiento_Backlog_GeoAuxilioVial_final.pdf)**

- 28 historias de usuario revisadas (HU-01 a HU-28).
- 4 problemas de prioridad alta corregidos (HU-28, HU-12/HU-19, HU-26 y HU-25).
- 3 historias de talla XL divididas en sub-issues (HU-19, HU-20 y HU-26).
- 11 decisiones abiertas registradas con propuesta, responsable e impacto.
- Grafo de dependencias sin ciclos, ordenado en 9 olas de trabajo.

## Historias de usuario

Las 28 historias están en [`docs/historias_usuario`](docs/historias_usuario/README.md).

## Migración aditiva de proveedores (HU-17)

Antes de ejecutar una versión que use los campos operativos de proveedor, ejecute desde la raíz del proyecto:

```powershell
.\venv\Scripts\python.exe migrate_hu17_provider_columns.py
```

El script usa la conexión configurada en `DATABASE_URL`, comprueba las columnas existentes mediante SQLAlchemy y agrega únicamente las columnas HU-17 que falten en `proveedores`. Es idempotente, no elimina ni recrea datos y no usa Alembic. Las tablas nuevas del microservicio se crean mediante el mecanismo existente de SQLAlchemy.

HU-14 conserva el perfil comercial y la asociación de cobertura en tablas propias del microservicio. `archivos_privados` es un registro interno de referencias y propietario; no existe un endpoint público de carga y ninguna API devuelve su clave de almacenamiento. El componente interno que reciba los archivos debe registrar la referencia privada antes de que el proveedor envíe sus metadatos.
