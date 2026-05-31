from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QComboBox, QCheckBox, QFrame,
    QTabWidget, QSplitter, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from core.models.terceros import TipoDocumento
from modules.terceros.service import TercerosService

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_DANGER  = "color:#dc2626;border:1px solid #dc2626;padding:4px 10px;border-radius:5px;"

TIPOS_DOC = [
    ("Cédula de Ciudadanía", TipoDocumento.CC),
    ("Cédula de Extranjería", TipoDocumento.CE),
    ("NIT",                   TipoDocumento.NIT),
    ("Pasaporte",             TipoDocumento.PA),
    ("Tarjeta de Identidad",  TipoDocumento.TI),
]

TIPO_LABELS = {
    TipoDocumento.CC:  "C.C.",
    TipoDocumento.CE:  "C.E.",
    TipoDocumento.NIT: "NIT",
    TipoDocumento.PA:  "Pasaporte",
    TipoDocumento.TI:  "T.I.",
}


# ══════════════════════════════════════════════════════════════
# Diálogo: Crear / Editar Tercero
# ══════════════════════════════════════════════════════════════
class DialogTercero(QDialog):
    def __init__(self, parent=None, tercero=None):
        super().__init__(parent)
        self.tercero = tercero
        self.setWindowTitle("Nuevo tercero" if not tercero else "Editar tercero")
        self.setMinimumWidth(520)
        self._build_ui()
        if tercero:
            self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)

        # ── Identificación ─────────────────────────────────────
        grp_id = QGroupBox("Identificación")
        grp_id.setStyleSheet("QGroupBox{font-weight:bold;}")
        f_id = QFormLayout(grp_id)
        f_id.setSpacing(8)

        self.cb_tipo_doc = QComboBox()
        for label, val in TIPOS_DOC:
            self.cb_tipo_doc.addItem(label, val)

        doc_row = QHBoxLayout()
        self.f_doc = QLineEdit()
        self.f_doc.setPlaceholderText("Número de documento")
        self.f_dv  = QLineEdit()
        self.f_dv.setPlaceholderText("DV")
        self.f_dv.setFixedWidth(48)
        self.f_dv.setMaxLength(1)
        self.lbl_dv = QLabel("-")
        self.lbl_dv.setFixedWidth(10)
        self.lbl_dv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        doc_row.addWidget(self.f_doc, 1)
        doc_row.addWidget(self.lbl_dv)
        doc_row.addWidget(self.f_dv)
        self.cb_tipo_doc.currentIndexChanged.connect(self._on_tipo_doc_changed)

        self.f_nombre = QLineEdit()
        self.f_nombre.setPlaceholderText("Nombre completo o razón social")

        f_id.addRow("Tipo documento *:", self.cb_tipo_doc)
        f_id.addRow("Documento *:",      doc_row)
        f_id.addRow("Nombre *:",         self.f_nombre)
        lay.addWidget(grp_id)

        # ── Clasificación ──────────────────────────────────────
        grp_tipo = QGroupBox("Clasificación del tercero")
        grp_tipo.setStyleSheet("QGroupBox{font-weight:bold;}")
        t_lay = QHBoxLayout(grp_tipo)
        self.chk_cliente    = QCheckBox("🛒  Cliente")
        self.chk_proveedor  = QCheckBox("📦  Proveedor")
        self.chk_empleado   = QCheckBox("👷  Empleado")
        for chk in (self.chk_cliente, self.chk_proveedor, self.chk_empleado):
            chk.setStyleSheet("font-size:13px; padding:4px 12px;")
            t_lay.addWidget(chk)
        t_lay.addStretch()
        lay.addWidget(grp_tipo)

        # ── Contacto ───────────────────────────────────────────
        grp_ctc = QGroupBox("Datos de contacto")
        grp_ctc.setStyleSheet("QGroupBox{font-weight:bold;}")
        f_ctc = QFormLayout(grp_ctc)
        f_ctc.setSpacing(8)
        self.f_email    = QLineEdit(); self.f_email.setPlaceholderText("correo@ejemplo.com")
        self.f_telefono = QLineEdit(); self.f_telefono.setPlaceholderText("Teléfono")
        self.f_dir      = QLineEdit(); self.f_dir.setPlaceholderText("Dirección")
        self.f_ciudad   = QLineEdit(); self.f_ciudad.setPlaceholderText("Ciudad")
        f_ctc.addRow("Email:",     self.f_email)
        f_ctc.addRow("Teléfono:", self.f_telefono)
        f_ctc.addRow("Dirección:", self.f_dir)
        f_ctc.addRow("Ciudad:",    self.f_ciudad)
        lay.addWidget(grp_ctc)

        # ── Botones ────────────────────────────────────────────
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Guardar" if self.tercero else "Crear tercero")
        self.btn_ok.setDefault(True)
        self.btn_ok.setStyleSheet(BTN_PRIMARY)
        self.btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_ok)
        lay.addLayout(btns)

        self._on_tipo_doc_changed()

    def _on_tipo_doc_changed(self):
        es_nit = self.cb_tipo_doc.currentData() == TipoDocumento.NIT
        self.f_dv.setVisible(es_nit)
        self.lbl_dv.setVisible(es_nit)

    def _cargar(self):
        t = self.tercero
        # tipo doc
        for i in range(self.cb_tipo_doc.count()):
            if self.cb_tipo_doc.itemData(i) == t.tipo_documento:
                self.cb_tipo_doc.setCurrentIndex(i)
                break
        self.f_doc.setText(t.numero_documento or "")
        self.f_nombre.setText(t.nombre         or "")
        self.f_email.setText(t.email           or "")
        self.f_telefono.setText(t.telefono     or "")
        self.f_dir.setText(t.direccion         or "")
        self.f_ciudad.setText(t.ciudad         or "")
        self.chk_cliente.setChecked(bool(t.es_cliente))
        self.chk_proveedor.setChecked(bool(t.es_proveedor))
        self.chk_empleado.setChecked(bool(t.es_empleado))

    def _guardar(self):
        if not self.f_nombre.text().strip():
            QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
            return
        if not self.f_doc.text().strip():
            QMessageBox.warning(self, "Requerido", "El número de documento es obligatorio.")
            return
        if not (self.chk_cliente.isChecked() or
                self.chk_proveedor.isChecked() or
                self.chk_empleado.isChecked()):
            QMessageBox.warning(self, "Clasificación",
                                "Marca al menos un tipo: Cliente, Proveedor o Empleado.")
            return
        self.accept()

    def datos(self) -> dict:
        doc = self.f_doc.text().strip()
        tipo = self.cb_tipo_doc.currentData()
        if tipo == TipoDocumento.NIT and self.f_dv.text().strip():
            doc = f"{doc}-{self.f_dv.text().strip()}"
        return {
            "tipo_documento":   tipo,
            "numero_documento": doc,
            "nombre":           self.f_nombre.text().strip(),
            "email":            self.f_email.text().strip()    or None,
            "telefono":         self.f_telefono.text().strip() or None,
            "direccion":        self.f_dir.text().strip()      or None,
            "ciudad":           self.f_ciudad.text().strip()   or None,
            "es_cliente":       self.chk_cliente.isChecked(),
            "es_proveedor":     self.chk_proveedor.isChecked(),
            "es_empleado":      self.chk_empleado.isChecked(),
        }


# ══════════════════════════════════════════════════════════════
# Widget principal: Módulo Terceros
# ══════════════════════════════════════════════════════════════
class TercerosWidget(QWidget):

    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.empresa_id = empresa_id
        self.session    = SessionLocal()
        self.service    = TercerosService(self.session, empresa_id)
        self._terceros  = []
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Título ─────────────────────────────────────────────
        titulo = QLabel("👥  Terceros")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b;")
        root.addWidget(titulo)

        # ── Barra de herramientas ──────────────────────────────
        tb = QHBoxLayout()

        self.f_buscar = QLineEdit()
        self.f_buscar.setPlaceholderText("🔍  Buscar por nombre o documento...")
        self.f_buscar.setFixedHeight(32)
        self.f_buscar.textChanged.connect(self._on_buscar)
        self._timer_buscar = QTimer()
        self._timer_buscar.setSingleShot(True)
        self._timer_buscar.setInterval(250)
        self._timer_buscar.timeout.connect(self._cargar)

        # Filtros rápidos
        self.chk_f_cliente   = QCheckBox("Clientes")
        self.chk_f_proveedor = QCheckBox("Proveedores")
        self.chk_f_empleado  = QCheckBox("Empleados")
        for chk in (self.chk_f_cliente, self.chk_f_proveedor, self.chk_f_empleado):
            chk.toggled.connect(self._cargar)

        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet("color:#64748b; font-size:12px;")

        btn_nuevo  = QPushButton("+ Nuevo tercero")
        btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.setFixedHeight(32)
        btn_nuevo.clicked.connect(self._nuevo)

        self.btn_editar = QPushButton("✏️ Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.setFixedHeight(32)
        self.btn_editar.clicked.connect(self._editar)

        self.btn_eliminar = QPushButton("🗑️ Eliminar")
        self.btn_eliminar.setEnabled(False)
        self.btn_eliminar.setFixedHeight(32)
        self.btn_eliminar.setStyleSheet(BTN_DANGER)
        self.btn_eliminar.clicked.connect(self._eliminar)

        tb.addWidget(self.f_buscar, stretch=1)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#e2e8f0;"); tb.addWidget(sep)
        tb.addWidget(QLabel("Filtrar:"))
        tb.addWidget(self.chk_f_cliente)
        tb.addWidget(self.chk_f_proveedor)
        tb.addWidget(self.chk_f_empleado)
        tb.addWidget(self.lbl_total)
        tb.addStretch()
        tb.addWidget(btn_nuevo)
        tb.addWidget(self.btn_editar)
        tb.addWidget(self.btn_eliminar)
        root.addLayout(tb)

        # ── Splitter: tabla + detalle ──────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tabla principal
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Tipo doc.", "Documento", "Nombre", "Cliente", "Proveedor", "Empleado"]
        )
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 100)
        self.tabla.setColumnWidth(1, 130)
        self.tabla.setColumnWidth(3, 70)
        self.tabla.setColumnWidth(4, 80)
        self.tabla.setColumnWidth(5, 75)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        self.tabla.itemDoubleClicked.connect(lambda _: self._editar())
        splitter.addWidget(self.tabla)

        # Panel de detalle
        panel = QWidget()
        panel.setStyleSheet("background:#f8fafc;")
        panel.setMinimumWidth(280)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.setSpacing(8)

        self.lbl_det_titulo = QLabel("Selecciona un tercero")
        self.lbl_det_titulo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_det_titulo.setStyleSheet("color:#1e293b;")
        self.lbl_det_titulo.setWordWrap(True)
        pl.addWidget(self.lbl_det_titulo)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#e2e8f0;"); pl.addWidget(sep2)

        self.txt_detalle = QTextEdit()
        self.txt_detalle.setReadOnly(True)
        self.txt_detalle.setStyleSheet(
            "background:white; border:1px solid #e2e8f0; border-radius:6px; "
            "font-size:12px; padding:6px;"
        )
        pl.addWidget(self.txt_detalle, stretch=1)

        lbl_tags = QLabel("Clasificación:")
        lbl_tags.setStyleSheet("color:#64748b; font-size:11px; font-weight:bold;")
        pl.addWidget(lbl_tags)

        self.lbl_badges = QLabel()
        self.lbl_badges.setWordWrap(True)
        self.lbl_badges.setStyleSheet("font-size:12px;")
        pl.addWidget(self.lbl_badges)

        splitter.addWidget(panel)
        splitter.setSizes([700, 300])
        root.addWidget(splitter)

    # ── Datos ──────────────────────────────────────────────────
    def _cargar(self):
        criterio = self.f_buscar.text().strip()
        self._terceros = self.service.listar(
            criterio        = criterio,
            solo_clientes   = self.chk_f_cliente.isChecked(),
            solo_proveedores= self.chk_f_proveedor.isChecked(),
            solo_empleados  = self.chk_f_empleado.isChecked(),
        )
        self._renderizar()

    def _renderizar(self):
        self.tabla.setRowCount(0)
        for t in self._terceros:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)

            tipo_str = TIPO_LABELS.get(t.tipo_documento, str(t.tipo_documento))
            item_tipo = QTableWidgetItem(tipo_str)
            item_tipo.setData(Qt.ItemDataRole.UserRole, t.id)

            self.tabla.setItem(r, 0, item_tipo)
            self.tabla.setItem(r, 1, QTableWidgetItem(t.numero_documento or ""))
            self.tabla.setItem(r, 2, QTableWidgetItem(t.nombre or ""))

            for col, val in [(3, t.es_cliente), (4, t.es_proveedor), (5, t.es_empleado)]:
                item = QTableWidgetItem("✔" if val else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if val:
                    item.setForeground(QColor("#16a34a"))
                self.tabla.setItem(r, col, item)

        self.lbl_total.setText(f"{len(self._terceros)} registros")
        self.btn_editar.setEnabled(False)
        self.btn_eliminar.setEnabled(False)
        self._limpiar_detalle()

    def _on_buscar(self):
        self._timer_buscar.start()

    def _on_sel(self):
        fila = self.tabla.currentRow()
        tiene = fila >= 0 and bool(self.tabla.selectedItems())
        self.btn_editar.setEnabled(tiene)
        self.btn_eliminar.setEnabled(tiene)
        if tiene:
            tercero_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
            tercero = next((t for t in self._terceros if t.id == tercero_id), None)
            if tercero:
                self._mostrar_detalle(tercero)
        else:
            self._limpiar_detalle()

    def _mostrar_detalle(self, t):
        self.lbl_det_titulo.setText(t.nombre)

        lineas = []
        tipo_str = TIPO_LABELS.get(t.tipo_documento, "")
        lineas.append(f"<b>{tipo_str}:</b> {t.numero_documento}")
        if t.email:
            lineas.append(f"<b>Email:</b> {t.email}")
        if t.telefono:
            lineas.append(f"<b>Teléfono:</b> {t.telefono}")
        if t.direccion:
            lineas.append(f"<b>Dirección:</b> {t.direccion}")
        if t.ciudad:
            lineas.append(f"<b>Ciudad:</b> {t.ciudad}")
        self.txt_detalle.setHtml("<br>".join(lineas))

        badges = []
        if t.es_cliente:
            badges.append("<span style='background:#dbeafe;color:#1d4ed8;"
                          "padding:2px 8px;border-radius:10px;'>🛒 Cliente</span>")
        if t.es_proveedor:
            badges.append("<span style='background:#dcfce7;color:#15803d;"
                          "padding:2px 8px;border-radius:10px;'>📦 Proveedor</span>")
        if t.es_empleado:
            badges.append("<span style='background:#fef9c3;color:#854d0e;"
                          "padding:2px 8px;border-radius:10px;'>👷 Empleado</span>")
        self.lbl_badges.setText("  ".join(badges))

    def _limpiar_detalle(self):
        self.lbl_det_titulo.setText("Selecciona un tercero")
        self.lbl_det_titulo.setStyleSheet("color:#94a3b8;")
        self.txt_detalle.clear()
        self.lbl_badges.clear()

    # ── CRUD ───────────────────────────────────────────────────
    def _nuevo(self):
        dlg = DialogTercero(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                t = self.service.crear(dlg.datos())
                self._cargar()
                QMessageBox.information(
                    self, "Tercero creado",
                    f"✅ {t.nombre} creado correctamente."
                )
            except ValueError as e:
                QMessageBox.warning(self, "Error de validación", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _editar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        tercero_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        tercero = self.service.obtener(tercero_id)
        if not tercero:
            return
        dlg = DialogTercero(self, tercero=tercero)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar(tercero_id, dlg.datos())
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _eliminar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        nombre = self.tabla.item(fila, 2).text()
        tercero_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        resp = QMessageBox.question(
            self, "Confirmar",
            f"¿Desactivar a '{nombre}'?\nNo se eliminará permanentemente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.service.desactivar(tercero_id)
            self._cargar()

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)
