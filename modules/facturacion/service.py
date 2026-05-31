from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from core.models.facturacion import (
    Producto, Documento, LineaDocumento, Consecutivo,
    TipoDocumento, EstadoDocumento, TipoImpuesto, UnidadMedida
)
from core.models.terceros import Tercero


def _r(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class FacturacionService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════
    # Productos
    # ══════════════════════════════════════════════════════════
    def listar_productos(self, criterio: str = "", solo_activos: bool = True) -> List[Producto]:
        q = self.db.query(Producto).filter(Producto.empresa_id == self.empresa_id)
        if solo_activos:
            q = q.filter(Producto.activo == True)
        if criterio:
            t = f"%{criterio}%"
            q = q.filter(Producto.nombre.ilike(t) | Producto.codigo.ilike(t))
        return q.order_by(Producto.nombre).all()

    def obtener_producto(self, prod_id: int) -> Optional[Producto]:
        return self.db.query(Producto).filter(
            Producto.id == prod_id, Producto.empresa_id == self.empresa_id
        ).first()

    def crear_producto(self, datos: dict) -> Producto:
        existe = self.db.query(Producto).filter(
            Producto.empresa_id == self.empresa_id,
            Producto.codigo     == datos["codigo"]
        ).first()
        if existe:
            raise ValueError(f"Ya existe un producto con el código '{datos['codigo']}'.")
        p = Producto(empresa_id=self.empresa_id, **datos)
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def actualizar_producto(self, prod_id: int, datos: dict) -> Producto:
        p = self.obtener_producto(prod_id)
        if not p:
            raise ValueError("Producto no encontrado.")
        for k, v in datos.items():
            setattr(p, k, v)
        self.db.commit()
        return p

    def desactivar_producto(self, prod_id: int):
        p = self.obtener_producto(prod_id)
        if p:
            p.activo = False
            self.db.commit()

    # ══════════════════════════════════════════════════════════
    # Consecutivos
    # ══════════════════════════════════════════════════════════
    def _get_consecutivo(self, tipo: TipoDocumento) -> Consecutivo:
        cons = self.db.query(Consecutivo).filter(
            Consecutivo.empresa_id == self.empresa_id,
            Consecutivo.tipo       == tipo
        ).first()
        if not cons:
            prefijos = {
                TipoDocumento.FACTURA_VENTA:       "FV",
                TipoDocumento.FACTURA_COMPRA:      "FC",
                TipoDocumento.NOTA_CREDITO_VENTA:  "NCV",
                TipoDocumento.NOTA_DEBITO_VENTA:   "NDV",
                TipoDocumento.NOTA_CREDITO_COMPRA: "NCC",
                TipoDocumento.NOTA_DEBITO_COMPRA:  "NDC",
                TipoDocumento.COTIZACION:           "COT",
                TipoDocumento.ORDEN_COMPRA:         "OC",
                TipoDocumento.REMISION:             "REM",
            }
            cons = Consecutivo(
                empresa_id=self.empresa_id,
                tipo=tipo,
                prefijo=prefijos.get(tipo, "DOC"),
                actual=0
            )
            self.db.add(cons)
            self.db.flush()
        return cons

    # ══════════════════════════════════════════════════════════
    # Documentos
    # ══════════════════════════════════════════════════════════
    def listar_documentos(
        self,
        tipo: TipoDocumento = None,
        tercero_id: int = None,
        estado: EstadoDocumento = None,
        limite: int = 200,
    ) -> List[Documento]:
        q = (self.db.query(Documento)
             .options(joinedload(Documento.tercero))
             .filter(Documento.empresa_id == self.empresa_id))
        if tipo:
            q = q.filter(Documento.tipo == tipo)
        if tercero_id:
            q = q.filter(Documento.tercero_id == tercero_id)
        if estado:
            q = q.filter(Documento.estado == estado)
        return q.order_by(Documento.fecha.desc(), Documento.id.desc()).limit(limite).all()

    def obtener_documento(self, doc_id: int) -> Optional[Documento]:
        return (self.db.query(Documento)
                .options(
                    joinedload(Documento.tercero),
                    joinedload(Documento.lineas).joinedload(LineaDocumento.producto)
                )
                .filter(Documento.id == doc_id, Documento.empresa_id == self.empresa_id)
                .first())

    def calcular_linea(self, linea: dict) -> dict:
        """Calcula subtotal, impuesto y total de una línea. No persiste."""
        cantidad  = _r(linea.get("cantidad", 1))
        precio    = _r(linea.get("precio_unitario", 0))
        desc_pct  = _r(linea.get("descuento_pct", 0))
        tarifa    = _r(linea.get("tarifa_impuesto", 0))

        bruto         = cantidad * precio
        desc_valor    = _r(bruto * desc_pct)
        subtotal      = _r(bruto - desc_valor)
        valor_impuesto = _r(subtotal * tarifa)
        total_linea   = _r(subtotal + valor_impuesto)

        return {**linea,
                "descuento_valor": desc_valor,
                "subtotal":        subtotal,
                "valor_impuesto":  valor_impuesto,
                "total_linea":     total_linea}

    def crear_documento(
        self,
        tipo: TipoDocumento,
        fecha: date,
        tercero_id: int,
        lineas: List[dict],
        observaciones: str = "",
        fecha_vence: date = None,
        periodo_id: int = None,
        documento_origen_id: int = None,
    ) -> Documento:
        if not lineas:
            raise ValueError("El documento debe tener al menos una línea.")

        cons   = self._get_consecutivo(tipo)
        numero = cons.siguiente()

        # Recalcular todas las líneas y acumular totales
        subtotal_total   = Decimal("0")
        descuento_total  = Decimal("0")
        impuesto_total   = Decimal("0")
        total_doc        = Decimal("0")

        lineas_calc = []
        for orden, l in enumerate(lineas, 1):
            lc = self.calcular_linea(l)
            lc["orden"] = orden
            subtotal_total  += lc["subtotal"]
            descuento_total += lc["descuento_valor"]
            impuesto_total  += lc["valor_impuesto"]
            total_doc       += lc["total_linea"]
            lineas_calc.append(lc)

        doc = Documento(
            empresa_id          = self.empresa_id,
            tipo                = tipo,
            numero              = numero,
            fecha               = fecha,
            fecha_vence         = fecha_vence,
            tercero_id          = tercero_id,
            documento_origen_id = documento_origen_id,
            observaciones       = observaciones,
            estado              = EstadoDocumento.BORRADOR,
            subtotal            = _r(subtotal_total),
            total_descuento     = _r(descuento_total),
            total_impuesto      = _r(impuesto_total),
            total               = _r(total_doc),
            periodo_id          = periodo_id,
        )
        self.db.add(doc)
        self.db.flush()

        for lc in lineas_calc:
            linea_obj = LineaDocumento(
                documento_id    = doc.id,
                orden           = lc["orden"],
                producto_id     = lc.get("producto_id"),
                descripcion     = lc.get("descripcion", ""),
                unidad_medida   = lc.get("unidad_medida", UnidadMedida.UNIDAD),
                cantidad        = lc["cantidad"],
                precio_unitario = lc["precio_unitario"],
                descuento_pct   = lc.get("descuento_pct", Decimal("0")),
                descuento_valor = lc["descuento_valor"],
                subtotal        = lc["subtotal"],
                tipo_impuesto   = lc.get("tipo_impuesto", TipoImpuesto.IVA),
                tarifa_impuesto = lc.get("tarifa_impuesto", Decimal("0")),
                valor_impuesto  = lc["valor_impuesto"],
                total_linea     = lc["total_linea"],
            )
            self.db.add(linea_obj)

        self.db.commit()
        self.db.refresh(doc)
        return doc

    def emitir(self, doc_id: int) -> Documento:
        doc = self.obtener_documento(doc_id)
        if not doc:
            raise ValueError("Documento no encontrado.")
        if doc.estado != EstadoDocumento.BORRADOR:
            raise ValueError("Solo se pueden emitir documentos en estado Borrador.")
        doc.estado = EstadoDocumento.EMITIDO
        self.db.commit()
        return doc

    def anular(self, doc_id: int) -> Documento:
        doc = self.obtener_documento(doc_id)
        if not doc:
            raise ValueError("Documento no encontrado.")
        if doc.estado == EstadoDocumento.ANULADO:
            raise ValueError("El documento ya está anulado.")
        doc.estado = EstadoDocumento.ANULADO
        self.db.commit()
        return doc

    # ══════════════════════════════════════════════════════════
    # Terceros (clientes / proveedores)
    # ══════════════════════════════════════════════════════════
    def listar_clientes(self) -> List[Tercero]:
        return (self.db.query(Tercero)
                .filter(Tercero.empresa_id == self.empresa_id,
                        Tercero.activo == True,
                        Tercero.es_cliente == True)
                .order_by(Tercero.nombre).all())

    def listar_proveedores(self) -> List[Tercero]:
        return (self.db.query(Tercero)
                .filter(Tercero.empresa_id == self.empresa_id,
                        Tercero.activo == True,
                        Tercero.es_proveedor == True)
                .order_by(Tercero.nombre).all())

    def buscar_terceros(self, criterio: str, tipo: str = "cliente") -> List[Tercero]:
        term = f"%{criterio}%"
        q = self.db.query(Tercero).filter(
            Tercero.empresa_id == self.empresa_id,
            Tercero.activo == True,
            Tercero.nombre.ilike(term) | Tercero.numero_documento.ilike(term)
        )
        if tipo == "cliente":
            q = q.filter(Tercero.es_cliente == True)
        elif tipo == "proveedor":
            q = q.filter(Tercero.es_proveedor == True)
        return q.order_by(Tercero.nombre).limit(30).all()
