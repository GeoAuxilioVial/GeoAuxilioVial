"""Consultas de candidatos para búsqueda de proveedores cercanos (HU-18)."""
from sqlalchemy.orm import Session

from app.domain.proveedor_domain import Proveedor
from app.domain.proveedor_hu14_domain import DatosProveedor, ProveedorZonaCobertura
from app.domain.zonas_cobertura_domain import ZonaCobertura


def listar_candidatos(
	db: Session, tipo_proveedor: str
) -> list[tuple[Proveedor, DatosProveedor, ZonaCobertura]]:
	return (
		db.query(Proveedor, DatosProveedor, ZonaCobertura)
		.join(DatosProveedor, DatosProveedor.proveedor_id == Proveedor.id)
		.join(
			ProveedorZonaCobertura,
			ProveedorZonaCobertura.proveedor_id == Proveedor.id,
		)
		.join(
			ZonaCobertura,
			ZonaCobertura.id == ProveedorZonaCobertura.zona_id,
		)
		.filter(
			Proveedor.estado_habilitacion == "HABILITADO",
			Proveedor.estado_operativo == "DISPONIBLE",
			Proveedor.latitud.is_not(None),
			Proveedor.longitud.is_not(None),
			Proveedor.actualizada_en.is_not(None),
			DatosProveedor.tipo_proveedor == tipo_proveedor,
			ZonaCobertura.activa.is_(True),
		)
		.order_by(Proveedor.id, ZonaCobertura.id)
		.all()
	)
