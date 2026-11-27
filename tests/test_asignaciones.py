import datetime as dt
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.errors import ZONA
from app.domain.auxilio_domain import (
	AsignacionAuxilio,
	AuditoriaAsignacion,
	SolicitudAuxilio,
)
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import DatosProveedor, ProveedorZonaCobertura
from app.domain.zonas_cobertura_domain import ZonaCobertura
from app.services.asignacion_service import (
	asignar_proveedor_mas_cercano,
	expirar_asignaciones_vencidas,
)
from main import app

ASIGNACIONES = "/api/v1/auxilio/asignaciones"
LATITUD = 7.1193
LONGITUD = -73.1227


def _token(usuario_id: int, roles: list[str]) -> str:
	return jwt.encode(
		{
			"sub": f"usr_{usuario_id}",
			"roles": roles,
			"rol": roles[0],
			"exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
		},
		settings.secret_key,
		algorithm="HS256",
	)


def _headers(usuario_id: int, roles: list[str] | None = None) -> dict[str, str]:
	return {
		"Authorization": f"Bearer {_token(usuario_id, roles or ['PROVEEDOR'])}"
	}


@pytest.fixture
def asignacion_context():
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	Base.metadata.create_all(bind=engine)
	factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

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
	latitud: float = LATITUD,
	longitud: float = LONGITUD,
) -> tuple[int, int]:
	usuario_id = uuid.uuid4().int % 2_000_000_000
	with contexto["db"]() as db:
		zona = ZonaCobertura(
			nombre=f"Zona-HU20-{uuid.uuid4().hex}",
			latitud_centro=LATITUD,
			longitud_centro=LONGITUD,
			radio_km=20,
			activa=True,
		)
		db.add(zona)
		db.flush()
		proveedor = Proveedor(
			usuario_id=usuario_id,
			estado_habilitacion="HABILITADO",
			estado_operativo="DISPONIBLE",
			latitud=latitud,
			longitud=longitud,
			actualizada_en=dt.datetime.now(ZONA),
		)
		db.add(proveedor)
		db.flush()
		proveedor_id = proveedor.id
		db.add(
			DatosProveedor(
				proveedor_id=proveedor.id,
				nombre_comercial=f"Proveedor-HU20-{proveedor.id}",
				tipo_proveedor="GRUA",
			)
		)
		db.add(
			ProveedorZonaCobertura(
				proveedor_id=proveedor.id,
				zona_id=zona.id,
			)
		)
		db.commit()
		return proveedor.id, usuario_id


def _crear_solicitud(contexto, estado: str = "BUSCANDO_PROVEEDOR") -> int:
	with contexto["db"]() as db:
		solicitud = SolicitudAuxilio(
			cliente_id="usr_900",
			tipo_servicio="GRUA",
			latitud=LATITUD,
			longitud=LONGITUD,
			estado=estado,
			version=1,
		)
		db.add(solicitud)
		db.commit()
		db.refresh(solicitud)
		return solicitud.id


def _crear_asignacion(
	contexto,
	proveedor_id: int,
	estado: str = "PENDIENTE",
	segundos_hasta_expirar: int = 60,
) -> tuple[int, int]:
	solicitud_estado = (
		"ASIGNADA" if estado == "PENDIENTE" else "BUSCANDO_PROVEEDOR"
	)
	with contexto["db"]() as db:
		solicitud = SolicitudAuxilio(
			cliente_id="usr_900",
			tipo_servicio="GRUA",
			latitud=LATITUD,
			longitud=LONGITUD,
			estado=solicitud_estado,
			version=1,
		)
		db.add(solicitud)
		db.flush()
		ahora = dt.datetime.now(ZONA)
		asignacion = AsignacionAuxilio(
			solicitud_id=solicitud.id,
			proveedor_id=proveedor_id,
			estado=estado,
			creada_en=ahora - dt.timedelta(seconds=60),
			expira_en=ahora + dt.timedelta(seconds=segundos_hasta_expirar),
			version=1,
		)
		db.add(asignacion)
		db.commit()
		db.refresh(asignacion)
		return asignacion.id, solicitud.id


def _respuesta(contexto, asignacion_id: int, usuario_id: int, body: dict):
	return contexto["client"].post(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}/respuesta",
		json=body,
		headers=_headers(usuario_id),
	)


def _codigo_409(respuesta) -> str:
	assert set(respuesta.json()["datos"]) == {"codigo"}
	return respuesta.json()["datos"]["codigo"]


def _codigo_422(respuesta) -> str:
	return respuesta.json()["datos"]["errores"][0]["codigo"]


def _estado(contexto, modelo, registro_id: int):
	with contexto["db"]() as db:
		return db.get(modelo, registro_id).estado


def _conteo_auditoria(contexto, asignacion_id: int) -> int:
	with contexto["db"]() as db:
		return db.scalar(
			select(func.count(AuditoriaAsignacion.id)).where(
				AuditoriaAsignacion.asignacion_id == asignacion_id
			)
		)


def test_aceptacion_valida_actualiza_asignacion_solicitud_y_auditoria(
	asignacion_context,
):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context, proveedor_id, segundos_hasta_expirar=60
	)

	respuesta = _respuesta(
		asignacion_context, asignacion_id, usuario_id, {"decision": "ACEPTAR"}
	)

	assert respuesta.status_code == 200
	assert set(respuesta.json()) == {"exito", "mensaje", "datos", "fechaHora"}
	assert respuesta.json()["exito"] is True
	assert respuesta.json()["mensaje"] == "Respuesta de asignación registrada"
	assert respuesta.json()["datos"] == {
		"asignacionId": f"asg_{asignacion_id:03d}",
		"decision": "ACEPTAR",
		"estadoAsignacion": "ACEPTADA",
		"estadoSolicitud": "ACEPTADA",
	}
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "ACEPTADA"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ACEPTADA"
	assert _conteo_auditoria(asignacion_context, asignacion_id) == 1


def test_rechazo_vuelve_a_busqueda_y_excluye_al_proveedor_rechazado(
	asignacion_context,
):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	siguiente_proveedor, _ = _crear_proveedor(
		asignacion_context, latitud=LATITUD + 0.01
	)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context, proveedor_id, segundos_hasta_expirar=60
	)

	respuesta = _respuesta(
		asignacion_context,
		asignacion_id,
		usuario_id,
		{"decision": "RECHAZAR", "observacion": "No disponible"},
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["estadoAsignacion"] == "RECHAZADA"
	assert respuesta.json()["datos"]["estadoSolicitud"] == "BUSCANDO_PROVEEDOR"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "BUSCANDO_PROVEEDOR"
	assert _conteo_auditoria(asignacion_context, asignacion_id) == 1

	with asignacion_context["db"]() as db:
		siguiente = asignar_proveedor_mas_cercano(
			db, f"aux_{solicitud_id:03d}"
		)
		assert siguiente is not None
		assert siguiente.proveedor_id == siguiente_proveedor
		assert siguiente.proveedor_id != proveedor_id
		assert (
			siguiente.expira_en - siguiente.creada_en
		).total_seconds() == settings.asignacion_plazo_respuesta_segundos
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"


def test_proveedor_no_asignado_recibe_404_sin_cambios(asignacion_context):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	_, otro_usuario_id = _crear_proveedor(
		asignacion_context, latitud=LATITUD + 0.01
	)
	asignacion_id, solicitud_id = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = _respuesta(
		asignacion_context, asignacion_id, otro_usuario_id, {"decision": "ACEPTAR"}
	)

	assert respuesta.status_code == 404
	assert respuesta.json()["mensaje"] == "Recurso no encontrado"
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "PENDIENTE"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"
	assert _conteo_auditoria(asignacion_context, asignacion_id) == 0


def test_usuario_sin_rol_proveedor_recibe_403_sin_cambios(asignacion_context):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	_, cliente_id = _crear_proveedor(
		asignacion_context, latitud=LATITUD + 0.01
	)
	asignacion_id, solicitud_id = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = asignacion_context["client"].post(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}/respuesta",
		json={"decision": "ACEPTAR"},
		headers=_headers(cliente_id, ["CLIENTE"]),
	)

	assert respuesta.status_code == 403
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "PENDIENTE"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"


def test_asignacion_vencida_responde_409_y_registra_expiracion(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context,
		proveedor_id,
		segundos_hasta_expirar=-300,
	)

	respuesta = _respuesta(
		asignacion_context, asignacion_id, usuario_id, {"decision": "ACEPTAR"}
	)

	assert respuesta.status_code == 409
	assert _codigo_409(respuesta) == "ASIGNACION_EXPIRADA"
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "EXPIRADA"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "BUSCANDO_PROVEEDOR"
	assert _conteo_auditoria(asignacion_context, asignacion_id) == 1


def test_respuesta_duplicada_conserva_la_primera(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context, proveedor_id, segundos_hasta_expirar=60
	)
	primera = _respuesta(
		asignacion_context, asignacion_id, usuario_id, {"decision": "ACEPTAR"}
	)

	segunda = _respuesta(
		asignacion_context, asignacion_id, usuario_id, {"decision": "RECHAZAR"}
	)

	assert primera.status_code == 200
	assert segunda.status_code == 409
	assert _codigo_409(segunda) == "ASIGNACION_YA_RESPONDIDA"
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "ACEPTADA"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ACEPTADA"
	assert _conteo_auditoria(asignacion_context, asignacion_id) == 1


def test_dos_respuestas_concurrentes_solo_una_se_aplica(tmp_path):
	engine = create_engine(
		f"sqlite:///{tmp_path / 'respuestas.db'}",
		connect_args={"check_same_thread": False, "timeout": 10},
	)
	Base.metadata.create_all(bind=engine)
	factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
	with factory() as db:
		zona = ZonaCobertura(
			nombre=f"Zona-HU20-{uuid.uuid4().hex}",
			latitud_centro=LATITUD,
			longitud_centro=LONGITUD,
			radio_km=20,
			activa=True,
		)
		db.add(zona)
		proveedor = Proveedor(
			usuario_id=uuid.uuid4().int % 2_000_000_000,
			estado_habilitacion="HABILITADO",
			estado_operativo="DISPONIBLE",
			latitud=LATITUD,
			longitud=LONGITUD,
			actualizada_en=dt.datetime.now(ZONA),
		)
		db.add(proveedor)
		db.flush()
		proveedor_id = proveedor.id
		db.add(
			DatosProveedor(
				proveedor_id=proveedor.id,
				nombre_comercial="Proveedor concurrente",
				tipo_proveedor="GRUA",
			)
		)
		db.add(
			ProveedorZonaCobertura(
				proveedor_id=proveedor.id, zona_id=zona.id
			)
		)
		solicitud = SolicitudAuxilio(
			cliente_id="usr_900",
			tipo_servicio="GRUA",
			latitud=LATITUD,
			longitud=LONGITUD,
			estado="ASIGNADA",
			version=1,
		)
		db.add(solicitud)
		db.flush()
		asignacion = AsignacionAuxilio(
			solicitud_id=solicitud.id,
			proveedor_id=proveedor.id,
			estado="PENDIENTE",
			creada_en=dt.datetime.now(ZONA),
			expira_en=dt.datetime.now(ZONA) + dt.timedelta(seconds=60),
			version=1,
		)
		db.add(asignacion)
		db.flush()
		asignacion_id = asignacion.id
		usuario_id = proveedor.usuario_id
		db.commit()

	def override_get_db():
		yield from _yield_db(factory)

	app.dependency_overrides[get_db] = override_get_db
	barrier = Barrier(2)

	def responder(decision: str):
		with TestClient(app, raise_server_exceptions=False) as client:
			barrier.wait(timeout=5)
			return client.post(
				f"{ASIGNACIONES}/asg_{asignacion_id:03d}/respuesta",
				json={"decision": decision},
				headers=_headers(usuario_id),
			)

	try:
		with ThreadPoolExecutor(max_workers=2) as pool:
			respuestas = list(pool.map(responder, ["ACEPTAR", "RECHAZAR"]))
	finally:
		app.dependency_overrides.pop(get_db, None)

	assert sorted(respuesta.status_code for respuesta in respuestas) == [200, 409]
	error = next(respuesta for respuesta in respuestas if respuesta.status_code == 409)
	assert _codigo_409(error) == "ASIGNACION_YA_RESPONDIDA"
	with factory() as db:
		assert db.get(AsignacionAuxilio, asignacion_id).estado in {
			"ACEPTADA",
			"RECHAZADA",
		}
		assert db.scalar(
			select(func.count(AuditoriaAsignacion.id)).where(
				AuditoriaAsignacion.asignacion_id == asignacion_id
			)
		) == 1
	Base.metadata.drop_all(bind=engine)
	engine.dispose()


def _yield_db(factory):
	db = factory()
	try:
		yield db
	finally:
		db.close()


def test_decision_fuera_de_catalogo_no_registra_respuesta(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = _respuesta(
		asignacion_context, asignacion_id, usuario_id, {"decision": "QUIZAS"}
	)

	assert respuesta.status_code == 422
	assert _codigo_422(respuesta) == "VALOR_FUERA_DE_CATALOGO"
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "PENDIENTE"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"


def test_decision_ausente_no_registra_respuesta(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = _respuesta(
		asignacion_context, asignacion_id, usuario_id, {}
	)

	assert respuesta.status_code == 422
	assert _codigo_422(respuesta) == "CAMPO_OBLIGATORIO"
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "PENDIENTE"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"


def test_asignacion_inexistente_devuelve_404(asignacion_context):
	_, usuario_id = _crear_proveedor(asignacion_context)

	respuesta = _respuesta(
		asignacion_context, 999, usuario_id, {"decision": "ACEPTAR"}
	)

	assert respuesta.status_code == 404
	assert respuesta.json()["mensaje"] == "Recurso no encontrado"


def test_token_ausente_devuelve_401_sin_cambios(asignacion_context):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = asignacion_context["client"].post(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}/respuesta",
		json={"decision": "ACEPTAR"},
	)

	assert respuesta.status_code == 401
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "PENDIENTE"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"


def test_json_mal_formado_devuelve_400_sin_cambios(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = asignacion_context["client"].post(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}/respuesta",
		content=b'{"decision":',
		headers={
			**_headers(usuario_id),
			"Content-Type": "application/json",
		},
	)

	assert respuesta.status_code == 400
	assert respuesta.json()["mensaje"] == "Solicitud mal formada"
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "PENDIENTE"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "ASIGNADA"


def test_get_detalle_devuelve_solo_campos_permitidos(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, _ = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = asignacion_context["client"].get(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}",
		headers=_headers(usuario_id),
	)

	assert respuesta.status_code == 200
	assert set(respuesta.json()) == {"exito", "mensaje", "datos", "fechaHora"}
	assert set(respuesta.json()["datos"]) == {
		"asignacionId",
		"estadoAsignacion",
		"tipoServicio",
		"latitud",
		"longitud",
		"expiraEn",
	}
	assert respuesta.json()["datos"]["asignacionId"] == f"asg_{asignacion_id:03d}"


def test_get_de_asignacion_ajena_devuelve_404(asignacion_context):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	_, otro_usuario_id = _crear_proveedor(
		asignacion_context, latitud=LATITUD + 0.01
	)
	asignacion_id, _ = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = asignacion_context["client"].get(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}",
		headers=_headers(otro_usuario_id),
	)

	assert respuesta.status_code == 404


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_get_y_post_requieren_rol_proveedor(asignacion_context, metodo):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	_, cliente_id = _crear_proveedor(
		asignacion_context, latitud=LATITUD + 0.01
	)
	asignacion_id, _ = _crear_asignacion(asignacion_context, proveedor_id)
	url = f"{ASIGNACIONES}/asg_{asignacion_id:03d}"
	cliente = asignacion_context["client"]
	respuesta = (
		cliente.get(url, headers=_headers(cliente_id, ["CLIENTE"]))
		if metodo == "get"
		else cliente.post(
			f"{url}/respuesta",
			json={"decision": "ACEPTAR"},
			headers=_headers(cliente_id, ["CLIENTE"]),
		)
	)

	assert respuesta.status_code == 403


def test_get_requiere_token(asignacion_context):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	asignacion_id, _ = _crear_asignacion(asignacion_context, proveedor_id)

	respuesta = asignacion_context["client"].get(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}"
	)

	assert respuesta.status_code == 401


def test_get_expira_asignacion_vencida_de_forma_perezosa(asignacion_context):
	proveedor_id, usuario_id = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context,
		proveedor_id,
		segundos_hasta_expirar=-300,
	)

	respuesta = asignacion_context["client"].get(
		f"{ASIGNACIONES}/asg_{asignacion_id:03d}",
		headers=_headers(usuario_id),
	)

	assert respuesta.status_code == 200
	assert respuesta.json()["datos"]["estadoAsignacion"] == "EXPIRADA"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "BUSCANDO_PROVEEDOR"
	assert _conteo_auditoria(asignacion_context, asignacion_id) == 1


def test_expiracion_es_idempotente_y_audita_proveedor(asignacion_context):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context, proveedor_id, segundos_hasta_expirar=-300
	)
	ahora = dt.datetime.now(ZONA)

	with asignacion_context["db"]() as db:
		assert expirar_asignaciones_vencidas(db, ahora) == 1
	with asignacion_context["db"]() as db:
		assert expirar_asignaciones_vencidas(db, ahora) == 0
		auditorias = db.scalars(
			select(AuditoriaAsignacion).where(
				AuditoriaAsignacion.asignacion_id == asignacion_id
			)
		).all()

	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "EXPIRADA"
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "BUSCANDO_PROVEEDOR"
	assert len(auditorias) == 1
	assert auditorias[0].proveedor_id == proveedor_id
	assert auditorias[0].fecha is not None


def test_asignar_siguiente_candidato_excluye_al_proveedor_expirado(
	asignacion_context,
):
	proveedor_id, _ = _crear_proveedor(asignacion_context)
	siguiente_proveedor, _ = _crear_proveedor(
		asignacion_context, latitud=LATITUD + 0.01
	)
	asignacion_id, solicitud_id = _crear_asignacion(
		asignacion_context, proveedor_id, segundos_hasta_expirar=-300
	)

	with asignacion_context["db"]() as db:
		expirar_asignaciones_vencidas(db)
		nueva = asignar_proveedor_mas_cercano(
			db, f"aux_{solicitud_id:03d}"
		)

	assert nueva is not None
	assert nueva.proveedor_id == siguiente_proveedor
	assert nueva.proveedor_id != proveedor_id
	assert _estado(asignacion_context, AsignacionAuxilio, asignacion_id) == "EXPIRADA"


def test_sin_candidatos_transiciona_a_sin_proveedor(asignacion_context):
	solicitud_id = _crear_solicitud(asignacion_context)

	with asignacion_context["db"]() as db:
		asignacion = asignar_proveedor_mas_cercano(
			db, f"aux_{solicitud_id:03d}"
		)

	assert asignacion is None
	assert _estado(asignacion_context, SolicitudAuxilio, solicitud_id) == "SIN_PROVEEDOR"


def test_dos_solicitudes_concurrentes_no_asignan_al_mismo_proveedor(tmp_path):
	engine = create_engine(
		f"sqlite:///{tmp_path / 'asignaciones.db'}",
		connect_args={"check_same_thread": False, "timeout": 10},
	)
	Base.metadata.create_all(bind=engine)
	factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
	with factory() as db:
		zona = ZonaCobertura(
			nombre=f"Zona-HU20-{uuid.uuid4().hex}",
			latitud_centro=LATITUD,
			longitud_centro=LONGITUD,
			radio_km=20,
			activa=True,
		)
		db.add(zona)
		proveedor = Proveedor(
			usuario_id=uuid.uuid4().int % 2_000_000_000,
			estado_habilitacion="HABILITADO",
			estado_operativo="DISPONIBLE",
			latitud=LATITUD,
			longitud=LONGITUD,
			actualizada_en=dt.datetime.now(ZONA),
		)
		db.add(proveedor)
		db.flush()
		proveedor_id = proveedor.id
		db.add(
			DatosProveedor(
				proveedor_id=proveedor.id,
				nombre_comercial="Proveedor compartido",
				tipo_proveedor="GRUA",
			)
		)
		db.add(
			ProveedorZonaCobertura(
				proveedor_id=proveedor.id, zona_id=zona.id
			)
		)
		solicitudes = [
			SolicitudAuxilio(
				cliente_id=f"usr_{i}",
				tipo_servicio="GRUA",
				latitud=LATITUD,
				longitud=LONGITUD,
				estado="BUSCANDO_PROVEEDOR",
				version=1,
			)
			for i in (901, 902)
		]
		db.add_all(solicitudes)
		db.commit()
		solicitud_ids = [solicitud.id for solicitud in solicitudes]

	barrier = Barrier(2)

	def asignar(solicitud_id: int):
		barrier.wait(timeout=5)
		with factory() as db:
			return asignar_proveedor_mas_cercano(
				db, f"aux_{solicitud_id:03d}"
			)

	with ThreadPoolExecutor(max_workers=2) as pool:
		resultados = list(pool.map(asignar, solicitud_ids))

	with factory() as db:
		asignaciones = db.scalars(
			select(AsignacionAuxilio).where(
				AsignacionAuxilio.estado == "PENDIENTE"
			)
		).all()
		estados = [
			db.get(SolicitudAuxilio, solicitud_id).estado
			for solicitud_id in solicitud_ids
		]
	assert sum(resultado is not None for resultado in resultados) == 1
	assert len(asignaciones) == 1
	assert asignaciones[0].proveedor_id == proveedor_id
	assert sorted(estados) == ["ASIGNADA", "SIN_PROVEEDOR"]
	Base.metadata.drop_all(bind=engine)
	engine.dispose()
