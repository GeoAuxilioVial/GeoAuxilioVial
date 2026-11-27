"""Persistencia SQLAlchemy de versiones tarifarias y métodos de pago (HU-06)."""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Integer, JSON, Numeric, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.domain.tarifario import MetodoPago, RecargoTarifario, Tarifario


class TarifarioModel(Base):
    __tablename__ = "hu06_tarifarios"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    version_num: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    tarifa_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valor_por_km: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    recargos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class MetodoPagoModel(Base):
    __tablename__ = "hu06_metodos_pago"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    habilitado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


def _a_dominio(modelo: TarifarioModel) -> Tarifario:
    return Tarifario(
        modelo.id,
        f"v{modelo.version_num}",
        modelo.moneda,
        Decimal(modelo.tarifa_base),
        Decimal(modelo.valor_por_km),
        [
            RecargoTarifario(item["concepto"], Decimal(str(item["valor"])))
            for item in (modelo.recargos or [])
        ],
        modelo.vigente,
    )


def _metodo_a_dominio(modelo: MetodoPagoModel) -> MetodoPago:
    return MetodoPago(modelo.id, modelo.codigo, modelo.nombre, modelo.habilitado)


class TarifarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def obtener_vigente(self) -> Tarifario | None:
        modelo = self.db.scalar(
            select(TarifarioModel).where(TarifarioModel.vigente.is_(True))
        )
        return _a_dominio(modelo) if modelo else None

    def actualizar_tarifario(self, moneda, tarifa_base, valor_por_km, recargos) -> Tarifario:
        # Se conserva cada versión anterior: servicios ya cotizados/liquidados no
        # cambian retroactivamente. La transacción deja una única versión vigente.
        anterior = self.db.scalar(
            select(TarifarioModel)
            .where(TarifarioModel.vigente.is_(True))
            .with_for_update()
        )
        siguiente = (anterior.version_num + 1) if anterior else 1
        self.db.query(TarifarioModel).filter(TarifarioModel.vigente.is_(True)).update(
            {TarifarioModel.vigente: False}, synchronize_session=False
        )
        modelo = TarifarioModel(
            id=f"tar_{uuid.uuid4().hex[:12]}",
            version_num=siguiente,
            moneda=moneda,
            tarifa_base=tarifa_base,
            valor_por_km=valor_por_km,
            recargos=[
                {"concepto": item["concepto"], "valor": str(item["valor"])}
                for item in recargos
            ],
            vigente=True,
        )
        self.db.add(modelo)
        self.db.commit()
        self.db.refresh(modelo)
        return _a_dominio(modelo)

    def listar_metodos_pago(self) -> list[MetodoPago]:
        modelos = self.db.scalars(
            select(MetodoPagoModel).order_by(MetodoPagoModel.codigo)
        ).all()
        return [_metodo_a_dominio(item) for item in modelos]

    def actualizar_metodo_pago(self, metodo_id: str, habilitado: bool) -> MetodoPago | None:
        modelo = self.db.get(MetodoPagoModel, metodo_id)
        if modelo is None:
            return None
        modelo.habilitado = habilitado
        self.db.commit()
        self.db.refresh(modelo)
        return _metodo_a_dominio(modelo)

    def inicializar_catalogos(self) -> None:
        # Catálogo inicial propuesto porque la HU no enumera métodos concretos.
        # La tarjeta se representa únicamente como opción de pasarela externa.
        iniciales = [
            ("EFECTIVO", "Efectivo"),
            ("TARJETA_PASARELA", "Tarjeta mediante pasarela externa"),
            ("TRANSFERENCIA", "Transferencia bancaria"),
        ]
        for codigo, nombre in iniciales:
            existe = self.db.scalar(
                select(MetodoPagoModel).where(MetodoPagoModel.codigo == codigo)
            )
            if existe is None:
                self.db.add(
                    MetodoPagoModel(
                        id=f"mp_{uuid.uuid4().hex[:10]}",
                        codigo=codigo,
                        nombre=nombre,
                        habilitado=True,
                    )
                )

        if self.obtener_vigente() is None:
            self.db.add(
                TarifarioModel(
                    id=f"tar_{uuid.uuid4().hex[:12]}",
                    version_num=1,
                    moneda="COP",
                    tarifa_base=Decimal("60000"),
                    valor_por_km=Decimal("2300"),
                    recargos=[{"concepto": "RECARGO_NOCTURNO", "valor": "10000"}],
                    vigente=True,
                )
            )
        self.db.commit()
