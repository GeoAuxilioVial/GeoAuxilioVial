import datetime as dt
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
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
	ProveedorZonaCobertura,
)
from app.domain.usuario_domain import Usuario
from app.services.documentos_requeridos_service import sembrar_documentos_base
from main import app
from migrate_hu17_provider_columns import migrar_columnas_hu17

URL_PROVEEDORES = "/api/v1/proveedores"
URL_DOCUMENTOS = f"{URL_PROVEEDORES}/documentos"
URL_REVISION = "/api/v1/backoffice/proveedores"


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


def _fecha_futura(dias: int = 30) -> str:
	return (dt.datetime.now(ZONA).date() + dt.timedelta(days=dias)).isoformat()


def _codigo_error(respuesta) -> str:
	return respuesta.json()["datos"]["errores"][0]["codigo"]


def _crear_usuario(test_db, roles: str = "CLIENTE") -> int:
	with test_db() as db:
		usuario = Usuario(
			nombre="Usuario HU14",
			correo=f"hu14.{uuid.uuid4().hex}@example.com",
			password_hash="hash-no-utilizado",
			roles=roles,
		)
		db.add(usuario)
		db.commit()
		db.refresh(usuario)
		return usuario.id


def _crear_zona(client: TestClient, activa: bool = True) -> str:
	respuesta = client.post(
		"/api/v1/parametros/zonas-cobertura",
		json={
			"nombre": f"Zona-{uuid.uuid4().hex[:8]}",
			"latitudCentro": 7.1193,
			"longitudCentro": -73.1227,
			"radioKm": 10,
			"activa": activa,
		},
		headers=_headers(999, ["ADMINISTRADOR"]),
	)
	assert respuesta.status_code == 201
	return respuesta.json()["datos"]["zonaId"]


def _registrar_proveedor(
	client: TestClient,
	test_db,
	usuario_id: int,
	zona_id: str | None = None,
	nombre: str = "Grúas HU14",
):
	zona_id = zona_id or _crear_zona(client)
	return client.post(
		URL_PROVEEDORES,
		json={
			"nombreComercial": nombre,
			"tipoProveedor": "GRUA",
			"zonasCobertura": [zona_id],
		},
		headers=_headers(usuario_id, ["CLIENTE"]),
	)


def _registrar_archivo(
	test_db,
	usuario_id: int,
	archivo_id: str = "file_123",
	valido: bool = True,
):
	with test_db() as db:
		db.add(
			ArchivoPrivado(
				archivo_id=archivo_id,
				usuario_id=usuario_id,
				clave_almacenamiento=f"privado/{archivo_id}",
				valido=valido,
			)
		)
		db.commit()


def _cargar_documento(
	client: TestClient,
	test_db,
	usuario_id: int,
	archivo_id: str = "file_123",
	tipo: str = "IDENTIFICACION",
	fecha: str | None = None,
	reemplaza: str | None = None,
):
	_registrar_archivo(test_db, usuario_id, archivo_id)
	datos = {"tipoDocumento": tipo, "archivoId": archivo_id}
	if fecha is not None:
		datos["fechaVencimiento"] = fecha
	else:
		datos["fechaVencimiento"] = _fecha_futura()
	if reemplaza is not None:
		datos["reemplazaDocumentoId"] = reemplaza
	return client.post(
		URL_DOCUMENTOS,
		json=datos,
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)


def _ruta_revision(proveedor_id: str, documento_id: str) -> str:
	return f"{URL_REVISION}/{proveedor_id}/documentos/{documento_id}"


@pytest.fixture
def test_db():
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
		yield factory
	finally:
		app.dependency_overrides.pop(get_db, None)
		Base.metadata.drop_all(bind=engine)
		engine.dispose()


@pytest.fixture
def client(test_db):
	with TestClient(app, raise_server_exceptions=False) as test_client:
		yield test_client


def test_registro_proveedor_valido_y_agrega_rol(client, test_db):
	usuario_id = _crear_usuario(test_db)
	zona_id = _crear_zona(client)

	respuesta = _registrar_proveedor(client, test_db, usuario_id, zona_id)

	assert respuesta.status_code == 201
	datos = respuesta.json()["datos"]
	assert datos["estadoHabilitacion"] == "PENDIENTE"
	assert datos["zonasCobertura"] == [zona_id]
	assert datos["documentosRequeridos"]
	assert "token" not in respuesta.json()["datos"]
	with test_db() as db:
		usuario = db.get(Usuario, usuario_id)
		proveedor = db.query(Proveedor).filter_by(usuario_id=usuario_id).one()
		assert "PROVEEDOR" in usuario.lista_roles()
		assert db.get(DatosProveedor, proveedor.id).nombre_comercial == "Grúas HU14"
		assert db.query(ProveedorZonaCobertura).filter_by(proveedor_id=proveedor.id).count() == 1


def test_proveedor_ya_registrado_no_crea_segundo_perfil(client, test_db):
	usuario_id = _crear_usuario(test_db)
	_registrar_proveedor(client, test_db, usuario_id)

	respuesta = _registrar_proveedor(client, test_db, usuario_id)

	assert respuesta.status_code == 409
	assert respuesta.json()["datos"] == {"codigo": "PROVEEDOR_YA_REGISTRADO"}
	with test_db() as db:
		assert db.query(Proveedor).filter_by(usuario_id=usuario_id).count() == 1


def test_tipo_proveedor_inexistente(client, test_db):
	usuario_id = _crear_usuario(test_db)
	zona_id = _crear_zona(client)

	respuesta = client.post(
		URL_PROVEEDORES,
		json={
			"nombreComercial": "Servicio inválido",
			"tipoProveedor": "AVION",
			"zonasCobertura": [zona_id],
		},
		headers=_headers(usuario_id, ["CLIENTE"]),
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "VALOR_FUERA_DE_CATALOGO"
	with test_db() as db:
		assert db.query(Proveedor).count() == 0


@pytest.mark.parametrize("zona_tipo", ["inexistente", "inactiva"])
def test_zona_inexistente_o_inactiva_no_registra_proveedor(
	client, test_db, zona_tipo
):
	usuario_id = _crear_usuario(test_db)
	zona_id = (
		"zon_999"
		if zona_tipo == "inexistente"
		else _crear_zona(client, activa=False)
	)

	respuesta = _registrar_proveedor(client, test_db, usuario_id, zona_id)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "VALOR_FUERA_DE_CATALOGO"
	with test_db() as db:
		assert db.query(Proveedor).count() == 0


def test_registro_proveedor_sin_token(client, test_db):
	respuesta = client.post(
		URL_PROVEEDORES,
		json={
			"nombreComercial": "Grúas HU14",
			"tipoProveedor": "GRUA",
			"zonasCobertura": ["zon_01"],
		},
	)

	assert respuesta.status_code == 401
	with test_db() as db:
		assert db.query(Proveedor).count() == 0


def test_carga_valida_pendiente_revision(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]

	respuesta = _cargar_documento(client, test_db, usuario_id)

	assert respuesta.status_code == 201
	assert respuesta.json()["datos"]["estado"] == "PENDIENTE_REVISION"
	assert respuesta.json()["datos"]["tipoDocumento"] == "IDENTIFICACION"
	assert "archivoId" not in respuesta.text
	assert "clave_almacenamiento" not in respuesta.text
	with test_db() as db:
		documento = db.query(DocumentoProveedor).one()
		assert documento.proveedor_id == int(proveedor["proveedorId"].removeprefix("prov_"))


def test_documento_vencido_no_se_registra(client, test_db):
	usuario_id = _crear_usuario(test_db)
	_registrar_proveedor(client, test_db, usuario_id)
	fecha_vencida = (dt.datetime.now(ZONA).date() - dt.timedelta(days=1)).isoformat()

	respuesta = _cargar_documento(
		client, test_db, usuario_id, fecha=fecha_vencida
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "DOCUMENTO_VENCIDO"
	with test_db() as db:
		assert db.query(DocumentoProveedor).count() == 0


def test_fecha_vencimiento_obligatoria_si_documento_la_exige(client, test_db):
	usuario_id = _crear_usuario(test_db)
	_registrar_proveedor(client, test_db, usuario_id)
	_registrar_archivo(test_db, usuario_id)

	respuesta = client.post(
		URL_DOCUMENTOS,
		json={"tipoDocumento": "IDENTIFICACION", "archivoId": "file_123"},
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "CAMPO_OBLIGATORIO"


def test_tipo_documento_no_requerido(client, test_db):
	usuario_id = _crear_usuario(test_db)
	_registrar_proveedor(client, test_db, usuario_id)

	respuesta = _cargar_documento(
		client, test_db, usuario_id, tipo="LICENCIA_CONDUCCION"
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "VALOR_FUERA_DE_CATALOGO"
	with test_db() as db:
		assert db.query(DocumentoProveedor).count() == 0


def test_carga_sin_rol_proveedor_no_registra_documento(client, test_db):
	usuario_id = _crear_usuario(test_db)
	_registrar_proveedor(client, test_db, usuario_id)
	_registrar_archivo(test_db, usuario_id)

	respuesta = client.post(
		URL_DOCUMENTOS,
		json={
			"tipoDocumento": "IDENTIFICACION",
			"archivoId": "file_123",
			"fechaVencimiento": _fecha_futura(),
		},
		headers=_headers(usuario_id, ["CLIENTE"]),
	)

	assert respuesta.status_code == 403
	with test_db() as db:
		assert db.query(DocumentoProveedor).count() == 0


@pytest.mark.parametrize(
	"archivo_id,registrado,propietario,valido",
	[
		("file_404", False, True, True),
		("file_123", True, False, True),
		("file_123", True, True, False),
		("https://publico/archivo", True, True, True),
	],
	ids=["inexistente", "ajeno", "invalido", "formato-invalido"],
)
def test_archivo_inexistente_ajeno_o_invalido_se_rechaza(
	client, test_db, archivo_id, registrado, propietario, valido
):
	usuario_id = _crear_usuario(test_db)
	_registrar_proveedor(client, test_db, usuario_id)
	if registrado:
		owner_id = usuario_id if propietario else _crear_usuario(test_db)
		_registrar_archivo(test_db, owner_id, archivo_id, valido=valido)

	respuesta = client.post(
		URL_DOCUMENTOS,
		json={
			"tipoDocumento": "IDENTIFICACION",
			"archivoId": archivo_id,
			"fechaVencimiento": _fecha_futura(),
		},
		headers=_headers(usuario_id, ["PROVEEDOR"]),
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "ARCHIVO_INVALIDO"
	with test_db() as db:
		assert db.query(DocumentoProveedor).count() == 0


def test_revision_por_revisor_persiste_auditoria(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	documento = _cargar_documento(client, test_db, usuario_id).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")

	respuesta = client.patch(
		_ruta_revision(proveedor["proveedorId"], documento["documentoId"]),
		json={"decision": "APROBADO", "motivo": "Documento legible"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["estado"] == "APROBADO"
	assert respuesta.json()["datos"]["estadoHabilitacion"] == "PENDIENTE"
	with test_db() as db:
		guardado = db.query(DocumentoProveedor).one()
		assert guardado.revisor_usuario_id == revisor_id
		assert guardado.revisado_en is not None
		assert guardado.motivo == "Documento legible"


def test_rechazo_sin_motivo_no_cambia_estado(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	documento = _cargar_documento(client, test_db, usuario_id).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")

	respuesta = client.patch(
		_ruta_revision(proveedor["proveedorId"], documento["documentoId"]),
		json={"decision": "RECHAZADO"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "MOTIVO_OBLIGATORIO"
	with test_db() as db:
		assert db.query(DocumentoProveedor).one().estado == "PENDIENTE_REVISION"


def test_decision_fuera_de_catalogo_no_cambia_estado(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	documento = _cargar_documento(client, test_db, usuario_id).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")

	respuesta = client.patch(
		_ruta_revision(proveedor["proveedorId"], documento["documentoId"]),
		json={"decision": "TAL_VEZ"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert respuesta.status_code == 422
	assert _codigo_error(respuesta) == "VALOR_FUERA_DE_CATALOGO"
	with test_db() as db:
		assert db.query(DocumentoProveedor).one().estado == "PENDIENTE_REVISION"


def test_documento_ya_revisado_no_admite_otra_decision(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	documento = _cargar_documento(client, test_db, usuario_id).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")
	url = _ruta_revision(proveedor["proveedorId"], documento["documentoId"])
	primera = client.patch(
		url,
		json={"decision": "APROBADO"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)
	segunda = client.patch(
		url,
		json={"decision": "RECHAZADO", "motivo": "Cambio tardío"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert primera.status_code == 200
	assert segunda.status_code == 409
	assert segunda.json()["datos"] == {"codigo": "DOCUMENTO_YA_REVISADO"}
	with test_db() as db:
		assert db.query(DocumentoProveedor).one().estado == "APROBADO"


def test_sin_rol_revisor_no_modifica_documento(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	documento = _cargar_documento(client, test_db, usuario_id).json()["datos"]
	cliente_id = _crear_usuario(test_db)

	respuesta = client.patch(
		_ruta_revision(proveedor["proveedorId"], documento["documentoId"]),
		json={"decision": "APROBADO"},
		headers=_headers(cliente_id, ["CLIENTE"]),
	)

	assert respuesta.status_code == 403
	with test_db() as db:
		assert db.query(DocumentoProveedor).one().estado == "PENDIENTE_REVISION"


def test_habilitacion_incompleta_permanece_pendiente(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	identificacion = _cargar_documento(
		client, test_db, usuario_id, archivo_id="file_identificacion"
	).json()["datos"]
	_cargar_documento(
		client,
		test_db,
		usuario_id,
		archivo_id="file_soat",
		tipo="SOAT",
	)
	revisor_id = _crear_usuario(test_db, roles="REVISOR")

	respuesta = client.patch(
		_ruta_revision(proveedor["proveedorId"], identificacion["documentoId"]),
		json={"decision": "APROBADO"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["proveedorHabilitado"] is False
	assert respuesta.json()["datos"]["estadoHabilitacion"] == "PENDIENTE"


def test_habilitacion_completa_al_aprobar_ultimo_documento(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	identificacion = _cargar_documento(
		client, test_db, usuario_id, archivo_id="file_identificacion"
	).json()["datos"]
	soat = _cargar_documento(
		client,
		test_db,
		usuario_id,
		archivo_id="file_soat",
		tipo="SOAT",
	).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")
	headers = _headers(revisor_id, ["REVISOR"])

	primera = client.patch(
		_ruta_revision(proveedor["proveedorId"], identificacion["documentoId"]),
		json={"decision": "APROBADO"},
		headers=headers,
	)
	ultima = client.patch(
		_ruta_revision(proveedor["proveedorId"], soat["documentoId"]),
		json={"decision": "APROBADO"},
		headers=headers,
	)

	assert primera.status_code == 200
	assert primera.json()["datos"]["proveedorHabilitado"] is False
	assert ultima.status_code == 200
	assert ultima.json()["datos"]["proveedorHabilitado"] is True
	assert ultima.json()["datos"]["estadoHabilitacion"] == "HABILITADO"
	with test_db() as db:
		proveedor_db = db.query(Proveedor).one()
		assert proveedor_db.estado_habilitacion == "HABILITADO"


def test_aprobar_renovacion_reemplaza_documento_anterior(client, test_db):
	usuario_id = _crear_usuario(test_db)
	proveedor = _registrar_proveedor(client, test_db, usuario_id).json()["datos"]
	anterior = _cargar_documento(
		client, test_db, usuario_id, archivo_id="file_anterior"
	).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")
	headers = _headers(revisor_id, ["REVISOR"])
	client.patch(
		_ruta_revision(proveedor["proveedorId"], anterior["documentoId"]),
		json={"decision": "APROBADO"},
		headers=headers,
	)
	renovacion = _cargar_documento(
		client,
		test_db,
		usuario_id,
		archivo_id="file_renovacion",
		reemplaza=anterior["documentoId"],
	).json()["datos"]

	respuesta = client.patch(
		_ruta_revision(proveedor["proveedorId"], renovacion["documentoId"]),
		json={"decision": "APROBADO"},
		headers=headers,
	)

	assert respuesta.status_code == 200
	with test_db() as db:
		documentos = db.query(DocumentoProveedor).order_by(DocumentoProveedor.id).all()
		assert [documento.estado for documento in documentos] == [
			"REEMPLAZADO",
			"APROBADO",
		]


def test_documento_inexistente_devuelve_404(client, test_db):
	revisor_id = _crear_usuario(test_db, roles="REVISOR")

	respuesta = client.patch(
		_ruta_revision("prov_123", "doc_999"),
		json={"decision": "APROBADO"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert respuesta.status_code == 404
	assert respuesta.json()["mensaje"] == "Recurso no encontrado"


def test_documento_de_otro_proveedor_devuelve_404_sin_modificarlo(client, test_db):
	primer_usuario = _crear_usuario(test_db)
	primer_proveedor = _registrar_proveedor(
		client, test_db, primer_usuario
	).json()["datos"]
	documento = _cargar_documento(
		client, test_db, primer_usuario
	).json()["datos"]
	segundo_usuario = _crear_usuario(test_db)
	segundo_proveedor = _registrar_proveedor(
		client, test_db, segundo_usuario
	).json()["datos"]
	revisor_id = _crear_usuario(test_db, roles="REVISOR")

	respuesta = client.patch(
		_ruta_revision(
			segundo_proveedor["proveedorId"], documento["documentoId"]
		),
		json={"decision": "APROBADO"},
		headers=_headers(revisor_id, ["REVISOR"]),
	)

	assert primer_proveedor["proveedorId"] != segundo_proveedor["proveedorId"]
	assert respuesta.status_code == 404
	assert respuesta.json()["mensaje"] == "Recurso no encontrado"
	with test_db() as db:
		assert db.query(DocumentoProveedor).one().estado == "PENDIENTE_REVISION"


def test_zona_con_proveedor_no_se_puede_eliminar(client, test_db):
	usuario_id = _crear_usuario(test_db)
	zona_id = _crear_zona(client)
	_registrar_proveedor(client, test_db, usuario_id, zona_id)

	respuesta = client.delete(
		f"/api/v1/parametros/zonas-cobertura/{zona_id}",
		headers=_headers(999, ["ADMINISTRADOR"]),
	)

	assert respuesta.status_code == 409
	assert respuesta.json()["datos"] == {"codigo": "ZONA_CON_DEPENDENCIAS"}


def test_migracion_hu17_agrega_solo_columnas_faltantes_y_es_idempotente():
	engine = create_engine("sqlite://")
	try:
		with engine.begin() as conexion:
			conexion.execute(
				text(
					"CREATE TABLE proveedores ("
					"id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, "
					"latitud FLOAT, estado_habilitacion VARCHAR(30))"
				)
			)
			conexion.execute(
				text(
					"INSERT INTO proveedores (id, usuario_id, latitud, estado_habilitacion) "
					"VALUES (1, 42, 7.1, 'HABILITADO')"
				)
			)

		agregadas = migrar_columnas_hu17(engine)

		assert set(agregadas) == {
			"longitud",
			"precision_metros",
			"actualizada_en",
		}
		columnas = {
			columna["name"] for columna in inspect(engine).get_columns("proveedores")
		}
		assert set(migrar_columnas_hu17(engine)) == set()
		with engine.connect() as conexion:
			fila = conexion.execute(
				text(
					"SELECT usuario_id, latitud, estado_habilitacion "
					"FROM proveedores WHERE id = 1"
				)
			).one()
		assert fila == (42, 7.1, "HABILITADO")
		assert {
			"estado_habilitacion",
			"latitud",
			"longitud",
			"precision_metros",
			"actualizada_en",
		}.issubset(columnas)
	finally:
		engine.dispose()


def test_migracion_hu17_falla_explicita_si_no_existe_tabla():
	engine = create_engine("sqlite://")
	try:
		with pytest.raises(RuntimeError, match="No existe la tabla proveedores"):
			migrar_columnas_hu17(engine)
	finally:
		engine.dispose()
