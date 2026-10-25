# GeoAuxilio Vial — Historias de usuario (HU-01 a HU-28)

Historias de usuario del Parcial #2 de Web Services: una historia por cada funcionalidad del alcance (FUN-01 a FUN-28). Cada historia tiene su propio archivo `HU-NN.md` en esta carpeta.

## Contexto

- Plataforma marketplace de asistencia vial bajo demanda y mantenimiento preventivo.
- Arquitectura de 9 módulos con persistencia aislada, contratos JSON y autenticación JWT.
- Cada archivo incluye: Dado / Para / Que, flujo esperado, criterios de aceptación, endpoint, ejemplos JSON, notas técnicas, requisitos de pruebas, trazabilidad (MOD, FUN, PRO) y los elementos comunes (sobre de respuesta, errores y definición de hecho).

## Índice

| HU | Título | Módulo | Función | Proceso |
|---|---|---|---|---|
| [HU-01](HU-01.md) | Administrar catálogos y tipos de usuarios/roles | MOD-09 | FUN-22 | PRO-22 |
| [HU-02](HU-02.md) | Administrar catálogo de tipologías y categorías de vehículos | MOD-09 | FUN-23 | PRO-23 |
| [HU-03](HU-03.md) | Administrar parámetros de proveedores, documentación legal y zonas de cobertura | MOD-09 | FUN-24 | PRO-24 |
| [HU-04](HU-04.md) | Administrar reglas, tipos de avería y criterios de auxilio vial | MOD-09 | FUN-25 | PRO-25 |
| [HU-05](HU-05.md) | Administrar catálogos, planes e intervalos de mantenimiento preventivo | MOD-09 | FUN-26 | PRO-26 |
| [HU-06](HU-06.md) | Administrar esquemas tarifarios base y métodos de pago habilitados | MOD-09 | FUN-27 | PRO-27 |
| [HU-07](HU-07.md) | Administrar criterios de evaluación del servicio y escalas de reputación ponderada | MOD-09 | FUN-28 | PRO-28 |
| [HU-08](HU-08.md) | Registrar e iniciar sesión de usuarios con emisión de tokens JWT firmados | MOD-01 | FUN-01 | PRO-01 |
| [HU-09](HU-09.md) | Gestionar perfiles de usuario aplicando permisos y visibilidad según rol asignado | MOD-01 | FUN-02 | PRO-02 |
| [HU-10](HU-10.md) | Solicitar y validar la ampliación de cuenta hacia rol dual (cliente y proveedor simultáneo) | MOD-01 | FUN-03 | PRO-03 |
| [HU-11](HU-11.md) | Registrar vehículos validando unicidad de placa y asociándolos al propietario | MOD-02 | FUN-04 | PRO-04 |
| [HU-12](HU-12.md) | Actualizar el estado operativo del vehículo a "varado" ante un reporte de falla | MOD-02 | FUN-05 | PRO-05 |
| [HU-13](HU-13.md) | Consultar historial integral de servicios mecánicos e indicador de kilometraje acumulado | MOD-02 | FUN-06 | PRO-06 |
| [HU-14](HU-14.md) | Registrar proveedores con validación de documentos legales y estado inicial pendiente | MOD-03 | FUN-07 | PRO-07 |
| [HU-15](HU-15.md) | Alternar y registrar el estado de disponibilidad operativa del proveedor | MOD-03 | FUN-08 | PRO-08 |
| [HU-16](HU-16.md) | Administrar vigencia de documentación legal y suspender proveedores con documentos vencidos | MOD-03 | FUN-09 | PRO-09 |
| [HU-17](HU-17.md) | Transmitir y registrar coordenadas GPS del proveedor en tiempo real con control de frescura | MOD-04 | FUN-10 | PRO-10 |
| [HU-18](HU-18.md) | Consultar e indexar espacialmente proveedores cercanos disponibles dentro del radio de cobertura | MOD-04 | FUN-11 | PRO-11 |
| [HU-19](HU-19.md) | Calcular y presentar cotización estimada del auxilio en tiempo real | MOD-05 | FUN-12 | PRO-12 |
| [HU-20](HU-20.md) | Asignar atómicamente el proveedor disponible más cercano mediante bloqueo optimista | MOD-05 | FUN-13 | PRO-13 |
| [HU-21](HU-21.md) | Realizar seguimiento cartográfico en vivo del desplazamiento del auxilio | MOD-05 | FUN-14 | PRO-14 |
| [HU-22](HU-22.md) | Cerrar formalmente el servicio de auxilio y disparar eventos de pago y calificación | MOD-05 | FUN-15 | PRO-15 |
| [HU-23](HU-23.md) | Agendar y confirmar citas de mantenimiento preventivo con talleres mecánicos aliados | MOD-06 | FUN-16 | PRO-16 |
| [HU-24](HU-24.md) | Generar y despachar recordatorios automatizados de mantenimiento por umbrales de uso | MOD-06 | FUN-17 | PRO-17 |
| [HU-25](HU-25.md) | Registrar el mantenimiento preventivo ejecutado y actualizar la hoja de vida vehicular | MOD-06 | FUN-18 | PRO-18 |
| [HU-26](HU-26.md) | Liquidar tarifa dinámica final y procesar retención/liberación de pago al proveedor | MOD-07 | FUN-19 | PRO-19 |
| [HU-27](HU-27.md) | Registrar calificación numérica y reseña del cliente sobre el servicio recibido | MOD-08 | FUN-20 | PRO-20 |
| [HU-28](HU-28.md) | Calcular y publicar el índice de reputación ponderada del proveedor | MOD-08 | FUN-21 | PRO-21 |

## Módulos

MOD-01 Autenticación e identidades · MOD-02 Gestión de vehículos · MOD-03 Gestión de proveedores · MOD-04 Motor geoespacial · MOD-05 Orquestador de auxilio vial · MOD-06 Mantenimiento preventivo · MOD-07 Pagos · MOD-08 Calificaciones y reputación · MOD-09 Parametrización.

## Nota

Los endpoints y contratos descritos son la especificación propuesta por el equipo; se cotejan con el inventario de APIs antes de declararse implementados.
