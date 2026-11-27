import datetime as d

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from main import app

client = TestClient(app)
URL = "/api/v1/parametros/documentos-requeridos"
BASE = [
    {"tipoDocumento": "IDENTIFICACION", "exigeVigencia": True},
    {"tipoDocumento": "SOAT", "exigeVigencia": True},
]


def _token(rol="ADMINISTRADOR"):
    payload = {"sub": "usr_test", "rol": rol,
               "exp": d.datetime.now(d.timezone.utc) + d.timedelta(hours=1)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {_token()}"}


@pytest.fixture(autouse=True)
def restaurar_grua():
    yield
    client.put(f"{URL}/GRUA", json={"documentosRequeridos": BASE},
               headers={"Authorization": f"Bearer {_token()}"})


def test_get_grua_ok(auth):
    r = client.get(URL, params={"tipoProveedor": "GRUA"}, headers=auth)
    assert r.status_code == 200
    tipos = [x["tipoDocumento"] for x in r.json()["datos"]["documentosRequeridos"]]
    assert "IDENTIFICACION" in tipos and "SOAT" in tipos


def test_get_tipo_fuera_de_catalogo(auth):
    r = client.get(URL, params={"tipoProveedor": "AVION"}, headers=auth)
    assert r.status_code == 422
    assert r.json()["datos"]["errores"][0]["codigo"] == "VALOR_FUERA_DE_CATALOGO"


def test_get_sin_tipo(auth):
    r = client.get(URL, headers=auth)
    assert r.status_code == 422
    assert r.json()["datos"]["errores"][0]["codigo"] == "CAMPO_OBLIGATORIO"


def test_put_reemplaza_lista(auth):
    nueva = [{"tipoDocumento": "SOAT", "exigeVigencia": True}]
    r = client.put(f"{URL}/GRUA", json={"documentosRequeridos": nueva}, headers=auth)
    assert r.status_code == 200
    r = client.get(URL, params={"tipoProveedor": "GRUA"}, headers=auth)
    assert r.json()["datos"]["documentosRequeridos"] == nueva


def test_put_lista_vacia(auth):
    r = client.put(f"{URL}/GRUA", json={"documentosRequeridos": []}, headers=auth)
    assert r.status_code == 422
    assert r.json()["datos"]["errores"][0]["codigo"] == "CAMPO_OBLIGATORIO"


def test_put_tipo_inexistente(auth):
    r = client.put(f"{URL}/AVION", json={"documentosRequeridos": BASE}, headers=auth)
    assert r.status_code == 404


def test_put_sin_token():
    r = client.put(f"{URL}/GRUA", json={"documentosRequeridos": BASE})
    assert r.status_code == 401


def test_put_rol_no_admin():
    h = {"Authorization": f"Bearer {_token('CLIENTE')}"}
    r = client.put(f"{URL}/GRUA", json={"documentosRequeridos": BASE}, headers=h)
    assert r.status_code == 403
