import datetime as dt
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.errors import ZONA
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import (
	ArchivoPrivado,
	DatosProveedor,
	DocumentoProveedor,
)
from app.domain.proveedor_hu16_domain import AuditoriaDocumento
from app.domain.usuario_domain import Usuario
from app.services.documentos_requeridos_service import sembrar_documentos_base
from app.services.proveedor_hu16_service import (
	EVENTO_DOCUMENTO_VENCIDO,
	procesar_vencimientos,
)
from main import app
from migrate_hu16_provider_columns import migrar_columnas_hu16

MIS_DOCUMENTOS = "/api/v1/proveedores/me/documentos"
DOCUMENTOS = "/api/v1/proveedores/documentos"
BACKOFFICE_DOCUMENTOS = "/api/v1/backoffice/proveedores"


def _token(usuario_id: int, roles: list[str]) -> str:
	return jwt.encode(
		{
			"sub": f"usr_{usuario_id:03d}",
			"roles": roles,
			"rol": roles[0],
			"exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
		},
		settings.secret_key,
		algorithm="HS256",
	)


def _headers(usuario_id: int, roles: list[str]) -> dict[str, str]:
	return {"Authorization": f"Bearer {_token(usuario_id, roles)}"}


def _hoy() -> dt.date:
	return dt.datetime.now(ZONA).date()


@pytest.fixture
def vigencia_context():
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	Base.metadata.create_all(bind=engine)
	factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
	with factory() as db:
		sembrar_documentos_base(db)

	def override_get_db():
		db = factory()
		try:
			yield db
		finally:
			db.close()

	app.dependency_overrides[get_db] = override_get_db
	try:
		with TestClient(app, raise_server_exceptions=False) as client:
			yield {"db": factory, "client": client}
	finally:
		app.dependency_overrides.pop(get_db, None)
		Base.metadata.drop_all(bind=engine)
		engine.dispose()


def _crear_proveedor(
	contexto,
	estado_habilitacion: str = "HABILITADO",
	estado_operativo: str = "NO_DISPONIBLE",
	motivo: str | None = None,
	roles: str = "PROVEEDOR",
) -> tuple[int, int]:
	with contexto["db"]() as db:
		usuario = Usuario(
			nombre="Proveedor HU16",
			correo=f"hu16.{uuid.uuid4().hex}@example.com",
			password_hash="hash-no-utilizado",
			roles=roles,
		)
		db.add(usuario)
		db.flush()
		proveedor = Proveedor(
			usuario_id=usuario.id,
			estado_habilitacion=estado_habilitacion,
			estado_operativo=estado_operativo,
			motivo_habilitacion=motivo,
		)
		db.add(proveedor)
		db.flush()
		db.add(
			DatosProveedor(
				proveedor_id=proveedor.id,
				nombre_comercial="Proveedor HU16",
				tipo_proveedor="GRUA",
			)
		)
		db.commit()
		return usuario.id, proveedor.id


def _crear_usuario(contexto, roles: str) -> int:
	with contexto["db"]() as db:
		usuario = Usuario(
			nombre="Usuario HU16",
			correo=f"hu16.usuario.{uuid.uuid4().hex}@example.com",
			password_hash="hash-no-utilizado",
			roles=roles,
		)
		db.add(usuario)
		db.commit()
		return usuario.id


def _crear_documento(
	contexto,
	proveedor_id: int,
	tipo: str,
	estado: str,
	dias_vencimiento: int | None = 30,
	reemplaza_id: int | None = None,
) -> int:
	with contexto["db"]() as db:
		archivo_id = f"file_{uuid.uuid4().hex}"
		db.add(
			ArchivoPrivado(
				archivo_id=archivo_id,
				proveedor_id=proveedor_id,
				clave_almacenamiento=f"privado/{archivo_id}",
				valido=True,
			)
		)
		fecha_vencimiento = (
			_hoy() + dt.timedelta(days=dias_vencimiento)
			if dias_vencimiento is not None
			else None
		)
		documento = DocumentoProveedor(
			proveedor_id=proveedor_id,
			archivo_id=archivo_id,
			tipo_documento=tipo,
			fecha_vencimiento=fecha_vencimiento,
			estado=estado,
			creado_en=dt.datetime.now(ZONA),
			reemplaza_documento_id=reemplaza_id,
		)
		db.add(documento)
		db.commit()
		db.refresh(documento)
		return documento.id


def _subir_documento(
	contexto,
	usuario_id: int,
	proveedor_id: int,
	tipo: str = "SOAT",
	fecha: dt.date | None = None,
	reemplaza_id: int | None = None,
):
	with contexto["db"]() as db:
		archivo_id = f"file_{uuid.uuid4().hex}"
		db.add(
			ArchivoPrivado(
				archivo_id=archivo_id,
				proveedor_id=proveedor_id,
				clave_almacenamiento=f"privado/{archivo_id}",
				valido=True,
			)
		)
		db.commit()
	body = {
		"tipoDocumento": tipo,
		"archivoId": archivo_id,
		"fechaVencimiento": (fecha or (_hoy() + dt.timedelta(days=60))).isoformat(),
	}
	if reemplaza_id is not None:
		body["reemplazaDocumentoId"] = f"doc_{reemplaza_id:03d}"
	return contexto["client"].post(
		DOCUMENTOS,
		json=body,
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)


def test_consulta_documentos_devuelve_todos_los_documentos_del_proveedor(
	vigencia_context,
):
	usuario_id, proveedor_id = _crear_proveedor(vigencia_context)
	documento_anterior = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "REEMPLAZADO", -20
	)
	documento_actual = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "PENDIENTE_REVISION"
	)
	otro_usuario, otro_proveedor = _crear_proveedor(vigencia_context)
	_crear_documento(
		vigencia_context, otro_proveedor, "SOAT", "APROBADO"
	)

	respuesta = vigencia_context["client"].get(
		MIS_DOCUMENTOS, headers=_headers(usuario_id, ["PROVEEDOR"])
	)

	assert respuesta.status_code == 200
	datos = respuesta.json()["datos"]
	assert datos["estadoHabilitacion"] == "HABILITADO"
	assert datos["motivo"] is None
	assert {
		documento["documentoId"] for documento in datos["documentos"]
	} == {f"doc_{documento_anterior:03d}", f"doc_{documento_actual:03d}"}
	assert f"usr_{otro_usuario:03d}" not in respuesta.text


def test_renovacion_valida_conserva_documento_anterior(vigencia_context):
	usuario_id, proveedor_id = _crear_proveedor(vigencia_context)
	documento_anterior = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "APROBADO", 5
	)

	respuesta = _subir_documento(
		vigencia_context,
		usuario_id,
		proveedor_id,
		reemplaza_id=documento_anterior,
	)

	assert respuesta.status_code == 201
	assert respuesta.json()["datos"]["estado"] == "PENDIENTE_REVISION"
	with vigencia_context["db"]() as db:
		anterior = db.get(DocumentoProveedor, documento_anterior)
		assert anterior.estado == "APROBADO"
		assert db.query(DocumentoProveedor).filter_by(proveedor_id=proveedor_id).count() == 2


def test_fecha_vencida_rechaza_renovacion_sin_registro(vigencia_context):
	usuario_id, proveedor_id = _crear_proveedor(vigencia_context)
	_crear_documento(vigencia_context, proveedor_id, "SOAT", "APROBADO")
	ayer = _hoy() - dt.timedelta(days=1)

	respuesta = _subir_documento(
		vigencia_context, usuario_id, proveedor_id, fecha=ayer
	)

	assert respuesta.status_code == 422
	assert respuesta.json()["datos"]["errores"][0]["codigo"] == "DOCUMENTO_VENCIDO"
	with vigencia_context["db"]() as db:
		assert db.query(DocumentoProveedor).filter_by(proveedor_id=proveedor_id).count() == 1


def test_renovacion_de_documento_ajeno_devuelve_404_sin_cambios(vigencia_context):
	usuario_id, proveedor_id = _crear_proveedor(vigencia_context)
	_, otro_proveedor_id = _crear_proveedor(vigencia_context)
	documento_ajeno = _crear_documento(
		vigencia_context, otro_proveedor_id, "SOAT", "APROBADO"
	)
	total_antes = _conteo_documentos(vigencia_context)

	respuesta = _subir_documento(
		vigencia_context,
		usuario_id,
		proveedor_id,
		reemplaza_id=documento_ajeno,
	)

	assert respuesta.status_code == 404
	assert respuesta.json()["mensaje"] == "Recurso no encontrado"
	assert _conteo_documentos(vigencia_context) == total_antes


def _conteo_documentos(contexto) -> int:
	with contexto["db"]() as db:
		return db.query(DocumentoProveedor).count()


def test_consulta_documentos_sin_autenticacion(vigencia_context):
	respuesta = vigencia_context["client"].get(MIS_DOCUMENTOS)

	assert respuesta.status_code == 401
	assert respuesta.json()["datos"] is None


def test_consulta_documentos_sin_rol_proveedor(vigencia_context):
	usuario_id = _crear_usuario(vigencia_context, "CLIENTE")

	respuesta = vigencia_context["client"].get(
		MIS_DOCUMENTOS, headers=_headers(usuario_id, ["CLIENTE"])
	)

	assert respuesta.status_code == 403
	assert respuesta.json()["datos"] is None


def test_proveedor_con_documento_vencido_consulta_estado_y_motivo(
	vigencia_context,
):
	usuario_id, proveedor_id = _crear_proveedor(
		vigencia_context,
		estado_habilitacion="SUSPENDIDO",
		estado_operativo="NO_DISPONIBLE",
		motivo="Documento obligatorio vencido: SOAT",
	)
	_crear_documento(vigencia_context, proveedor_id, "SOAT", "VENCIDO", -1)

	respuesta = vigencia_context["client"].get(
		MIS_DOCUMENTOS, headers=_headers(usuario_id, ["PROVEEDOR"])
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["habilitado"] is False
	assert respuesta.json()["datos"]["estadoHabilitacion"] == "SUSPENDIDO"
	assert respuesta.json()["datos"]["motivo"] == "Documento obligatorio vencido: SOAT"


def test_proceso_vencimiento_suspende_y_marca_no_disponible(vigencia_context):
	usuario_id, proveedor_id = _crear_proveedor(
		vigencia_context,
		estado_habilitacion="HABILITADO",
		estado_operativo="DISPONIBLE",
	)
	_crear_documento(vigencia_context, proveedor_id, "SOAT", "APROBADO", -1)
	_crear_documento(
		vigencia_context, proveedor_id, "IDENTIFICACION", "APROBADO", 30
	)

	with vigencia_context["db"]() as db:
		resultado = procesar_vencimientos(db)
		proveedor = db.get(Proveedor, proveedor_id)
		documento = (
			db.query(DocumentoProveedor)
			.filter_by(proveedor_id=proveedor_id, tipo_documento="SOAT")
			.one()
		)

	assert resultado == {
		"documentosVencidos": 1,
		"proveedoresSuspendidos": 1,
		"auditoriasRegistradas": 1,
	}
	assert documento.estado == "VENCIDO"
	assert proveedor.estado_habilitacion == "SUSPENDIDO"
	assert proveedor.estado_operativo == "NO_DISPONIBLE"
	assert proveedor.motivo_habilitacion == "Documento obligatorio vencido: SOAT"


def test_proceso_vencimiento_es_idempotente_y_no_duplica_auditoria(
	vigencia_context,
):
	_, proveedor_id = _crear_proveedor(vigencia_context)
	documento_id = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "APROBADO", -1
	)

	with vigencia_context["db"]() as db:
		primera = procesar_vencimientos(db)
		segunda = procesar_vencimientos(db)
		auditorias = (
			db.query(AuditoriaDocumento)
			.filter_by(
				proveedor_id=proveedor_id,
				documento_id=documento_id,
				evento=EVENTO_DOCUMENTO_VENCIDO,
			)
			.count()
		)

	assert primera["auditoriasRegistradas"] == 1
	assert segunda == {
		"documentosVencidos": 0,
		"proveedoresSuspendidos": 0,
		"auditoriasRegistradas": 0,
	}
	assert auditorias == 1


def test_renovacion_aprobada_reemplaza_anterior_y_no_reactiva_proveedor(
	vigencia_context,
):
	usuario_id, proveedor_id = _crear_proveedor(
		vigencia_context,
		estado_habilitacion="SUSPENDIDO",
		estado_operativo="NO_DISPONIBLE",
		motivo="Documento obligatorio vencido: SOAT",
	)
	anterior_id = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "VENCIDO", -1
	)
	_crear_documento(
		vigencia_context, proveedor_id, "IDENTIFICACION", "APROBADO", 30
	)
	renovacion_id = _crear_documento(
		vigencia_context,
		proveedor_id,
		"SOAT",
		"PENDIENTE_REVISION",
		60,
		reemplaza_id=anterior_id,
	)
	revisor_id = _crear_usuario(vigencia_context, "REVISOR")

	respuesta = vigencia_context["client"].patch(
		f"{BACKOFFICE_DOCUMENTOS}/prov_{proveedor_id:03d}/documentos/"
		f"doc_{renovacion_id:03d}",
		json={"decision": "APROBADO"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["estadoHabilitacion"] == "HABILITADO"
	with vigencia_context["db"]() as db:
		proveedor = db.get(Proveedor, proveedor_id)
		anterior = db.get(DocumentoProveedor, anterior_id)
		renovacion = db.get(DocumentoProveedor, renovacion_id)
		assert proveedor.estado_operativo == "NO_DISPONIBLE"
		assert proveedor.motivo_habilitacion is None
		assert anterior.estado == "REEMPLAZADO"
		assert renovacion.estado == "APROBADO"
	assert usuario_id > 0


def test_historial_incluye_documentos_reemplazados(vigencia_context):
	usuario_id, proveedor_id = _crear_proveedor(vigencia_context)
	anterior_id = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "REEMPLAZADO", -1
	)
	actual_id = _crear_documento(
		vigencia_context,
		proveedor_id,
		"SOAT",
		"APROBADO",
		60,
		reemplaza_id=anterior_id,
	)

	respuesta = vigencia_context["client"].get(
		MIS_DOCUMENTOS, headers=_headers(usuario_id, ["PROVEEDOR"])
	)

	assert respuesta.status_code == 200
	documentos = respuesta.json()["datos"]["documentos"]
	assert {documento["documentoId"] for documento in documentos} == {
		f"doc_{anterior_id:03d}",
		f"doc_{actual_id:03d}",
	}
	assert next(
		documento["estado"]
		for documento in documentos
		if documento["documentoId"] == f"doc_{anterior_id:03d}"
	) == "REEMPLAZADO"


@pytest.mark.parametrize("rol", ["REVISOR", "ADMINISTRADOR"])
def test_backoffice_consulta_documentos_para_roles_autorizados(
	vigencia_context, rol
):
	_, proveedor_id = _crear_proveedor(vigencia_context)
	documento_id = _crear_documento(
		vigencia_context, proveedor_id, "SOAT", "PENDIENTE_REVISION"
	)
	revisor_id = _crear_usuario(vigencia_context, rol)

	respuesta = vigencia_context["client"].get(
		f"{BACKOFFICE_DOCUMENTOS}/prov_{proveedor_id:03d}/documentos",
		headers=_headers(revisor_id, [rol]),
	)

	assert respuesta.status_code == 200
	datos = respuesta.json()["datos"]
	assert datos["proveedorId"] == f"prov_{proveedor_id:03d}"
	assert datos["documentos"][0]["documentoId"] == f"doc_{documento_id:03d}"


def test_backoffice_rechaza_rol_sin_permiso(vigencia_context):
	_, proveedor_id = _crear_proveedor(vigencia_context)
	cliente_id = _crear_usuario(vigencia_context, "CLIENTE")

	respuesta = vigencia_context["client"].get(
		f"{BACKOFFICE_DOCUMENTOS}/prov_{proveedor_id:03d}/documentos",
		headers=_headers(cliente_id, ["CLIENTE"]),
	)

	assert respuesta.status_code == 403


def test_migracion_hu16_agrega_columnas_aditivamente_e_idempotente():
	engine = create_engine("sqlite://")
	try:
		with engine.begin() as conexion:
			conexion.execute(
				text(
					"CREATE TABLE proveedores ("
					"id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL)"
				)
			)
			conexion.execute(
				text("INSERT INTO proveedores (id, usuario_id) VALUES (1, 23)")
			)

		agregadas = migrar_columnas_hu16(engine)
		segunda = migrar_columnas_hu16(engine)
		with engine.connect() as conexion:
			fila = conexion.execute(
				text("SELECT * FROM proveedores WHERE id=1")
			).mappings().one()

		assert agregadas == ["estado_operativo", "motivo_habilitacion"]
		assert segunda == []
		assert fila["usuario_id"] == 23
		assert fila["estado_operativo"] == "NO_DISPONIBLE"
		assert fila["motivo_habilitacion"] is None
	finally:
		engine.dispose()


def test_migracion_hu16_falla_si_no_existe_tabla_proveedores():
	engine = create_engine("sqlite://")
	try:
		with pytest.raises(RuntimeError, match="No existe la tabla proveedores"):
			migrar_columnas_hu16(engine)
	finally:
		engine.dispose()
