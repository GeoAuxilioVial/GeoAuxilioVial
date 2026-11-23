from app.core.errors import ErrorNegocio
from app.domain.tipo_vehiculo import TipoVehiculo, UsoTipoVehiculoPort, normalizar_codigo
from app.repositories.tipo_vehiculo_repository import TipoVehiculoRepository


class ConsultaUsoNoConfigurada:
    """Adaptador seguro hasta integrar el endpoint/cliente real de MOD-02.

    Fallar cerrado evita borrar accidentalmente un tipo que esté en uso.
    """

    def esta_en_uso(self, tipo_vehiculo_id: str) -> bool:
        raise ErrorNegocio(
            503,
            "No es posible verificar si el tipo está en uso: la integración con MOD-02 aún no está configurada",
        )


class TipoVehiculoService:
    def __init__(self, repo: TipoVehiculoRepository, uso: UsoTipoVehiculoPort):
        self.repo = repo
        self.uso = uso

    def listar(self, activo: bool | None = None) -> list[TipoVehiculo]:
        return self.repo.listar(activo)

    def crear(self, codigo: str, nombre: str, categoria: str, activo: bool) -> TipoVehiculo:
        codigo = normalizar_codigo(codigo)
        nombre = nombre.strip()
        categoria = categoria.strip().upper()
        if self.repo.obtener_por_codigo(codigo):
            raise ErrorNegocio(409, "Ya existe un tipo de vehículo con ese código")
        return self.repo.crear(codigo, nombre, categoria, activo)

    def actualizar(
        self, tipo_id: str, codigo: str, nombre: str, categoria: str, activo: bool
    ) -> TipoVehiculo:
        if self.repo.obtener(tipo_id) is None:
            raise ErrorNegocio(404, "Tipo de vehículo no encontrado")
        codigo = normalizar_codigo(codigo)
        otro = self.repo.obtener_por_codigo(codigo)
        if otro and otro.id != tipo_id:
            raise ErrorNegocio(409, "Ya existe un tipo de vehículo con ese código")
        return self.repo.actualizar(
            tipo_id, codigo, nombre.strip(), categoria.strip().upper(), activo
        )

    def eliminar(self, tipo_id: str) -> None:
        if self.repo.obtener(tipo_id) is None:
            raise ErrorNegocio(404, "Tipo de vehículo no encontrado")
        if self.uso.esta_en_uso(tipo_id):
            raise ErrorNegocio(
                409,
                "El tipo de vehículo está en uso por registros activos y no puede eliminarse",
            )
        self.repo.eliminar(tipo_id)
