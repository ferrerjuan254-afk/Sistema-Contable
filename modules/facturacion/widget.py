from decimal import Decimal, InvalidOperation
from datetime import date, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QComboBox, QFrame, QTabWidget,
    QSplitter, QDateEdit, QDoubleSpinBox, QTextEdit,
    QCheckBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from core.models.facturacion import (
    TipoDocumento, EstadoDocumento, TipoImpuesto, UnidadMedida
)
from modules.facturacion.service import FacturacionService

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_SUCCESS = "background:#059669;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_DANGER  = "color:#dc2626;border:1px solid #fca5a5;padding:4px 10px;border-radius:5px;"
BTN_WARN    = "background:#d97706;color:white;padding:5px 12px;border-radius:5px;"


def _fmt(v) -> str:
    try:
        return f"${Decimal(str(v)):,.2f}"
    except Exception:
        return "$0.00"


TIPOS_DOC_LABELS = {
    TipoDocumento.FACTURA_VENTA:       "Factura de Venta",
    TipoDocumento.FACTURA_COMPRA:      "Factura de Compra",
    TipoDocumento.NOTA_CREDITO_VENTA:  "Nota Crédito Venta",
    TipoDocumento.NOTA_DEBITO_VENTA:   "Nota Débito Venta",
    TipoDocumento.NOTA_CREDITO_COMPRA: "Nota Crédito Compra",
    TipoDocumento.NOTA_DEBITO_COMPRA:  "Nota Débito Compra",
    TipoDocumento.COTIZACION:          "Cotización",
    TipoDocumento.ORDEN_COMPRA:        "Orden de Compra",
    TipoDocumento.REMISION:            "Remisión",
}

ESTADO_COLOR = {
    "borrador": ("#92400e", "#fef3c7"),
    "emitido":  ("#166534", "#dcfce7"),
    "anulado":  ("#7f1d1d", "#fee2e2"),
}

IMPUESTOS = [
    ("Sin impuesto",      TipoImpuesto.NINGUNO, Decimal("0")),
    ("IVA 19%",           TipoImpuesto.IVA,     Decimal("0.19")),
    ("IVA 5%",            TipoImpuesto.IVA,     Decimal("0.05")),
    ("INC 8%",            TipoImpuesto.INC,     Decimal("0.08")),
    ("Retención Fuente",  TipoImpuesto.RETENCION, Decimal("0")),
]

UNIDADES = [(u.value.upper(), u) for u in UnidadMedida]


# ══════════════════════════════════════════════════════════════
# Widget búsqueda de tercero (reutiliza patrón CuentaSearch)
# ══════════════════════════════════════════════════════════════
class TerceroSearchWidget(QWidget):
    tercero_seleccionado = pyqtSignal(object)

    def __init__(self, service: FacturacionService, tipo: str = "cliente", parent=None):
        super().__init__(parent)
        self.service  = service
        self.tipo     = tipo
        self._tercero = None
        self._sel     = False
        self._frame   = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Buscar por nombre o documento...")
        self.edit.textChanged.connect(self._on_text)
        lay.addWidget(self.edit)

        self._timer = QTimer(); self._timer.setSingleShot(True)
        self._timer.setInterval(180); self._timer.timeout.connect(self._buscar)

    def _popup(self):
        if self._frame:
            return self._frame
        top = self.window()
        f = QFrame(top)
        f.setStyleSheet("QFrame{border:2px solid #2563eb;background:white;border-radius:4px;}")
        f.hide()
        fl = QVBoxLayout(f); fl.setContentsMargins(0, 0, 0, 0)
        lst = QListWidget()
        lst.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lst.setStyleSheet(
            "QListWidget{border:none;background:white;font-size:12px;color:#111;}"
            "QListWidget::item{color:#111;padding:4px 8px;}"
            "QListWidget::item:hover{background:#eff6ff;color:#1e3a8a;}"
        )
        lst.itemClicked.connect(self._on_click)
        fl.addWidget(lst); f._lista = lst
        self._frame = f
        return f

    def _on_text(self, text):
        if self._sel:
            return
        if not text.strip():
            self._tercero = None
            self.edit.setStyleSheet("")
            if self._frame:
                self._frame.hide()
            return
        self._timer.start()

    def _buscar(self):
        texto = self.edit.text().strip()
        if not texto:
            return
        resultados = self.service.buscar_terceros(texto, self.tipo)
        p = self._popup(); p._lista.clear()
        if not resultados:
            p.hide(); return
        for t in resultados:
            item = QListWidgetItem(f"{t.numero_documento}  —  {t.nombre}")
            item.setForeground(QColor("#111111"))
            item.setData(Qt.ItemDataRole.UserRole, t)
            p._lista.addItem(item)
        top = self.window()
        gp = self.edit.mapToGlobal(self.edit.rect().bottomLeft())
        lp = top.mapFromGlobal(gp)
        p.setGeometry(lp.x(), lp.y(), max(self.edit.width(), 400),
                      min(len(resultados) * 28 + 4, 240))
        p.raise_(); p.show()

    def _on_click(self, item):
        t = item.data(Qt.ItemDataRole.UserRole)
        self._tercero = t
        self._sel = True
        self.edit.setText(f"{t.numero_documento}  —  {t.nombre}")
        self.edit.setStyleSheet("border:1px solid #16a34a;color:#111;")
        self._sel = False
        self._frame.hide()
        self.tercero_seleccionado.emit(t)

    def get_tercero(self):
        return self._tercero

    def set_tercero(self, t):
        self._tercero = t
        self._sel = True
        self.edit.setText(f"{t.numero_documento}  —  {t.nombre}" if t else "")
        self._sel = False

    def hideEvent(self, e):
        if self._frame:
            self._frame.hide()
        super().hideEvent(e)


# ══════════════════════════════════════════════════════════════
# Diálogo: Crear / Editar Producto
# ══════════════════════════════════════════════════════════════
class DialogProducto(QDialog):
    def __init__(self, parent=None, producto=None):
        super().__init__(parent)
        self.producto = producto
        self.setWindowTitle("Nuevo producto/servicio" if not producto else "Editar producto")
        self.setMinimumWidth(480)
        self._build_ui()
        if producto:
            self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12)

        grp1 = QGroupBox("Identificación")
        grp1.setStyleSheet("QGroupBox{font-weight:bold;}")
        f1 = QFormLayout(grp1); f1.setSpacing(8)
        self.f_codigo    = QLineEdit(); self.f_codigo.setMaxLength(40)
        self.f_nombre    = QLineEdit()
        self.f_desc      = QTextEdit(); self.f_desc.setFixedHeight(60)
        self.chk_serv    = QCheckBox("Es un servicio (no maneja inventario)")
        self.cb_unidad   = QComboBox()
        for label, val in UNIDADES:
            self.cb_unidad.addItem(label, val)
        f1.addRow("Código *:",      self.f_codigo)
        f1.addRow("Nombre *:",      self.f_nombre)
        f1.addRow("Descripción:",   self.f_desc)
        f1.addRow("",               self.chk_serv)
        f1.addRow("Unidad medida:", self.cb_unidad)
        lay.addWidget(grp1)

        grp2 = QGroupBox("Precios e impuestos")
        grp2.setStyleSheet("QGroupBox{font-weight:bold;}")
        f2 = QFormLayout(grp2); f2.setSpacing(8)
        self.spin_pventa  = QDoubleSpinBox()
        self.spin_pventa.setRange(0, 999_999_999); self.spin_pventa.setDecimals(2)
        self.spin_pventa.setPrefix("$ "); self.spin_pventa.setSingleStep(1000)
        self.spin_pcompra = QDoubleSpinBox()
        self.spin_pcompra.setRange(0, 999_999_999); self.spin_pcompra.setDecimals(2)
        self.spin_pcompra.setPrefix("$ "); self.spin_pcompra.setSingleStep(1000)
        self.cb_impuesto  = QComboBox()
        for label, tipo, tarifa in IMPUESTOS:
            self.cb_impuesto.addItem(label, (tipo, tarifa))
        f2.addRow("Precio de venta:",  self.spin_pventa)
        f2.addRow("Precio de compra:", self.spin_pcompra)
        f2.addRow("Impuesto:",         self.cb_impuesto)
        lay.addWidget(grp2)

        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def _cargar(self):
        p = self.producto
        self.f_codigo.setText(p.codigo or "")
        self.f_nombre.setText(p.nombre or "")
        self.f_desc.setPlainText(p.descripcion or "")
        self.chk_serv.setChecked(bool(p.es_servicio))
        self.spin_pventa.setValue(float(p.precio_venta or 0))
        self.spin_pcompra.setValue(float(p.precio_compra or 0))
        for i in range(self.cb_impuesto.count()):
            tipo, tarifa = self.cb_impuesto.itemData(i)
            if tipo == p.tipo_impuesto and abs(float(tarifa) - float(p.tarifa_impuesto or 0)) < 0.0001:
                self.cb_impuesto.setCurrentIndex(i); break
        for i in range(self.cb_unidad.count()):
            if self.cb_unidad.itemData(i) == p.unidad_medida:
                self.cb_unidad.setCurrentIndex(i); break

    def _guardar(self):
        if not self.f_codigo.text().strip() or not self.f_nombre.text().strip():
            QMessageBox.warning(self, "Requerido", "Código y nombre son obligatorios.")
            return
        self.accept()

    def datos(self) -> dict:
        tipo_imp, tarifa = self.cb_impuesto.currentData()
        return {
            "codigo":          self.f_codigo.text().strip(),
            "nombre":          self.f_nombre.text().strip(),
            "descripcion":     self.f_desc.toPlainText().strip() or None,
            "es_servicio":     self.chk_serv.isChecked(),
            "unidad_medida":   self.cb_unidad.currentData(),
            "precio_venta":    Decimal(str(int(self.spin_pventa.value()))),
            "precio_compra":   Decimal(str(int(self.spin_pcompra.value()))),
            "tipo_impuesto":   tipo_imp,
            "tarifa_impuesto": tarifa,
        }


# ══════════════════════════════════════════════════════════════
# Tab: Productos / Servicios
# ══════════════════════════════════════════════════════════════
class TabProductos(QWidget):
    def __init__(self, service: FacturacionService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui(); self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(10)
        tb = QHBoxLayout()
        self.f_buscar = QLineEdit(); self.f_buscar.setPlaceholderText("🔍 Buscar...")
        self.f_buscar.setFixedHeight(32)
        self.f_buscar.textChanged.connect(self._on_buscar)
        self._timer = QTimer(); self._timer.setSingleShot(True)
        self._timer.setInterval(250); self._timer.timeout.connect(self._cargar)
        self.lbl_total = QLabel(); self.lbl_total.setStyleSheet("color:#64748b;font-size:12px;")
        btn_nuevo = QPushButton("+ Nuevo"); btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.setFixedHeight(32); btn_nuevo.clicked.connect(self._nuevo)
        self.btn_editar = QPushButton("✏️ Editar")
        self.btn_editar.setEnabled(False); self.btn_editar.clicked.connect(self._editar)
        self.btn_elim = QPushButton("🗑️")
        self.btn_elim.setEnabled(False); self.btn_elim.setStyleSheet(BTN_DANGER)
        self.btn_elim.clicked.connect(self._eliminar)
        for w in [self.f_buscar, self.lbl_total]:
            tb.addWidget(w, 1 if w == self.f_buscar else 0)
        tb.addStretch(); tb.addWidget(btn_nuevo)
        tb.addWidget(self.btn_editar); tb.addWidget(self.btn_elim)
        lay.addLayout(tb)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Código", "Nombre", "Tipo", "Unidad", "P. Venta", "Impuesto"])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 100); self.tabla.setColumnWidth(2, 80)
        self.tabla.setColumnWidth(3, 70);  self.tabla.setColumnWidth(4, 110)
        self.tabla.setColumnWidth(5, 100)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        self.tabla.itemDoubleClicked.connect(lambda _: self._editar())
        lay.addWidget(self.tabla)

    def _cargar(self):
        self.tabla.setRowCount(0)
        prods = self.service.listar_productos(criterio=self.f_buscar.text().strip())
        for p in prods:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            item = QTableWidgetItem(p.codigo); item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.tabla.setItem(r, 0, item)
            self.tabla.setItem(r, 1, QTableWidgetItem(p.nombre))
            self.tabla.setItem(r, 2, QTableWidgetItem("Servicio" if p.es_servicio else "Producto"))
            self.tabla.setItem(r, 3, QTableWidgetItem(p.unidad_medida.value.upper() if p.unidad_medida else ""))
            v = QTableWidgetItem(_fmt(p.precio_venta))
            v.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(r, 4, v)
            tarifa_pct = float(p.tarifa_impuesto or 0) * 100
            imp_str = f"{p.tipo_impuesto.value.upper()} {tarifa_pct:.0f}%" if tarifa_pct > 0 else "—"
            self.tabla.setItem(r, 5, QTableWidgetItem(imp_str))
        self.lbl_total.setText(f"{len(prods)} registros")
        self.btn_editar.setEnabled(False); self.btn_elim.setEnabled(False)

    def _on_buscar(self): self._timer.start()
    def _on_sel(self):
        t = bool(self.tabla.selectedItems())
        self.btn_editar.setEnabled(t); self.btn_elim.setEnabled(t)

    def _nuevo(self):
        dlg = DialogProducto(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_producto(dlg.datos()); self._cargar()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _editar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        pid = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        p   = self.service.obtener_producto(pid)
        dlg = DialogProducto(self, producto=p)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar_producto(pid, dlg.datos()); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _eliminar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        pid    = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        nombre = self.tabla.item(fila, 1).text()
        if QMessageBox.question(self, "Confirmar", f"¿Desactivar '{nombre}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.service.desactivar_producto(pid); self._cargar()

    def refresh(self): self._cargar()


# ══════════════════════════════════════════════════════════════
# Diálogo: Nuevo Documento (Factura / Nota / Cotización)
# ══════════════════════════════════════════════════════════════
class DialogDocumento(QDialog):
    def __init__(self, service: FacturacionService,
                 tipo: TipoDocumento, parent=None):
        super().__init__(parent)
        self.service = service
        self.tipo    = tipo
        self.setWindowTitle(TIPOS_DOC_LABELS.get(tipo, "Documento"))
        self.setMinimumSize(1060, 680)
        self._build_ui()
        self._agregar_linea()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        titulo = QLabel(f"📄 {TIPOS_DOC_LABELS.get(self.tipo, 'Documento')}")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b;"); lay.addWidget(titulo)

        # Cabecera
        cab = QGroupBox("Datos del documento")
        cab.setStyleSheet("QGroupBox{font-weight:bold;}")
        cl = QHBoxLayout(cab)

        tipo_tercero = "proveedor" if "compra" in self.tipo.value else "cliente"
        self.tercero_sw = TerceroSearchWidget(self.service, tipo=tipo_tercero)

        self.de_fecha = QDateEdit(QDate.currentDate()); self.de_fecha.setCalendarPopup(True)
        self.de_fecha.setFixedWidth(120)
        self.de_vence = QDateEdit(QDate.currentDate().addDays(30))
        self.de_vence.setCalendarPopup(True); self.de_vence.setFixedWidth(120)
        self.f_obs = QLineEdit(); self.f_obs.setPlaceholderText("Observaciones...")

        cl.addWidget(QLabel(f"{'Cliente' if tipo_tercero=='cliente' else 'Proveedor'} *:"))
        cl.addWidget(self.tercero_sw, 2)
        cl.addWidget(QLabel("  Fecha:")); cl.addWidget(self.de_fecha)
        cl.addWidget(QLabel("  Vence:")); cl.addWidget(self.de_vence)
        cl.addWidget(QLabel("  Obs:")); cl.addWidget(self.f_obs, 1)
        lay.addWidget(cab)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;"); lay.addWidget(sep)

        lbl_lin = QLabel("Líneas del documento")
        lbl_lin.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold)); lay.addWidget(lbl_lin)

        # Tabla de líneas
        # Cols: Descripción | Unidad | Cantidad | Precio unit. | Desc% | Subtotal | Impuesto | Total línea
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels(
            ["Descripción / Producto", "Unidad", "Cantidad", "Precio unit.", "Desc%", "Subtotal", "Impuesto", "Total"]
        )
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.setColumnWidth(1, 65); self.tbl.setColumnWidth(2, 80)
        self.tbl.setColumnWidth(3, 115); self.tbl.setColumnWidth(4, 60)
        self.tbl.setColumnWidth(5, 105); self.tbl.setColumnWidth(6, 90)
        self.tbl.setColumnWidth(7, 110)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.cellChanged.connect(self._on_cell_changed)
        lay.addWidget(self.tbl)

        lin_tb = QHBoxLayout()
        btn_add_linea = QPushButton("+ Línea vacía"); btn_add_linea.clicked.connect(self._agregar_linea)
        btn_prod = QPushButton("📦 Buscar producto"); btn_prod.clicked.connect(self._agregar_desde_producto)
        btn_del  = QPushButton("🗑 Quitar línea")
        btn_del.setStyleSheet("color:#dc2626;"); btn_del.clicked.connect(self._quitar_linea)
        lin_tb.addWidget(btn_add_linea); lin_tb.addWidget(btn_prod)
        lin_tb.addWidget(btn_del); lin_tb.addStretch()
        lay.addLayout(lin_tb)

        # Totales
        tots = QHBoxLayout(); tots.addStretch()
        self.lbl_subtotal = QLabel("Subtotal: $0.00")
        self.lbl_iva      = QLabel("Impuesto: $0.00")
        self.lbl_total    = QLabel("TOTAL: $0.00")
        self.lbl_total.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_total.setStyleSheet("color:#1d4ed8;")
        for lbl in [self.lbl_subtotal, self.lbl_iva]:
            lbl.setStyleSheet("color:#64748b;font-size:12px;")
        tots.addWidget(self.lbl_subtotal); tots.addWidget(QLabel("  |  "))
        tots.addWidget(self.lbl_iva); tots.addWidget(QLabel("    "))
        tots.addWidget(self.lbl_total)
        lay.addLayout(tots)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#e2e8f0;"); lay.addWidget(sep2)

        btns = QHBoxLayout(); btns.addStretch()
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        self.btn_borrador = QPushButton("💾 Guardar borrador")
        self.btn_borrador.clicked.connect(lambda: self._guardar(emitir=False))
        self.btn_emitir   = QPushButton("✅ Guardar y emitir")
        self.btn_emitir.setStyleSheet(BTN_SUCCESS)
        self.btn_emitir.clicked.connect(lambda: self._guardar(emitir=True))
        btns.addWidget(btn_cancel); btns.addWidget(self.btn_borrador)
        btns.addWidget(self.btn_emitir)
        lay.addLayout(btns)

        self._id_guardado = None

    # ── Líneas ─────────────────────────────────────────────────
    def _agregar_linea(self, desc="", unidad=None, cantidad=1.0,
                       precio=0.0, desc_pct=0.0,
                       tipo_imp=TipoImpuesto.NINGUNO, tarifa=Decimal("0"),
                       producto_id=None):
        self.tbl.blockSignals(True)
        r = self.tbl.rowCount(); self.tbl.insertRow(r)

        desc_item = QTableWidgetItem(desc)
        desc_item.setData(Qt.ItemDataRole.UserRole, {
            "producto_id": producto_id,
            "tipo_impuesto": tipo_imp,
            "tarifa_impuesto": tarifa,
        })
        self.tbl.setItem(r, 0, desc_item)

        und_cb = QComboBox()
        for label, val in UNIDADES:
            und_cb.addItem(label, val)
        if unidad:
            for i in range(und_cb.count()):
                if und_cb.itemData(i) == unidad:
                    und_cb.setCurrentIndex(i); break
        self.tbl.setCellWidget(r, 1, und_cb)

        for col, val, align_right in [
            (2, str(cantidad),       True),
            (3, f"{precio:.2f}",     True),
            (4, f"{desc_pct:.2f}",   True),
        ]:
            it = QTableWidgetItem(val)
            if align_right:
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl.setItem(r, col, it)

        for col in (5, 6, 7):
            it = QTableWidgetItem("0.00")
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it.setForeground(QColor("#64748b"))
            self.tbl.setItem(r, col, it)

        self.tbl.setRowHeight(r, 34)
        self.tbl.blockSignals(False)
        self._recalcular_fila(r)

    def _agregar_desde_producto(self):
        """Abre un mini-diálogo para buscar y seleccionar un producto."""
        dlg = QDialog(self); dlg.setWindowTitle("Buscar producto")
        dlg.setMinimumSize(500, 380)
        dlay = QVBoxLayout(dlg)
        buscar = QLineEdit(); buscar.setPlaceholderText("Buscar por código o nombre...")
        dlay.addWidget(buscar)
        lista = QTableWidget(0, 4)
        lista.setHorizontalHeaderLabels(["Código", "Nombre", "Precio venta", "IVA"])
        lista.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lista.setColumnWidth(0, 80); lista.setColumnWidth(2, 110); lista.setColumnWidth(3, 80)
        lista.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lista.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lista.verticalHeader().setVisible(False)
        lista.setAlternatingRowColors(False)
        dlay.addWidget(lista)
        btns2 = QHBoxLayout(); btns2.addStretch()
        btn_ok2 = QPushButton("Agregar al documento"); btn_ok2.setStyleSheet(BTN_PRIMARY)
        btn_ok2.clicked.connect(dlg.accept)
        btns2.addWidget(QPushButton("Cancelar", clicked=dlg.reject)); btns2.addWidget(btn_ok2)
        dlay.addLayout(btns2)

        def _fill(texto=""):
            lista.setRowCount(0)
            for p in self.service.listar_productos(criterio=texto):
                r2 = lista.rowCount(); lista.insertRow(r2)
                item = QTableWidgetItem(p.codigo)
                item.setData(Qt.ItemDataRole.UserRole, p)
                lista.setItem(r2, 0, item)
                lista.setItem(r2, 1, QTableWidgetItem(p.nombre))
                vi = QTableWidgetItem(_fmt(p.precio_venta))
                vi.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                lista.setItem(r2, 2, vi)
                t_pct = float(p.tarifa_impuesto or 0) * 100
                lista.setItem(r2, 3, QTableWidgetItem(f"{t_pct:.0f}%" if t_pct else "—"))

        _timer2 = QTimer(); _timer2.setSingleShot(True); _timer2.setInterval(220)
        _timer2.timeout.connect(lambda: _fill(buscar.text()))
        buscar.textChanged.connect(lambda _: _timer2.start())
        _fill()

        if dlg.exec() == QDialog.DialogCode.Accepted:
            fila_sel = lista.currentRow()
            if fila_sel >= 0:
                prod = lista.item(fila_sel, 0).data(Qt.ItemDataRole.UserRole)
                self._agregar_linea(
                    desc       = prod.nombre,
                    unidad     = prod.unidad_medida,
                    cantidad   = 1.0,
                    precio     = float(prod.precio_venta or 0),
                    tipo_imp   = prod.tipo_impuesto,
                    tarifa     = prod.tarifa_impuesto or Decimal("0"),
                    producto_id= prod.id,
                )

    def _quitar_linea(self):
        fila = self.tbl.currentRow()
        if fila >= 0 and self.tbl.rowCount() > 1:
            self.tbl.removeRow(fila); self._actualizar_totales()

    def _on_cell_changed(self, row, col):
        if col in (2, 3, 4):
            self._recalcular_fila(row)

    def _recalcular_fila(self, row):
        self.tbl.blockSignals(True)
        try:
            desc_item = self.tbl.item(row, 0)
            meta      = desc_item.data(Qt.ItemDataRole.UserRole) if desc_item else {}
            tarifa    = Decimal(str(meta.get("tarifa_impuesto", 0) or 0))

            cantidad = Decimal(self.tbl.item(row, 2).text().replace(",", ".") or "0")
            precio   = Decimal(self.tbl.item(row, 3).text().replace(",", ".") or "0")
            desc_pct = Decimal(self.tbl.item(row, 4).text().replace(",", ".") or "0") / 100

            bruto      = cantidad * precio
            desc_val   = (bruto * desc_pct).quantize(Decimal("0.01"))
            subtotal   = (bruto - desc_val).quantize(Decimal("0.01"))
            impuesto   = (subtotal * tarifa).quantize(Decimal("0.01"))
            total      = subtotal + impuesto

            for col, val in [(5, subtotal), (6, impuesto), (7, total)]:
                it = self.tbl.item(row, col)
                if it:
                    it.setText(f"{val:,.2f}")
        except Exception:
            pass
        self.tbl.blockSignals(False)
        self._actualizar_totales()

    def _actualizar_totales(self):
        sub = Decimal("0"); imp = Decimal("0"); tot = Decimal("0")
        for r in range(self.tbl.rowCount()):
            try:
                sub += Decimal(self.tbl.item(r, 5).text().replace(",", "") or "0")
                imp += Decimal(self.tbl.item(r, 6).text().replace(",", "") or "0")
                tot += Decimal(self.tbl.item(r, 7).text().replace(",", "") or "0")
            except Exception:
                pass
        self.lbl_subtotal.setText(f"Subtotal: {_fmt(sub)}")
        self.lbl_iva.setText(f"Impuesto: {_fmt(imp)}")
        self.lbl_total.setText(f"TOTAL: {_fmt(tot)}")

    def _guardar(self, emitir: bool):
        if not self.tercero_sw.get_tercero():
            QMessageBox.warning(self, "Falta tercero",
                                "Selecciona un cliente o proveedor.")
            return

        lineas = []
        for r in range(self.tbl.rowCount()):
            desc_item = self.tbl.item(r, 0)
            if not desc_item or not desc_item.text().strip():
                continue
            meta = desc_item.data(Qt.ItemDataRole.UserRole) or {}
            try:
                cantidad = Decimal(self.tbl.item(r, 2).text().replace(",", ".") or "0")
                precio   = Decimal(self.tbl.item(r, 3).text().replace(",", ".") or "0")
                desc_pct = Decimal(self.tbl.item(r, 4).text().replace(",", ".") or "0") / 100
            except InvalidOperation:
                QMessageBox.warning(self, "Valor inválido", f"Fila {r+1}: valor numérico inválido.")
                return

            und_cb = self.tbl.cellWidget(r, 1)
            lineas.append({
                "producto_id":     meta.get("producto_id"),
                "descripcion":     desc_item.text().strip(),
                "unidad_medida":   und_cb.currentData() if und_cb else UnidadMedida.UNIDAD,
                "cantidad":        cantidad,
                "precio_unitario": precio,
                "descuento_pct":   desc_pct,
                "tipo_impuesto":   meta.get("tipo_impuesto", TipoImpuesto.NINGUNO),
                "tarifa_impuesto": Decimal(str(meta.get("tarifa_impuesto", 0) or 0)),
            })

        if not lineas:
            QMessageBox.warning(self, "Sin líneas", "Agrega al menos una línea con descripción.")
            return

        qd1 = self.de_fecha.date(); qd2 = self.de_vence.date()
        try:
            doc = self.service.crear_documento(
                tipo        = self.tipo,
                fecha       = date(qd1.year(), qd1.month(), qd1.day()),
                tercero_id  = self.tercero_sw.get_tercero().id,
                lineas      = lineas,
                observaciones = self.f_obs.text().strip(),
                fecha_vence = date(qd2.year(), qd2.month(), qd2.day()),
            )
            if emitir:
                self.service.emitir(doc.id)
            self._id_guardado = doc.id
            QMessageBox.information(
                self, "Documento guardado",
                f"✅ {TIPOS_DOC_LABELS[self.tipo]} {doc.numero} "
                f"{'emitida' if emitir else 'guardada como borrador'} correctamente.\n"
                f"Total: {_fmt(doc.total)}"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab: Documentos (Ventas / Compras)
# ══════════════════════════════════════════════════════════════
class TabDocumentos(QWidget):
    def __init__(self, service: FacturacionService,
                 tipos: list, titulo: str, parent=None):
        super().__init__(parent)
        self.service = service
        self.tipos   = tipos
        self.titulo  = titulo
        self._docs   = []
        self._build_ui(); self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(10)
        tb = QHBoxLayout()

        self.cb_tipo = QComboBox(); self.cb_tipo.setFixedWidth(200)
        self.cb_tipo.addItem("Todos los tipos", None)
        for t in self.tipos:
            self.cb_tipo.addItem(TIPOS_DOC_LABELS.get(t, t.value), t)
        self.cb_tipo.currentIndexChanged.connect(self._cargar)

        self.cb_estado = QComboBox(); self.cb_estado.setFixedWidth(120)
        self.cb_estado.addItem("Todos", None)
        self.cb_estado.addItem("Borrador", EstadoDocumento.BORRADOR)
        self.cb_estado.addItem("Emitido",  EstadoDocumento.EMITIDO)
        self.cb_estado.addItem("Anulado",  EstadoDocumento.ANULADO)
        self.cb_estado.currentIndexChanged.connect(self._cargar)

        btn_nuevo = QPushButton(f"+ Nuevo")
        btn_nuevo.setStyleSheet(BTN_PRIMARY); btn_nuevo.clicked.connect(self._nuevo)
        self.btn_emitir = QPushButton("✅ Emitir")
        self.btn_emitir.setStyleSheet(BTN_SUCCESS); self.btn_emitir.setEnabled(False)
        self.btn_emitir.clicked.connect(self._emitir)
        self.btn_anular = QPushButton("🚫 Anular")
        self.btn_anular.setStyleSheet(BTN_DANGER); self.btn_anular.setEnabled(False)
        self.btn_anular.clicked.connect(self._anular)
        btn_ref = QPushButton("🔄"); btn_ref.setFixedWidth(36)
        btn_ref.clicked.connect(self._cargar)

        tb.addWidget(QLabel("Tipo:")); tb.addWidget(self.cb_tipo)
        tb.addWidget(QLabel("Estado:")); tb.addWidget(self.cb_estado)
        tb.addStretch()
        tb.addWidget(btn_nuevo); tb.addWidget(self.btn_emitir)
        tb.addWidget(self.btn_anular); tb.addWidget(btn_ref)
        lay.addLayout(tb)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(
            ["Número", "Tipo", "Fecha", "Tercero", "Subtotal", "Total", "Estado"])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 110); self.tabla.setColumnWidth(1, 140)
        self.tabla.setColumnWidth(2, 95);  self.tabla.setColumnWidth(4, 110)
        self.tabla.setColumnWidth(5, 110); self.tabla.setColumnWidth(6, 90)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        splitter.addWidget(self.tabla)

        # Detalle de líneas
        grp = QGroupBox("Líneas del documento seleccionado")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl = QVBoxLayout(grp)
        self.tbl_lin = QTableWidget(0, 5)
        self.tbl_lin.setHorizontalHeaderLabels(
            ["Descripción", "Cantidad", "Precio unit.", "Impuesto", "Total línea"])
        self.tbl_lin.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_lin.setColumnWidth(1, 80); self.tbl_lin.setColumnWidth(2, 110)
        self.tbl_lin.setColumnWidth(3, 90); self.tbl_lin.setColumnWidth(4, 110)
        self.tbl_lin.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_lin.verticalHeader().setVisible(False)
        self.tbl_lin.setAlternatingRowColors(False)
        gl.addWidget(self.tbl_lin)
        splitter.addWidget(grp)
        splitter.setSizes([320, 200])
        lay.addWidget(splitter)

    def _cargar(self):
        self.service.db.expire_all()
        tipo   = self.cb_tipo.currentData()
        estado = self.cb_estado.currentData()
        self._docs = self.service.listar_documentos(tipo=tipo, estado=estado)
        self.tabla.setRowCount(0)
        for d in self._docs:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            num_item = QTableWidgetItem(d.numero)
            num_item.setData(Qt.ItemDataRole.UserRole, d.id)
            self.tabla.setItem(r, 0, num_item)
            self.tabla.setItem(r, 1, QTableWidgetItem(TIPOS_DOC_LABELS.get(d.tipo, "")))
            self.tabla.setItem(r, 2, QTableWidgetItem(str(d.fecha)))
            nombre_t = d.tercero.nombre if d.tercero else "—"
            self.tabla.setItem(r, 3, QTableWidgetItem(nombre_t))
            for col, val in [(4, d.subtotal), (5, d.total)]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabla.setItem(r, col, it)
            estado_v = d.estado.value if hasattr(d.estado, "value") else d.estado
            est_str  = {"borrador": "Borrador", "emitido": "Emitido",
                        "anulado": "Anulado"}.get(estado_v, estado_v)
            est_item = QTableWidgetItem(est_str)
            fg, bg = ESTADO_COLOR.get(estado_v, ("#374151", "#f8fafc"))
            est_item.setForeground(QColor(fg)); est_item.setBackground(QColor(bg))
            self.tabla.setItem(r, 6, est_item)

        self.btn_emitir.setEnabled(False); self.btn_anular.setEnabled(False)
        self.tbl_lin.setRowCount(0)

    def _on_sel(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        doc_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        doc = self.service.obtener_documento(doc_id)
        if not doc:
            return

        estado_v = doc.estado.value if hasattr(doc.estado, "value") else doc.estado
        self.btn_emitir.setEnabled(estado_v == "borrador")
        self.btn_anular.setEnabled(estado_v != "anulado")

        self.tbl_lin.setRowCount(0)
        for lin in doc.lineas:
            r = self.tbl_lin.rowCount(); self.tbl_lin.insertRow(r)
            self.tbl_lin.setItem(r, 0, QTableWidgetItem(lin.descripcion))
            self.tbl_lin.setItem(r, 1, QTableWidgetItem(str(lin.cantidad)))
            for col, val in [(2, lin.precio_unitario), (3, lin.valor_impuesto), (4, lin.total_linea)]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_lin.setItem(r, col, it)

    def _nuevo(self):
        # Si hay varios tipos, preguntar cuál
        tipo = self.tipos[0] if len(self.tipos) == 1 else self._elegir_tipo()
        if not tipo:
            return
        dlg = DialogDocumento(self.service, tipo, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._cargar()

    def _elegir_tipo(self) -> TipoDocumento:
        dlg = QDialog(self); dlg.setWindowTitle("Tipo de documento")
        dlg.setFixedSize(280, 200)
        dlay = QVBoxLayout(dlg)
        cb = QComboBox()
        for t in self.tipos:
            cb.addItem(TIPOS_DOC_LABELS.get(t, t.value), t)
        dlay.addWidget(QLabel("Selecciona el tipo de documento:"))
        dlay.addWidget(cb)
        btns2 = QHBoxLayout(); btns2.addStretch()
        btn_ok = QPushButton("Aceptar"); btn_ok.setStyleSheet(BTN_PRIMARY)
        btn_ok.clicked.connect(dlg.accept)
        btns2.addWidget(QPushButton("Cancelar", clicked=dlg.reject)); btns2.addWidget(btn_ok)
        dlay.addLayout(btns2)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return cb.currentData()
        return None

    def _emitir(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        doc_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        numero = self.tabla.item(fila, 0).text()
        if QMessageBox.question(self, "Emitir", f"¿Emitir el documento {numero}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                self.service.emitir(doc_id); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _anular(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        doc_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        numero = self.tabla.item(fila, 0).text()
        if QMessageBox.question(self, "Anular", f"¿Anular el documento {numero}?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                self.service.anular(doc_id); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self): self._cargar()


# ══════════════════════════════════════════════════════════════
# Widget principal: Módulo Facturación
# ══════════════════════════════════════════════════════════════
class FacturacionWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        self.service = FacturacionService(self.session, empresa_id)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)

        titulo = QLabel("🧾  Facturación")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        lay.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 20px;font-size:13px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#2563eb;}"
        )

        self.tab_ventas   = TabDocumentos(
            self.service,
            tipos  = [TipoDocumento.FACTURA_VENTA, TipoDocumento.NOTA_CREDITO_VENTA,
                      TipoDocumento.NOTA_DEBITO_VENTA, TipoDocumento.COTIZACION,
                      TipoDocumento.REMISION],
            titulo = "Ventas"
        )
        self.tab_compras  = TabDocumentos(
            self.service,
            tipos  = [TipoDocumento.FACTURA_COMPRA, TipoDocumento.NOTA_CREDITO_COMPRA,
                      TipoDocumento.NOTA_DEBITO_COMPRA, TipoDocumento.ORDEN_COMPRA],
            titulo = "Compras"
        )
        self.tab_productos = TabProductos(self.service)

        self.tabs.addTab(self.tab_ventas,    "📤 Ventas")
        self.tabs.addTab(self.tab_compras,   "📥 Compras")
        self.tabs.addTab(self.tab_productos, "📦 Productos / Servicios")

        self.tabs.currentChanged.connect(self._on_tab)
        lay.addWidget(self.tabs)

    def _on_tab(self, index):
        self.session.expire_all()

    def closeEvent(self, event):
        self.session.close(); super().closeEvent(event)
