from typing import List, Optional
from sqlalchemy.orm import Session
from core.models.terceros import Tercero, TipoDocumento, TipoTercero


class TercerosService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    def listar(
        self,
        criterio: str = "",
        solo_clientes: bool = False,
        solo_proveedores: bool = False,
        solo_empleados: bool = False,
    ) -> List[Tercero]:
        q = self.db.query(Tercero).filter(
            Tercero.empresa_id == self.empresa_id,
            Tercero.activo == True,
        )
        if criterio:
            term = f"%{criterio}%"
            q = q.filter(
                Tercero.nombre.ilike(term) |
                Tercero.numero_documento.ilike(term)
            )
        if solo_clientes:
            q = q.filter(Tercero.es_cliente == True)
        if solo_proveedores:
            q = q.filter(Tercero.es_proveedor == True)
        if solo_empleados:
            q = q.filter(Tercero.es_empleado == True)
        return q.order_by(Tercero.nombre).all()

    def obtener(self, tercero_id: int) -> Optional[Tercero]:
        return self.db.query(Tercero).filter(
            Tercero.id == tercero_id,
            Tercero.empresa_id == self.empresa_id,
        ).first()

    def buscar(self, criterio: str, limit: int = 30) -> List[Tercero]:
        term = f"%{criterio}%"
        return (
            self.db.query(Tercero)
            .filter(
                Tercero.empresa_id == self.empresa_id,
                Tercero.activo == True,
                (Tercero.nombre.ilike(term) | Tercero.numero_documento.ilike(term))
            )
            .order_by(Tercero.nombre)
            .limit(limit)
            .all()
        )

    def crear(self, datos: dict) -> Tercero:
        # Validar documento único por empresa
        existe = self.db.query(Tercero).filter(
            Tercero.empresa_id   == self.empresa_id,
            Tercero.tipo_documento == datos["tipo_documento"],
            Tercero.numero_documento == datos["numero_documento"],
        ).first()
        if existe:
            raise ValueError(
                f"Ya existe un tercero con {datos['tipo_documento'].upper()} "
                f"{datos['numero_documento']}."
            )
        tercero = Tercero(empresa_id=self.empresa_id, **datos)
        self.db.add(tercero)
        self.db.commit()
        self.db.refresh(tercero)
        return tercero

    def actualizar(self, tercero_id: int, datos: dict) -> Tercero:
        tercero = self.obtener(tercero_id)
        if not tercero:
            raise ValueError("Tercero no encontrado.")
        for campo, valor in datos.items():
            setattr(tercero, campo, valor)
        self.db.commit()
        return tercero

    def desactivar(self, tercero_id: int) -> bool:
        tercero = self.obtener(tercero_id)
        if not tercero:
            return False
        tercero.activo = False
        self.db.commit()
        return True
