"""Contrato de respuesta de proveedores cercanos (HU-18)."""
from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import DatosProveedor


def proveedor_cercano_a_dict(
	proveedor: Proveedor,
	perfil: DatosProveedor,
	distancia: float,
) -> dict:
	return {
		"id": proveedor.proveedor_id,
		"nombreComercial": perfil.nombre_comercial,
		"distanciaKm": round(distancia, 2),
		"estado": proveedor.estado_operativo,
		"calificacionPromedio": None,
	}
