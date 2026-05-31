from decimal import Decimal, InvalidOperation
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QComboBox, QFrame, QTabWidget,
    QSplitter, QDateEdit, QDoubleSpinBox, QTextEdit,
    QCheckBox, QListWidget, QListWidgetItem, QSizePolicy,
    QFileDialog
)
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from core.models.tesoreria import (
    TipoCuenta, TipoTransaccion, EstadoConciliacion
)
from modules.tesoreria.service import TesoreriaService

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_SUCCESS = "background:#059669;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_DANGER  = "color:#dc2626;border:1px solid #fca5a5;padding:4px 10px;border-radius:5px;"
BTN_WARN    = "background:#d97706;color:white;padding:5px 12px;border-radius:5px;"

TIPO_CUENTA_LABELS = {
    TipoCuenta.CAJA:     "💵 Caja",
    TipoCuenta.BANCO:    "🏦 Banco",
    TipoCuenta.BOLSILLO: "👛 Fondo menor",
}

TIPO_TXN_LABELS = {
    TipoTransaccion.INGRESO:   ("📥 Ingreso",  "#15803d", "#dcfce7"),
    TipoTransaccion.EGRESO:    ("📤 Egreso",   "#b91c1c", "#fee2e2"),
    TipoTransaccion.TRASLADO:  ("🔄 Traslado", "#1d4ed8", "#dbeafe"),
}


def _fmt(v) -> str:
    try:
        return f"${Decimal(str(v)):,.2f}"
    except Exception:
        return "$0.00"


# ══════════════════════════════════════════════════════════════
# Widget búsqueda de tercero (inline, sin ventana flotante)
# ══════════════════════════════════════════════════════════════
class TerceroInlineSearch(QWidget):
    tercero_sel = pyqtSignal(object)

    def __init__(self, service: TesoreriaService, parent=None):
        super().__init__(parent)
        self.service  = service
        self._tercero = None
        self._sel     = False
        self._frame   = None
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Buscar tercero (opcional)...")
        self.edit.textChanged.connect(self._on_text)
        lay.addWidget(self.edit)
        self._timer = QTimer(); self._timer.setSingleShot(True)
        self._timer.setInterval(200); self._timer.timeout.connect(self._buscar)

    def _popup(self):
        if self._frame: return self._frame
        top = self.window()
        f = QFrame(top)
        f.setStyleSheet("QFrame{border:2px solid #2563eb;background:white;border-radius:4px;}")
        f.hide()
        fl = QVBoxLayout(f); fl.setContentsMargins(0,0,0,0)
        lst = QListWidget()
        lst.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lst.setStyleSheet(
            "QListWidget{border:none;background:white;font-size:12px;color:#111;}"
            "QListWidget::item{color:#111;padding:4px 8px;}"
            "QListWidget::item:hover{background:#eff6ff;}"
        )
        lst.itemClicked.connect(self._on_click)
        fl.addWidget(lst); f._lista = lst
        self._frame = f; return f

    def _on_text(self, text):
        if self._sel: return
        if not text.strip():
            self._tercero = None; self.edit.setStyleSheet("")
            if self._frame: self._frame.hide()
            return
        self._timer.start()

    def _buscar(self):
        texto = self.edit.text().strip()
        if not texto: return
        resultados = self.service.buscar_terceros(texto)
        p = self._popup(); p._lista.clear()
        if not resultados: p.hide(); return
        for t in resultados:
            item = QListWidgetItem(f"{t.numero_documento}  —  {t.nombre}")
            item.setForeground(QColor("#111111"))
            item.setData(Qt.ItemDataRole.UserRole, t)
            p._lista.addItem(item)
        top = self.window()
        gp  = self.edit.mapToGlobal(self.edit.rect().bottomLeft())
        lp  = top.mapFromGlobal(gp)
        p.setGeometry(lp.x(), lp.y(), max(self.edit.width(), 360),
                      min(len(resultados)*28+4, 220))
        p.raise_(); p.show()

    def _on_click(self, item):
        t = item.data(Qt.ItemDataRole.UserRole)
        self._tercero = t; self._sel = True
        self.edit.setText(f"{t.numero_documento}  —  {t.nombre}")
        self.edit.setStyleSheet("border:1px solid #16a34a;color:#111;")
        self._sel = False; self._frame.hide()
        self.tercero_sel.emit(t)

    def get_tercero(self): return self._tercero
    def reset(self):
        self._sel = True; self.edit.clear()
        self._sel = False; self.edit.setStyleSheet("")
        self._tercero = None
        if self._frame: self._frame.hide()
    def hideEvent(self, e):
        if self._frame: self._frame.hide()
        super().hideEvent(e)


# ══════════════════════════════════════════════════════════════
# Diálogo: Crear / Editar Cuenta de Tesorería
# ══════════════════════════════════════════════════════════════
class DialogCuenta(QDialog):
    def __init__(self, parent=None, cuenta=None):
        super().__init__(parent)
        self.cuenta = cuenta
        self.setWindowTitle("Nueva cuenta" if not cuenta else "Editar cuenta")
        self.setMinimumWidth(460)
        self._build_ui()
        if cuenta: self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12)

        grp1 = QGroupBox("Identificación")
        grp1.setStyleSheet("QGroupBox{font-weight:bold;}")
        f1 = QFormLayout(grp1); f1.setSpacing(8)
        self.f_nombre = QLineEdit()
        self.cb_tipo  = QComboBox()
        for tipo, label in TIPO_CUENTA_LABELS.items():
            self.cb_tipo.addItem(label, tipo)
        self.cb_tipo.currentIndexChanged.connect(self._on_tipo_changed)
        f1.addRow("Nombre *:", self.f_nombre)
        f1.addRow("Tipo *:",   self.cb_tipo)
        lay.addWidget(grp1)

        self.grp_banco = QGroupBox("Datos bancarios")
        self.grp_banco.setStyleSheet("QGroupBox{font-weight:bold;}")
        f2 = QFormLayout(self.grp_banco); f2.setSpacing(8)
        self.f_banco      = QLineEdit(); self.f_banco.setPlaceholderText("Ej: Bancolombia, Davivienda")
        self.f_num_cuenta = QLineEdit(); self.f_num_cuenta.setPlaceholderText("Número de cuenta")
        self.cb_tipo_cta  = QComboBox()
        self.cb_tipo_cta.addItems(["Ahorros", "Corriente"])
        f2.addRow("Banco:",          self.f_banco)
        f2.addRow("No. Cuenta:",     self.f_num_cuenta)
        f2.addRow("Tipo de cuenta:", self.cb_tipo_cta)
        lay.addWidget(self.grp_banco)

        grp3 = QGroupBox("Saldo")
        grp3.setStyleSheet("QGroupBox{font-weight:bold;}")
        f3 = QFormLayout(grp3); f3.setSpacing(8)
        self.spin_saldo = QDoubleSpinBox()
        self.spin_saldo.setRange(-999_999_999, 999_999_999)
        self.spin_saldo.setDecimals(2); self.spin_saldo.setPrefix("$ ")
        self.spin_saldo.setSingleStep(10000)
        f3.addRow("Saldo inicial:", self.spin_saldo)
        if self.cuenta:
            nota = QLabel("ℹ️  El saldo inicial no se puede modificar. "
                          "Los movimientos ajustan el saldo automáticamente.")
            nota.setStyleSheet("color:#64748b;font-size:11px;"); nota.setWordWrap(True)
            f3.addRow("", nota)
            self.spin_saldo.setEnabled(False)
        lay.addWidget(grp3)

        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)
        self._on_tipo_changed()

    def _on_tipo_changed(self):
        es_banco = self.cb_tipo.currentData() == TipoCuenta.BANCO
        self.grp_banco.setVisible(es_banco)
        self.adjustSize()

    def _cargar(self):
        c = self.cuenta
        self.f_nombre.setText(c.nombre or "")
        for i in range(self.cb_tipo.count()):
            if self.cb_tipo.itemData(i) == c.tipo:
                self.cb_tipo.setCurrentIndex(i); break
        self.f_banco.setText(c.banco or "")
        self.f_num_cuenta.setText(c.numero_cuenta or "")
        if c.tipo_cuenta_banco:
            idx = self.cb_tipo_cta.findText(c.tipo_cuenta_banco)
            if idx >= 0: self.cb_tipo_cta.setCurrentIndex(idx)
        self.spin_saldo.setValue(float(c.saldo_inicial or 0))

    def _guardar(self):
        if not self.f_nombre.text().strip():
            QMessageBox.warning(self, "Requerido", "El nombre es obligatorio.")
            return
        self.accept()

    def datos(self) -> dict:
        tipo = self.cb_tipo.currentData()
        d = {
            "nombre": self.f_nombre.text().strip(),
            "tipo":   tipo,
        }
        if tipo == TipoCuenta.BANCO:
            d["banco"]             = self.f_banco.text().strip() or None
            d["numero_cuenta"]     = self.f_num_cuenta.text().strip() or None
            d["tipo_cuenta_banco"] = self.cb_tipo_cta.currentText()
        if not self.cuenta:
            saldo = Decimal(str(self.spin_saldo.value()))
            d["saldo_inicial"] = saldo
            d["saldo_actual"]  = saldo
        return d


# ══════════════════════════════════════════════════════════════
# Diálogo: Registrar Transacción (ingreso / egreso / traslado)
# ══════════════════════════════════════════════════════════════
class DialogTransaccion(QDialog):
    def __init__(self, service: TesoreriaService,
                 tipo: TipoTransaccion,
                 cuenta_id: int = None, parent=None):
        super().__init__(parent)
        self.service    = service
        self.tipo       = tipo
        self.cuenta_id  = cuenta_id
        label, _, _     = TIPO_TXN_LABELS[tipo]
        self.setWindowTitle(label)
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12)

        label, color, bg = TIPO_TXN_LABELS[self.tipo]
        titulo = QLabel(label)
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color:{color};")
        lay.addWidget(titulo)

        form = QFormLayout(); form.setSpacing(10)

        # Cuenta origen
        self.cb_cuenta = QComboBox()
        cuentas = self.service.listar_cuentas()
        for c in cuentas:
            tipo_lbl = TIPO_CUENTA_LABELS.get(c.tipo, "")
            self.cb_cuenta.addItem(
                f"{tipo_lbl}  {c.nombre}  ({_fmt(c.saldo_actual)})", c.id)
        if self.cuenta_id:
            for i in range(self.cb_cuenta.count()):
                if self.cb_cuenta.itemData(i) == self.cuenta_id:
                    self.cb_cuenta.setCurrentIndex(i); break

        form.addRow("Cuenta:", self.cb_cuenta)

        # Cuenta destino (solo traslados)
        self.cb_destino = QComboBox()
        for c in cuentas:
            tipo_lbl = TIPO_CUENTA_LABELS.get(c.tipo, "")
            self.cb_destino.addItem(f"{tipo_lbl}  {c.nombre}", c.id)
        self.lbl_destino = QLabel("Cuenta destino:")
        form.addRow(self.lbl_destino, self.cb_destino)
        self.lbl_destino.setVisible(self.tipo == TipoTransaccion.TRASLADO)
        self.cb_destino.setVisible(self.tipo == TipoTransaccion.TRASLADO)

        self.de_fecha = QDateEdit(QDate.currentDate())
        self.de_fecha.setCalendarPopup(True); self.de_fecha.setFixedWidth(130)
        form.addRow("Fecha:", self.de_fecha)

        self.f_concepto = QLineEdit()
        self.f_concepto.setPlaceholderText("Descripción del movimiento...")
        form.addRow("Concepto *:", self.f_concepto)

        self.f_ref = QLineEdit()
        self.f_ref.setPlaceholderText("No. cheque, transferencia, recibo...")
        form.addRow("Referencia:", self.f_ref)

        self.spin_valor = QDoubleSpinBox()
        self.spin_valor.setRange(0.01, 999_999_999_999)
        self.spin_valor.setDecimals(2); self.spin_valor.setPrefix("$ ")
        self.spin_valor.setSingleStep(10000)
        form.addRow("Valor *:", self.spin_valor)

        # Tercero (no aplica en traslados)
        self.tercero_sw = TerceroInlineSearch(self.service)
        self.lbl_tercero = QLabel("Tercero:")
        form.addRow(self.lbl_tercero, self.tercero_sw)
        self.lbl_tercero.setVisible(self.tipo != TipoTransaccion.TRASLADO)
        self.tercero_sw.setVisible(self.tipo != TipoTransaccion.TRASLADO)

        self.f_notas = QTextEdit(); self.f_notas.setFixedHeight(60)
        self.f_notas.setPlaceholderText("Notas adicionales (opcional)...")
        form.addRow("Notas:", self.f_notas)
        lay.addLayout(form)

        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("💾 Guardar")
        btn_ok.setDefault(True); btn_ok.setStyleSheet(BTN_PRIMARY)
        btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def _guardar(self):
        if not self.f_concepto.text().strip():
            QMessageBox.warning(self, "Requerido", "El concepto es obligatorio.")
            return
        if self.spin_valor.value() <= 0:
            QMessageBox.warning(self, "Valor inválido", "El valor debe ser mayor a cero.")
            return
        self.accept()

    def datos(self) -> dict:
        qd = self.de_fecha.date()
        t  = self.tercero_sw.get_tercero()
        return {
            "cuenta_id":          self.cb_cuenta.currentData(),
            "cuenta_destino_id":  self.cb_destino.currentData()
                                  if self.tipo == TipoTransaccion.TRASLADO else None,
            "fecha":              date(qd.year(), qd.month(), qd.day()),
            "concepto":           self.f_concepto.text().strip(),
            "referencia":         self.f_ref.text().strip() or None,
            "valor":              Decimal(str(self.spin_valor.value())),
            "tercero_id":         t.id if t else None,
            "notas":              self.f_notas.toPlainText().strip() or None,
        }


# ══════════════════════════════════════════════════════════════
# Tab 1: Cuentas de Tesorería
# ══════════════════════════════════════════════════════════════
class TabCuentas(QWidget):
    cuenta_seleccionada = pyqtSignal(int)   # emite cuenta_id al hacer clic

    def __init__(self, service: TesoreriaService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui(); self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        # Resumen saldo total
        self.lbl_saldo_total = QLabel()
        self.lbl_saldo_total.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_saldo_total.setStyleSheet("color:#1e293b; background:#f1f5f9; "
                                           "padding:8px 16px; border-radius:8px;")
        lay.addWidget(self.lbl_saldo_total)

        tb = QHBoxLayout()
        btn_nuevo = QPushButton("+ Nueva cuenta"); btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.clicked.connect(self._nuevo)
        self.btn_editar  = QPushButton("✏️ Editar"); self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self._editar)
        self.btn_desact  = QPushButton("🗑️"); self.btn_desact.setEnabled(False)
        self.btn_desact.setStyleSheet(BTN_DANGER); self.btn_desact.clicked.connect(self._desactivar)
        btn_ref = QPushButton("🔄"); btn_ref.setFixedWidth(36); btn_ref.clicked.connect(self._cargar)
        tb.addStretch(); tb.addWidget(btn_nuevo)
        tb.addWidget(self.btn_editar); tb.addWidget(self.btn_desact); tb.addWidget(btn_ref)
        lay.addLayout(tb)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Tipo", "Nombre", "Banco/Info", "Saldo inicial", "Saldo actual"])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 100); self.tabla.setColumnWidth(3, 120); self.tabla.setColumnWidth(4, 130)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        self.tabla.itemDoubleClicked.connect(self._on_doble_clic)
        lay.addWidget(self.tabla)

    def _cargar(self):
        self.service.db.expire_all()
        self.tabla.setRowCount(0)
        cuentas = self.service.listar_cuentas()
        for c in cuentas:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            tipo_lbl = TIPO_CUENTA_LABELS.get(c.tipo, str(c.tipo))
            tipo_item = QTableWidgetItem(tipo_lbl)
            tipo_item.setData(Qt.ItemDataRole.UserRole, c.id)
            self.tabla.setItem(r, 0, tipo_item)
            self.tabla.setItem(r, 1, QTableWidgetItem(c.nombre))
            info = f"{c.banco or ''}  {c.numero_cuenta or ''}".strip()
            self.tabla.setItem(r, 2, QTableWidgetItem(info))
            for col, val in [(3, c.saldo_inicial), (4, c.saldo_actual)]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == 4:
                    col_v = Decimal(str(val or 0))
                    it.setForeground(QColor("#15803d" if col_v >= 0 else "#b91c1c"))
                    it.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                self.tabla.setItem(r, col, it)

        total = self.service.saldo_total()
        self.lbl_saldo_total.setText(f"💰  Saldo total disponible:   {_fmt(total)}")
        self.btn_editar.setEnabled(False); self.btn_desact.setEnabled(False)

    def _on_sel(self):
        tiene = bool(self.tabla.selectedItems())
        self.btn_editar.setEnabled(tiene); self.btn_desact.setEnabled(tiene)

    def _on_doble_clic(self, item):
        cid = self.tabla.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        self.cuenta_seleccionada.emit(cid)

    def _nuevo(self):
        dlg = DialogCuenta(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_cuenta(dlg.datos()); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _editar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        cid   = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        cuenta = self.service.obtener_cuenta(cid)
        dlg   = DialogCuenta(self, cuenta=cuenta)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar_cuenta(cid, dlg.datos()); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _desactivar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        nombre = self.tabla.item(fila, 1).text()
        cid    = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Desactivar", f"¿Desactivar '{nombre}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.service.desactivar_cuenta(cid); self._cargar()

    def refresh(self): self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 2: Movimientos (libro de caja/banco)
# ══════════════════════════════════════════════════════════════
class TabMovimientos(QWidget):
    def __init__(self, service: TesoreriaService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui(); self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        # Filtros
        fil = QHBoxLayout()
        self.cb_cuenta = QComboBox(); self.cb_cuenta.setFixedWidth(260)
        self.cb_cuenta.addItem("Todas las cuentas", None)
        self.cb_tipo = QComboBox(); self.cb_tipo.setFixedWidth(140)
        self.cb_tipo.addItem("Todos los tipos", None)
        for tipo, (label, _, _) in TIPO_TXN_LABELS.items():
            self.cb_tipo.addItem(label, tipo)
        self.de_desde = QDateEdit(); self.de_desde.setCalendarPopup(True)
        self.de_desde.setDate(QDate.currentDate().addDays(-30))
        self.de_desde.setFixedWidth(115)
        self.de_hasta = QDateEdit(QDate.currentDate()); self.de_hasta.setCalendarPopup(True)
        self.de_hasta.setFixedWidth(115)
        btn_fil = QPushButton("🔍 Filtrar"); btn_fil.clicked.connect(self._cargar)
        btn_fil.setStyleSheet(BTN_PRIMARY)

        fil.addWidget(QLabel("Cuenta:")); fil.addWidget(self.cb_cuenta)
        fil.addWidget(QLabel("Tipo:"));   fil.addWidget(self.cb_tipo)
        fil.addWidget(QLabel("Del:"));    fil.addWidget(self.de_desde)
        fil.addWidget(QLabel("Al:"));     fil.addWidget(self.de_hasta)
        fil.addWidget(btn_fil); fil.addStretch()
        lay.addLayout(fil)

        # Botones de acción
        acc = QHBoxLayout()
        btn_ing  = QPushButton("📥 Ingreso"); btn_ing.setStyleSheet(BTN_SUCCESS)
        btn_ing.clicked.connect(lambda: self._nueva_txn(TipoTransaccion.INGRESO))
        btn_egr  = QPushButton("📤 Egreso")
        btn_egr.setStyleSheet("background:#dc2626;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;")
        btn_egr.clicked.connect(lambda: self._nueva_txn(TipoTransaccion.EGRESO))
        btn_tsl  = QPushButton("🔄 Traslado"); btn_tsl.setStyleSheet(BTN_WARN)
        btn_tsl.clicked.connect(lambda: self._nueva_txn(TipoTransaccion.TRASLADO))
        self.btn_anular = QPushButton("🚫 Anular"); self.btn_anular.setStyleSheet(BTN_DANGER)
        self.btn_anular.setEnabled(False); self.btn_anular.clicked.connect(self._anular)
        self.lbl_total_fil = QLabel(); self.lbl_total_fil.setStyleSheet("color:#64748b;font-size:12px;")
        acc.addWidget(btn_ing); acc.addWidget(btn_egr); acc.addWidget(btn_tsl)
        acc.addWidget(self.btn_anular); acc.addStretch(); acc.addWidget(self.lbl_total_fil)
        lay.addLayout(acc)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(
            ["Fecha", "Cuenta", "Tipo", "Concepto", "Referencia", "Tercero", "Valor"])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 90); self.tabla.setColumnWidth(1, 130)
        self.tabla.setColumnWidth(2, 90); self.tabla.setColumnWidth(4, 110)
        self.tabla.setColumnWidth(5, 130); self.tabla.setColumnWidth(6, 120)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(
            lambda: self.btn_anular.setEnabled(bool(self.tabla.selectedItems())))
        lay.addWidget(self.tabla)

    def showEvent(self, event):
        super().showEvent(event)
        self._recargar_cuentas()

    def _recargar_cuentas(self):
        self.cb_cuenta.blockSignals(True)
        self.cb_cuenta.clear()
        self.cb_cuenta.addItem("Todas las cuentas", None)
        for c in self.service.listar_cuentas():
            self.cb_cuenta.addItem(
                f"{TIPO_CUENTA_LABELS.get(c.tipo,'')}  {c.nombre}", c.id)
        self.cb_cuenta.blockSignals(False)

    def _cargar(self):
        self.service.db.expire_all()
        qd1 = self.de_desde.date(); qd2 = self.de_hasta.date()
        txns = self.service.listar_transacciones(
            cuenta_id   = self.cb_cuenta.currentData(),
            tipo        = self.cb_tipo.currentData(),
            fecha_desde = date(qd1.year(), qd1.month(), qd1.day()),
            fecha_hasta = date(qd2.year(), qd2.month(), qd2.day()),
        )
        self.tabla.setRowCount(0)
        total_ing = Decimal("0"); total_egr = Decimal("0")
        for txn in txns:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            id_item = QTableWidgetItem(str(txn.fecha))
            id_item.setData(Qt.ItemDataRole.UserRole, txn.id)
            self.tabla.setItem(r, 0, id_item)
            nombre_cta = txn.cuenta.nombre if txn.cuenta else "—"
            if txn.cuenta_destino:
                nombre_cta += f" → {txn.cuenta_destino.nombre}"
            self.tabla.setItem(r, 1, QTableWidgetItem(nombre_cta))
            tipo_v = txn.tipo.value if hasattr(txn.tipo, "value") else txn.tipo
            label, color, bg = TIPO_TXN_LABELS.get(txn.tipo, (tipo_v, "#374151", "#f8fafc"))
            tipo_item = QTableWidgetItem(label)
            tipo_item.setForeground(QColor(color)); tipo_item.setBackground(QColor(bg))
            self.tabla.setItem(r, 2, tipo_item)
            self.tabla.setItem(r, 3, QTableWidgetItem(txn.concepto or ""))
            self.tabla.setItem(r, 4, QTableWidgetItem(txn.referencia or ""))
            t_nom = txn.tercero.nombre if txn.tercero else ""
            self.tabla.setItem(r, 5, QTableWidgetItem(t_nom))
            val = Decimal(str(txn.valor))
            v_item = QTableWidgetItem(_fmt(val))
            v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v_item.setForeground(QColor(color))
            v_item.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            self.tabla.setItem(r, 6, v_item)
            if txn.tipo == TipoTransaccion.INGRESO: total_ing += val
            elif txn.tipo == TipoTransaccion.EGRESO: total_egr += val
        self.lbl_total_fil.setText(
            f"{len(txns)} movimientos  |  "
            f"Ingresos: {_fmt(total_ing)}  |  "
            f"Egresos: {_fmt(total_egr)}  |  "
            f"Neto: {_fmt(total_ing - total_egr)}"
        )
        self.btn_anular.setEnabled(False)

    def _nueva_txn(self, tipo: TipoTransaccion):
        cid = self.cb_cuenta.currentData()
        dlg = DialogTransaccion(self.service, tipo, cuenta_id=cid, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.datos()
            try:
                if tipo == TipoTransaccion.INGRESO:
                    self.service.registrar_ingreso(**{k:v for k,v in d.items()
                                                      if k != "cuenta_destino_id"})
                elif tipo == TipoTransaccion.EGRESO:
                    self.service.registrar_egreso(**{k:v for k,v in d.items()
                                                     if k != "cuenta_destino_id"})
                else:
                    self.service.registrar_traslado(
                        cuenta_origen_id  = d["cuenta_id"],
                        cuenta_destino_id = d["cuenta_destino_id"],
                        fecha    = d["fecha"],
                        concepto = d["concepto"],
                        valor    = d["valor"],
                        referencia = d.get("referencia"),
                        notas    = d.get("notas"),
                    )
                self._cargar()
            except ValueError as e:
                QMessageBox.warning(self, "Error de validación", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _anular(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        txn_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        concepto = self.tabla.item(fila, 3).text()
        if QMessageBox.question(
            self, "Anular transacción",
            f"¿Anular '{concepto}'?\nSe revertirá el saldo de la cuenta.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                self.service.anular_transaccion(txn_id); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def ir_a_cuenta(self, cuenta_id: int):
        """Filtrar por una cuenta específica (llamado desde TabCuentas)."""
        for i in range(self.cb_cuenta.count()):
            if self.cb_cuenta.itemData(i) == cuenta_id:
                self.cb_cuenta.setCurrentIndex(i); break
        self._cargar()

    def refresh(self):
        self._recargar_cuentas(); self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 3: Conciliación Bancaria
# ══════════════════════════════════════════════════════════════
class TabConciliacion(QWidget):
    def __init__(self, service: TesoreriaService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        # Selección cuenta
        top = QHBoxLayout()
        self.cb_cuenta = QComboBox(); self.cb_cuenta.setFixedWidth(300)
        self.cb_cuenta.currentIndexChanged.connect(self._cargar)
        self.lbl_resumen = QLabel()
        self.lbl_resumen.setStyleSheet("color:#1e293b;font-size:12px;")
        top.addWidget(QLabel("Cuenta bancaria:")); top.addWidget(self.cb_cuenta)
        top.addWidget(self.lbl_resumen); top.addStretch()
        btn_imp = QPushButton("📂 Importar extracto CSV")
        btn_imp.clicked.connect(self._importar_csv)
        top.addWidget(btn_imp)
        lay.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Extracto bancario
        grp_ext = QGroupBox("Extracto bancario (no conciliado)")
        grp_ext.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl = QVBoxLayout(grp_ext)
        self.tbl_extracto = QTableWidget(0, 5)
        self.tbl_extracto.setHorizontalHeaderLabels(
            ["Fecha", "Descripción", "Débito", "Crédito", "Saldo"])
        hh1 = self.tbl_extracto.horizontalHeader()
        hh1.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_extracto.setColumnWidth(0, 90); self.tbl_extracto.setColumnWidth(2, 100)
        self.tbl_extracto.setColumnWidth(3, 100); self.tbl_extracto.setColumnWidth(4, 100)
        self.tbl_extracto.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_extracto.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_extracto.verticalHeader().setVisible(False)
        self.tbl_extracto.setAlternatingRowColors(False)
        gl.addWidget(self.tbl_extracto)
        splitter.addWidget(grp_ext)

        # Movimientos en libros
        grp_lib = QGroupBox("Movimientos en libros (no conciliados)")
        grp_lib.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl2 = QVBoxLayout(grp_lib)
        self.tbl_libros = QTableWidget(0, 4)
        self.tbl_libros.setHorizontalHeaderLabels(["Fecha", "Concepto", "Tipo", "Valor"])
        hh2 = self.tbl_libros.horizontalHeader()
        hh2.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_libros.setColumnWidth(0, 90); self.tbl_libros.setColumnWidth(2, 90)
        self.tbl_libros.setColumnWidth(3, 110)
        self.tbl_libros.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_libros.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_libros.verticalHeader().setVisible(False)
        self.tbl_libros.setAlternatingRowColors(False)
        gl2.addWidget(self.tbl_libros)
        splitter.addWidget(grp_lib)

        splitter.setSizes([500, 400])
        lay.addWidget(splitter)

        btns = QHBoxLayout()
        self.btn_conciliar = QPushButton("✅ Conciliar seleccionados")
        self.btn_conciliar.setStyleSheet(BTN_SUCCESS)
        self.btn_conciliar.clicked.connect(self._conciliar)
        lbl_hint = QLabel("Selecciona una línea del extracto y un movimiento en libros, luego concilia.")
        lbl_hint.setStyleSheet("color:#64748b;font-size:11px;")
        btns.addWidget(self.btn_conciliar); btns.addWidget(lbl_hint); btns.addStretch()
        lay.addLayout(btns)

    def showEvent(self, event):
        super().showEvent(event)
        self._recargar_cuentas()

    def _recargar_cuentas(self):
        self.cb_cuenta.blockSignals(True)
        self.cb_cuenta.clear()
        bancos = [c for c in self.service.listar_cuentas()
                  if c.tipo == TipoCuenta.BANCO]
        if not bancos:
            self.cb_cuenta.addItem("— No hay cuentas bancarias —", None)
        else:
            for c in bancos:
                self.cb_cuenta.addItem(c.nombre, c.id)
        self.cb_cuenta.blockSignals(False)
        self._cargar()

    def _cargar(self):
        self.service.db.expire_all()
        cid = self.cb_cuenta.currentData()
        self.tbl_extracto.setRowCount(0)
        self.tbl_libros.setRowCount(0)
        if not cid: return

        # Extracto
        for le in self.service.listar_extracto(cid, solo_no_conciliado=True):
            r = self.tbl_extracto.rowCount(); self.tbl_extracto.insertRow(r)
            id_item = QTableWidgetItem(str(le.fecha))
            id_item.setData(Qt.ItemDataRole.UserRole, le.id)
            self.tbl_extracto.setItem(r, 0, id_item)
            self.tbl_extracto.setItem(r, 1, QTableWidgetItem(le.descripcion))
            for col, val in [(2, le.debito), (3, le.credito), (4, le.saldo)]:
                it = QTableWidgetItem(_fmt(val) if val else "")
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_extracto.setItem(r, col, it)

        # Libros (movimientos no conciliados de esa cuenta)
        for txn in self.service.listar_transacciones(cuenta_id=cid):
            if txn.conciliacion == EstadoConciliacion.CONCILIADO:
                continue
            r = self.tbl_libros.rowCount(); self.tbl_libros.insertRow(r)
            id_item = QTableWidgetItem(str(txn.fecha))
            id_item.setData(Qt.ItemDataRole.UserRole, txn.id)
            self.tbl_libros.setItem(r, 0, id_item)
            self.tbl_libros.setItem(r, 1, QTableWidgetItem(txn.concepto or ""))
            label, color, _ = TIPO_TXN_LABELS.get(txn.tipo, (str(txn.tipo), "#374151", ""))
            tipo_item = QTableWidgetItem(label)
            tipo_item.setForeground(QColor(color))
            self.tbl_libros.setItem(r, 2, tipo_item)
            v_it = QTableWidgetItem(_fmt(txn.valor))
            v_it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_libros.setItem(r, 3, v_it)

        # Resumen
        res = self.service.resumen_conciliacion(cid)
        self.lbl_resumen.setText(
            f"Saldo libros: {_fmt(res['saldo_libros'])}  |  "
            f"Líneas pendientes: {res['lineas_pendientes']}"
        )

    def _conciliar(self):
        fila_ext = self.tbl_extracto.currentRow()
        fila_lib = self.tbl_libros.currentRow()
        if fila_ext < 0 or fila_lib < 0:
            QMessageBox.warning(self, "Selección",
                                "Selecciona una línea del extracto Y un movimiento en libros.")
            return
        le_id  = self.tbl_extracto.item(fila_ext, 0).data(Qt.ItemDataRole.UserRole)
        txn_id = self.tbl_libros.item(fila_lib, 0).data(Qt.ItemDataRole.UserRole)
        try:
            self.service.conciliar(le_id, txn_id)
            self._cargar()
            QMessageBox.information(self, "Conciliado", "✅ Conciliación registrada correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _importar_csv(self):
        """Importa un extracto bancario desde CSV con columnas: fecha,descripcion,debito,credito,saldo"""
        cid = self.cb_cuenta.currentData()
        if not cid:
            QMessageBox.warning(self, "Sin cuenta", "Selecciona una cuenta bancaria primero.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir extracto CSV", "", "CSV (*.csv);;Todos (*)")
        if not path:
            return
        try:
            import csv
            from datetime import datetime as dt
            lineas = []
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fecha_raw = row.get("fecha", "").strip()
                    try:
                        fecha = dt.strptime(fecha_raw, "%Y-%m-%d").date()
                    except ValueError:
                        try:
                            fecha = dt.strptime(fecha_raw, "%d/%m/%Y").date()
                        except ValueError:
                            continue
                    lineas.append({
                        "fecha":       fecha,
                        "descripcion": row.get("descripcion", "").strip(),
                        "referencia":  row.get("referencia", "").strip() or None,
                        "debito":      row.get("debito", "0").replace(",", "").strip() or "0",
                        "credito":     row.get("credito", "0").replace(",", "").strip() or "0",
                        "saldo":       row.get("saldo", "").replace(",", "").strip() or None,
                    })
            if not lineas:
                QMessageBox.warning(self, "Sin datos", "No se encontraron líneas válidas en el CSV.")
                return
            n = self.service.importar_extracto(cid, lineas)
            QMessageBox.information(self, "Importado",
                                    f"✅ {n} líneas importadas correctamente.")
            self._cargar()
        except Exception as e:
            QMessageBox.critical(self, "Error al importar", str(e))

    def refresh(self):
        self._recargar_cuentas()


# ══════════════════════════════════════════════════════════════
# Widget principal: Módulo Tesorería
# ══════════════════════════════════════════════════════════════
class TesoreriaWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        self.service = TesoreriaService(self.session, empresa_id)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)

        titulo = QLabel("💰  Tesorería")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        lay.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 20px;font-size:13px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#2563eb;}"
        )

        self.tab_cuentas  = TabCuentas(self.service)
        self.tab_movs     = TabMovimientos(self.service)
        self.tab_concil   = TabConciliacion(self.service)

        # Doble clic en cuenta → ir a movimientos de esa cuenta
        self.tab_cuentas.cuenta_seleccionada.connect(self._ir_a_movimientos)

        self.tabs.addTab(self.tab_cuentas, "🏦 Cuentas")
        self.tabs.addTab(self.tab_movs,    "📋 Movimientos")
        self.tabs.addTab(self.tab_concil,  "✅ Conciliación")

        self.tabs.currentChanged.connect(self._on_tab)
        lay.addWidget(self.tabs)

    def _on_tab(self, index):
        self.session.expire_all()
        if index == 0: self.tab_cuentas.refresh()
        elif index == 1: self.tab_movs.refresh()
        elif index == 2: self.tab_concil.refresh()

    def _ir_a_movimientos(self, cuenta_id: int):
        self.tabs.setCurrentIndex(1)
        self.tab_movs.ir_a_cuenta(cuenta_id)

    def closeEvent(self, event):
        self.session.close(); super().closeEvent(event)
