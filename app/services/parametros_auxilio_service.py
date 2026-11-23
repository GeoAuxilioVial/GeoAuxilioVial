from app.core.errors import ErrorNegocio
from app.domain.tipo_averia import UsoTipoAveriaPort
from app.repositories.parametros_auxilio_repository import ParametrosAuxilioRepository


class ConsultaUsoTipoAveriaNoConfigurada:
    """Adaptador fail-closed mientras MOD-05 no exponga la consulta de dependencias."""

    def esta_en_uso(self, tipo_averia_id: str) -> bool:
        raise ErrorNegocio(
            503,
            "No es posible verificar si el tipo de avería está en uso: la integración con MOD-05 no está configurada",
        )


class ParametrosAuxilioService:
    def __init__(self, repo: ParametrosAuxilioRepository, uso: UsoTipoAveriaPort):
        self.repo = repo
        self.uso = uso

    def listar_tipos(self, activo: bool | None = None):
        return self.repo.listar_tipos(activo)

    def crear_tipo(self, codigo: str, nombre: str, activo: bool):
        codigo = codigo.strip().upper()
        nombre = nombre.strip()
        if self.repo.obtener_tipo_por_codigo(codigo):
            raise ErrorNegocio(409, "Ya existe un tipo de avería con ese código")
        return self.repo.crear_tipo(codigo, nombre, activo)

    def actualizar_tipo(self, tipo_id: str, codigo: str, nombre: str, activo: bool):
        if self.repo.obtener_tipo(tipo_id) is None:
            raise ErrorNegocio(404, "Tipo de avería no encontrado")
        codigo = codigo.strip().upper()
        otro = self.repo.obtener_tipo_por_codigo(codigo)
        if otro and otro.id != tipo_id:
            raise ErrorNegocio(409, "Ya existe un tipo de avería con ese código")
        return self.repo.actualizar_tipo(tipo_id, codigo, nombre.strip(), activo)

    def eliminar_tipo(self, tipo_id: str):
        if self.repo.obtener_tipo(tipo_id) is None:
            raise ErrorNegocio(404, "Tipo de avería no encontrado")
        if self.uso.esta_en_uso(tipo_id):
            raise ErrorNegocio(409, "El tipo de avería está en uso por solicitudes activas y no puede eliminarse")
        self.repo.eliminar_tipo(tipo_id)

    def listar_reglas(self):
        return self.repo.listar_reglas()

    def actualizar_regla(self, regla_id: str, valor):
        return self.repo.actualizar_regla(regla_id, valor)
