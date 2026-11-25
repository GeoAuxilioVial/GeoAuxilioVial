"""Reglas de negocio y acceso de lectura para consumidores MOD-05/MOD-07."""
from app.core.errors import ErrorNegocio
from app.repositories.tarifario_repository import TarifarioRepository


class TarifarioService:
    def __init__(self, repo: TarifarioRepository):
        self.repo = repo

    def consultar_tarifario(self):
        tarifario = self.repo.obtener_vigente()
        if tarifario is None:
            raise ErrorNegocio(404, "No existe un tarifario vigente")
        return tarifario

    def actualizar_tarifario(self, datos):
        # Pydantic ya valida importes no negativos, formato y conceptos únicos.
        return self.repo.actualizar_tarifario(
            moneda=datos.moneda,
            tarifa_base=datos.tarifaBase,
            valor_por_km=datos.valorPorKm,
            recargos=[item.model_dump() for item in datos.recargos],
        )

    def listar_metodos_pago(self):
        return self.repo.listar_metodos_pago()

    def actualizar_metodo_pago(self, metodo_id: str, habilitado: bool):
        metodo = self.repo.actualizar_metodo_pago(metodo_id, habilitado)
        if metodo is None:
            raise ErrorNegocio(404, "Método de pago no encontrado")
        return metodo


def obtener_tarifario_vigente(db):
    """Punto de lectura reutilizable por MOD-05 y MOD-07."""
    return TarifarioService(TarifarioRepository(db)).consultar_tarifario()
