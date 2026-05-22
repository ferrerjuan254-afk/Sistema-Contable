from sqlalchemy.orm import Session
from core.models.empresa import Empresa, Sede
from modules.contabilidad.puc_colombia import cargar_puc


class EmpresaService:

    def __init__(self, session: Session):
        self.session = session

    # ── Empresas ───────────────────────────────────────────────

    def listar(self) -> list[Empresa]:
        return self.session.query(Empresa).filter_by(activa=True).order_by(Empresa.razon_social).all()

    def obtener(self, empresa_id: int) -> Empresa | None:
        return self.session.get(Empresa, empresa_id)

    def crear(self, datos: dict) -> Empresa:
        empresa = Empresa(**datos)
        self.session.add(empresa)
        self.session.flush()  # Para obtener el ID

        # Crear sede principal automáticamente
        sede = Sede(
            empresa_id=empresa.id,
            nombre="Sede Principal",
            ciudad=empresa.ciudad,
            direccion=empresa.direccion,
            telefono=empresa.telefono,
            activa=True,
        )
        self.session.add(sede)

        # Cargar PUC colombiano para la empresa
        cargar_puc(self.session, empresa.id)

        self.session.commit()
        return empresa

    def actualizar(self, empresa_id: int, datos: dict) -> Empresa | None:
        empresa = self.obtener(empresa_id)
        if not empresa:
            return None
        for campo, valor in datos.items():
            setattr(empresa, campo, valor)
        self.session.commit()
        return empresa

    def desactivar(self, empresa_id: int) -> bool:
        empresa = self.obtener(empresa_id)
        if not empresa:
            return False
        empresa.activa = False
        self.session.commit()
        return True

    # ── Sedes ──────────────────────────────────────────────────

    def listar_sedes(self, empresa_id: int) -> list[Sede]:
        return (
            self.session.query(Sede)
            .filter_by(empresa_id=empresa_id, activa=True)
            .order_by(Sede.nombre)
            .all()
        )

    def crear_sede(self, empresa_id: int, datos: dict) -> Sede:
        sede = Sede(empresa_id=empresa_id, **datos)
        self.session.add(sede)
        self.session.commit()
        return sede

    def actualizar_sede(self, sede_id: int, datos: dict) -> Sede | None:
        sede = self.session.get(Sede, sede_id)
        if not sede:
            return None
        for campo, valor in datos.items():
            setattr(sede, campo, valor)
        self.session.commit()
        return sede

    def desactivar_sede(self, sede_id: int) -> bool:
        sede = self.session.get(Sede, sede_id)
        if not sede:
            return False
        sede.activa = False
        self.session.commit()
        return True
