from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QComboBox, QFrame, QTabWidget,
    QSplitter, QDateEdit, QDoubleSpinBox, QTextEdit,
    QCheckBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from core.models.impuestos import (
    TipoRetencion, TipoDeclaracion, EstadoDeclaracion
)
from modules.impuestos.service import ImpuestosService, TARIFAS_RTEFUENTE

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_SUCCESS = "background:#059669;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_WARN    = "background:#d97706;color:white;padding:5px 12px;border-radius:5px;font-weight:bold;"
BTN_DANGER  = "color:#dc2626;border:1px solid #fca5a5;padding:4px 10px;border-radius:5px;"

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

RET_LABELS = {
    TipoRetencion.SALARIOS:       "Salarios",
    TipoRetencion.HONORARIOS:     "Honorarios",
    TipoRetencion.SERVICIOS:      "Servicios",
    TipoRetencion.COMPRAS:        "Compras",
    TipoRetencion.ARRENDAMIENTOS: "Arrendamientos",
    TipoRetencion.DIVIDENDOS:     "Dividendos",
    TipoRetencion.INTERESES:      "Intereses",
    TipoRetencion.COMISIONES:     "Comisiones",
    TipoRetencion.OTROS:          "Otros conceptos",
    TipoRetencion.RETEIVA:        "Reteiva",
    TipoRetencion.RETEICA:        "Reteica",
}

DEC_LABELS = {
    TipoDeclaracion.RETENCION_FUENTE: "Retención en la Fuente",
    TipoDeclaracion.IVA:              "IVA",
    TipoDeclaracion.ICA:              "ICA",
    TipoDeclaracion.RENTA:            "Renta",
    TipoDeclaracion.GMF:              "GMF (4×1000)",
    TipoDeclaracion.INC:              "Impoconsumo",
    TipoDeclaracion.CREE:             "CREE",
}

ESTADO_COLOR = {
    "borrador":    ("#92400e", "#fef3c7"),
    "presentada":  ("#1d4ed8", "#dbeafe"),
    "pagada":      ("#166534", "#dcfce7"),
    "en_firme":    ("#374151", "#f1f5f9"),
}


def _fmt(v) -> str:
    try:
        return f"${Decimal(str(v)):,.0f}"
    except Exception:
        return "$0"


# ══════════════════════════════════════════════════════════════
# Búsqueda inline de terceros
# ══════════════════════════════════════════════════════════════
class TerceroSearch(QWidget):
    def __init__(self, service: ImpuestosService, parent=None):
        super().__init__(parent)
        self.service  = service
        self._tercero = None
        self._sel     = False
        self._frame   = None
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
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
        from PyQt6.QtWidgets import QVBoxLayout as VL
        fl = VL(f); fl.setContentsMargins(0, 0, 0, 0)
        lst = QListWidget()
        lst.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lst.setStyleSheet(
            "QListWidget{border:none;background:white;font-size:12px;color:#111;}"
            "QListWidget::item{color:#111;padding:4px 8px;}"
            "QListWidget::item:hover{background:#eff6ff;}")
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
        res = self.service.buscar_terceros(texto)
        p = self._popup(); p._lista.clear()
        if not res: p.hide(); return
        for t in res:
            item = QListWidgetItem(f"{t.numero_documento}  —  {t.nombre}")
            item.setForeground(QColor("#111")); item.setData(Qt.ItemDataRole.UserRole, t)
            p._lista.addItem(item)
        top = self.window()
        gp = self.edit.mapToGlobal(self.edit.rect().bottomLeft())
        lp = top.mapFromGlobal(gp)
        p.setGeometry(lp.x(), lp.y(), max(self.edit.width(), 380),
                      min(len(res) * 28 + 4, 220))
        p.raise_(); p.show()

    def _on_click(self, item):
        t = item.data(Qt.ItemDataRole.UserRole)
        self._tercero = t; self._sel = True
        self.edit.setText(f"{t.numero_documento}  —  {t.nombre}")
        self.edit.setStyleSheet("border:1px solid #16a34a;color:#111;")
        self._sel = False; self._frame.hide()

    def get_tercero(self): return self._tercero
    def hideEvent(self, e):
        if self._frame: self._frame.hide()
        super().hideEvent(e)


# ══════════════════════════════════════════════════════════════
# Diálogo: Nueva Retención
# ══════════════════════════════════════════════════════════════
class DialogRetencion(QDialog):
    def __init__(self, service: ImpuestosService,
                 periodo_id: int = None, parent=None):
        super().__init__(parent)
        self.service    = service
        self.periodo_id = periodo_id
        self.setWindowTitle("Registrar retención")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12)
        form = QFormLayout(); form.setSpacing(10)

        self.cb_tipo = QComboBox()
        for tipo, label in RET_LABELS.items():
            tarifa = TARIFAS_RTEFUENTE.get(tipo, Decimal("0"))
            pct    = float(tarifa) * 100
            suffix = f"  ({pct:.1f}%)" if pct > 0 else ""
            self.cb_tipo.addItem(f"{label}{suffix}", tipo)
        self.cb_tipo.currentIndexChanged.connect(self._on_tipo_changed)

        self.chk_practicada = QCheckBox("Nosotros practicamos la retención al tercero")
        self.chk_practicada.setChecked(True)
        self.chk_practicada.setStyleSheet("font-size:12px;")

        self.de_fecha = QDateEdit(QDate.currentDate())
        self.de_fecha.setCalendarPopup(True); self.de_fecha.setFixedWidth(130)

        self.tercero_sw = TerceroSearch(service=self.service)

        self.spin_base = QDoubleSpinBox()
        self.spin_base.setRange(0, 999_999_999_999); self.spin_base.setDecimals(0)
        self.spin_base.setPrefix("$ "); self.spin_base.setSingleStep(100000)
        self.spin_base.valueChanged.connect(self._recalcular)

        self.spin_tarifa = QDoubleSpinBox()
        self.spin_tarifa.setRange(0, 100); self.spin_tarifa.setDecimals(4)
        self.spin_tarifa.setSuffix(" %"); self.spin_tarifa.setFixedWidth(120)
        self.spin_tarifa.valueChanged.connect(self._recalcular)

        self.lbl_valor = QLabel("$0")
        self.lbl_valor.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_valor.setStyleSheet("color:#1d4ed8;")

        self.f_concepto = QLineEdit()
        self.f_concepto.setPlaceholderText("Descripción del concepto...")

        form.addRow("Tipo retención *:", self.cb_tipo)
        form.addRow("",                  self.chk_practicada)
        form.addRow("Fecha *:",          self.de_fecha)
        form.addRow("Tercero:",          self.tercero_sw)
        form.addRow("Base gravable *:",  self.spin_base)
        form.addRow("Tarifa *:",         self.spin_tarifa)
        form.addRow("Valor retención:", self.lbl_valor)
        form.addRow("Concepto:",         self.f_concepto)
        lay.addLayout(form)

        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("💾 Guardar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)

        self._on_tipo_changed()

    def _on_tipo_changed(self):
        tipo   = self.cb_tipo.currentData()
        tarifa = TARIFAS_RTEFUENTE.get(tipo, Decimal("0"))
        self.spin_tarifa.setValue(float(tarifa) * 100)

    def _recalcular(self):
        base   = Decimal(str(self.spin_base.value()))
        tarifa = Decimal(str(self.spin_tarifa.value())) / 100
        valor  = (base * tarifa).quantize(Decimal("1"))
        self.lbl_valor.setText(_fmt(valor))

    def _guardar(self):
        if self.spin_base.value() <= 0:
            QMessageBox.warning(self, "Base inválida", "La base gravable debe ser mayor a cero.")
            return
        self.accept()

    def datos(self) -> dict:
        base   = Decimal(str(int(self.spin_base.value())))
        tarifa = Decimal(str(self.spin_tarifa.value())) / 100
        valor  = (base * tarifa).quantize(Decimal("1"))
        qd     = self.de_fecha.date()
        t      = self.tercero_sw.get_tercero()
        return {
            "tipo":          self.cb_tipo.currentData(),
            "es_practicada": self.chk_practicada.isChecked(),
            "fecha":         date(qd.year(), qd.month(), qd.day()),
            "tercero_id":    t.id if t else None,
            "base_gravable": base,
            "tarifa":        tarifa,
            "valor":         valor,
            "concepto":      self.f_concepto.text().strip() or None,
            "periodo_id":    self.periodo_id,
        }


# ══════════════════════════════════════════════════════════════
# Diálogo: Declaración de Impuesto
# ══════════════════════════════════════════════════════════════
class DialogDeclaracion(QDialog):
    def __init__(self, service: ImpuestosService,
                 tipo: TipoDeclaracion, declaracion=None, parent=None):
        super().__init__(parent)
        self.service     = service
        self.tipo        = tipo
        self.declaracion = declaracion
        self.setWindowTitle(
            f"{'Editar' if declaracion else 'Nueva'} declaración — "
            f"{DEC_LABELS.get(tipo, tipo.value)}"
        )
        self.setMinimumWidth(520)
        self._build_ui()
        if declaracion:
            self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12)

        grp1 = QGroupBox("Período")
        grp1.setStyleSheet("QGroupBox{font-weight:bold;}")
        f1 = QFormLayout(grp1); f1.setSpacing(8)
        self.de_inicio = QDateEdit(); self.de_inicio.setCalendarPopup(True)
        self.de_inicio.setDate(QDate.currentDate().addDays(-30))
        self.de_fin    = QDateEdit(QDate.currentDate()); self.de_fin.setCalendarPopup(True)
        self.de_vence  = QDateEdit(); self.de_vence.setCalendarPopup(True)
        self.de_vence.setDate(QDate.currentDate().addDays(15))
        f1.addRow("Desde:", self.de_inicio)
        f1.addRow("Hasta:", self.de_fin)
        f1.addRow("Vence:", self.de_vence)
        lay.addWidget(grp1)

        grp2 = QGroupBox("Valores")
        grp2.setStyleSheet("QGroupBox{font-weight:bold;}")
        f2 = QFormLayout(grp2); f2.setSpacing(8)

        def spin(maximo=9_999_999_999):
            s = QDoubleSpinBox(); s.setRange(0, maximo)
            s.setDecimals(0); s.setPrefix("$ "); s.setSingleStep(10000)
            s.valueChanged.connect(self._recalcular)
            return s

        self.spin_base     = spin()
        self.spin_cargo    = spin()
        self.spin_desc     = spin()
        self.spin_anticipo = spin()
        self.spin_sancion  = spin()
        self.spin_intereses = spin()
        self.lbl_saldo     = QLabel("$0")
        self.lbl_saldo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_saldo.setStyleSheet("color:#1d4ed8;")

        f2.addRow("Base gravable:",      self.spin_base)
        f2.addRow("Impuesto a cargo:",   self.spin_cargo)
        f2.addRow("Descuentos:",         self.spin_desc)
        f2.addRow("Anticipos/retenc.:", self.spin_anticipo)
        f2.addRow("Sanciones:",          self.spin_sancion)
        f2.addRow("Intereses:",          self.spin_intereses)
        f2.addRow("→ Saldo a pagar:",    self.lbl_saldo)
        lay.addWidget(grp2)

        self.f_notas = QTextEdit(); self.f_notas.setFixedHeight(55)
        self.f_notas.setPlaceholderText("Notas...")
        lay.addWidget(QLabel("Notas:")); lay.addWidget(self.f_notas)

        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def _recalcular(self):
        cargo    = Decimal(str(int(self.spin_cargo.value())))
        desc     = Decimal(str(int(self.spin_desc.value())))
        anticipo = Decimal(str(int(self.spin_anticipo.value())))
        sancion  = Decimal(str(int(self.spin_sancion.value())))
        intereses = Decimal(str(int(self.spin_intereses.value())))
        saldo = max(cargo - desc - anticipo + sancion + intereses, Decimal("0"))
        self.lbl_saldo.setText(_fmt(saldo))
        self.lbl_saldo.setStyleSheet(
            "color:#b91c1c;font-size:13px;font-weight:bold;" if saldo > 0
            else "color:#15803d;font-size:13px;font-weight:bold;"
        )

    def _cargar(self):
        d = self.declaracion
        def _set(de_widget, d_field):
            v = getattr(d, d_field, None)
            if v:
                de_widget.setDate(QDate(v.year, v.month, v.day))
        _set(self.de_inicio, "fecha_inicio")
        _set(self.de_fin,    "fecha_fin")
        _set(self.de_vence,  "fecha_vence")
        for spin, campo in [
            (self.spin_base,     "base_gravable"),
            (self.spin_cargo,    "impuesto_cargo"),
            (self.spin_desc,     "descuentos"),
            (self.spin_anticipo, "anticipos"),
            (self.spin_sancion,  "sancion"),
            (self.spin_intereses,"intereses"),
        ]:
            spin.setValue(float(getattr(d, campo, 0) or 0))
        self.f_notas.setPlainText(d.notas or "")

    def datos(self) -> dict:
        def _d(qde): qd = qde.date(); return date(qd.year(), qd.month(), qd.day())
        return {
            "tipo":           self.tipo,
            "fecha_inicio":   _d(self.de_inicio),
            "fecha_fin":      _d(self.de_fin),
            "fecha_vence":    _d(self.de_vence),
            "base_gravable":  Decimal(str(int(self.spin_base.value()))),
            "impuesto_cargo": Decimal(str(int(self.spin_cargo.value()))),
            "descuentos":     Decimal(str(int(self.spin_desc.value()))),
            "anticipos":      Decimal(str(int(self.spin_anticipo.value()))),
            "sancion":        Decimal(str(int(self.spin_sancion.value()))),
            "intereses":      Decimal(str(int(self.spin_intereses.value()))),
            "notas":          self.f_notas.toPlainText().strip() or None,
        }


# ══════════════════════════════════════════════════════════════
# Tab 1 — Retenciones
# ══════════════════════════════════════════════════════════════
class TabRetenciones(QWidget):
    def __init__(self, service: ImpuestosService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui(); self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        fil = QHBoxLayout()
        self.cb_periodo = QComboBox(); self.cb_periodo.setFixedWidth(200)
        self.cb_periodo.currentIndexChanged.connect(self._cargar)
        self.cb_tipo = QComboBox(); self.cb_tipo.setFixedWidth(180)
        self.cb_tipo.addItem("Todos los tipos", None)
        for tipo, label in RET_LABELS.items():
            self.cb_tipo.addItem(label, tipo)
        self.cb_tipo.currentIndexChanged.connect(self._cargar)
        self.chk_pract = QCheckBox("Solo practicadas")
        self.chk_pract.toggled.connect(self._cargar)
        fil.addWidget(QLabel("Periodo:")); fil.addWidget(self.cb_periodo)
        fil.addWidget(QLabel("Tipo:"));   fil.addWidget(self.cb_tipo)
        fil.addWidget(self.chk_pract); fil.addStretch()
        lay.addLayout(fil)

        # Resumen del periodo
        self.grp_res = QGroupBox("Resumen del periodo")
        self.grp_res.setStyleSheet("QGroupBox{font-weight:bold;}")
        rl = QHBoxLayout(self.grp_res)
        self._lbl_res = {}
        for key, label in [
            ("total_practicadas", "Total practicadas"),
            ("total_recibidas",   "Total recibidas"),
            ("saldo_pagar",       "Saldo a declarar"),
        ]:
            col = QVBoxLayout()
            lk  = QLabel(label); lk.setStyleSheet("color:#64748b;font-size:11px;")
            lv  = QLabel("$0")
            lv.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lk, alignment=Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lv, alignment=Qt.AlignmentFlag.AlignCenter)
            self._lbl_res[key] = lv
            rl.addLayout(col)
            if key != "saldo_pagar":
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color:#e2e8f0;"); rl.addWidget(sep)
        lay.addWidget(self.grp_res)

        tb = QHBoxLayout()
        btn_nuevo = QPushButton("+ Registrar retención"); btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.clicked.connect(self._nuevo)
        self.btn_elim = QPushButton("🗑 Eliminar"); self.btn_elim.setStyleSheet(BTN_DANGER)
        self.btn_elim.setEnabled(False); self.btn_elim.clicked.connect(self._eliminar)
        self.lbl_total = QLabel(); self.lbl_total.setStyleSheet("color:#64748b;font-size:12px;")
        tb.addWidget(btn_nuevo); tb.addWidget(self.btn_elim)
        tb.addStretch(); tb.addWidget(self.lbl_total)
        lay.addLayout(tb)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "Fecha", "Tipo", "Dirección", "Tercero",
            "Base gravable", "Tarifa", "Valor"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 90); self.tabla.setColumnWidth(1, 130)
        self.tabla.setColumnWidth(2, 90); self.tabla.setColumnWidth(4, 120)
        self.tabla.setColumnWidth(5, 70); self.tabla.setColumnWidth(6, 110)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(
            lambda: self.btn_elim.setEnabled(bool(self.tabla.selectedItems())))
        lay.addWidget(self.tabla)

    def showEvent(self, event):
        super().showEvent(event)
        self.service.db.expire_all()
        self._llenar_periodos()

    def _llenar_periodos(self):
        self.cb_periodo.blockSignals(True)
        self.cb_periodo.clear()
        self.cb_periodo.addItem("Todos los periodos", None)
        for p in self.service.listar_periodos():
            self.cb_periodo.addItem(f"{MESES[p.mes]} {p.anio}", p.id)
        self.cb_periodo.blockSignals(False)

    def _cargar(self):
        self.service.db.expire_all()
        pid     = self.cb_periodo.currentData()
        tipo    = self.cb_tipo.currentData()
        solo_p  = self.chk_pract.isChecked()
        rets    = self.service.listar_retenciones(
            periodo_id   = pid,
            tipo         = tipo,
            es_practicada= True if solo_p else None,
        )
        self.tabla.setRowCount(0)
        for r in rets:
            row = self.tabla.rowCount(); self.tabla.insertRow(row)
            id_item = QTableWidgetItem(str(r.fecha))
            id_item.setData(Qt.ItemDataRole.UserRole, r.id)
            self.tabla.setItem(row, 0, id_item)
            self.tabla.setItem(row, 1, QTableWidgetItem(RET_LABELS.get(r.tipo, "")))
            dir_str = "📤 Practicada" if r.es_practicada else "📥 Recibida"
            dir_item = QTableWidgetItem(dir_str)
            dir_item.setForeground(QColor("#1d4ed8" if r.es_practicada else "#15803d"))
            self.tabla.setItem(row, 2, dir_item)
            t_nom = r.tercero.nombre if r.tercero else "—"
            self.tabla.setItem(row, 3, QTableWidgetItem(t_nom))
            for col, val in [(4, r.base_gravable), (6, r.valor)]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabla.setItem(row, col, it)
            pct = float(r.tarifa) * 100 if r.tarifa else 0
            self.tabla.setItem(row, 5, QTableWidgetItem(f"{pct:.2f}%"))

        self.lbl_total.setText(f"{len(rets)} registros")

        # Resumen
        if pid:
            res = self.service.resumen_retenciones_periodo(pid)
            self._lbl_res["total_practicadas"].setText(_fmt(res["total_practicadas"]))
            self._lbl_res["total_recibidas"].setText(_fmt(res["total_recibidas"]))
            sp = res["saldo_pagar"]
            self._lbl_res["saldo_pagar"].setText(_fmt(sp))
            self._lbl_res["saldo_pagar"].setStyleSheet(
                "color:#b91c1c;font-size:13px;font-weight:bold;" if sp > 0
                else "color:#15803d;font-size:13px;font-weight:bold;"
            )
            self.grp_res.setVisible(True)
        else:
            self.grp_res.setVisible(False)

        self.btn_elim.setEnabled(False)

    def _nuevo(self):
        pid = self.cb_periodo.currentData()
        dlg = DialogRetencion(self.service, periodo_id=pid, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_retencion(dlg.datos()); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _eliminar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        ret_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self, "Eliminar retención",
            "¿Eliminar esta retención?\nSolo es posible si no está incluida en una declaración.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                self.service.eliminar_retencion(ret_id); self._cargar()
            except ValueError as e:
                QMessageBox.warning(self, "No permitido", str(e))

    def refresh(self): self._llenar_periodos(); self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 2 — Resumen IVA
# ══════════════════════════════════════════════════════════════
class TabIVA(QWidget):
    def __init__(self, service: ImpuestosService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(12)

        info = QLabel(
            "ℹ️  Este panel consolida el IVA generado en ventas y el IVA descontable "
            "en compras del período seleccionado, tomando los datos de Facturación."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#eff6ff;color:#1d4ed8;padding:8px 12px;"
            "border-radius:6px;font-size:12px;")
        lay.addWidget(info)

        fil = QHBoxLayout()
        self.de_desde = QDateEdit(); self.de_desde.setCalendarPopup(True)
        self.de_desde.setDate(QDate.currentDate().addDays(-60))
        self.de_desde.setFixedWidth(120)
        self.de_hasta = QDateEdit(QDate.currentDate()); self.de_hasta.setCalendarPopup(True)
        self.de_hasta.setFixedWidth(120)
        btn_calc = QPushButton("🧮 Calcular IVA"); btn_calc.setStyleSheet(BTN_PRIMARY)
        btn_calc.clicked.connect(self._calcular)
        fil.addWidget(QLabel("Del:")); fil.addWidget(self.de_desde)
        fil.addWidget(QLabel("Al:")); fil.addWidget(self.de_hasta)
        fil.addWidget(btn_calc); fil.addStretch()
        lay.addLayout(fil)

        # Tarjetas resumen
        self.grp_iva = QGroupBox("Resultado IVA del período")
        self.grp_iva.setStyleSheet("QGroupBox{font-weight:bold;}")
        self.grp_iva.setVisible(False)
        gl = QHBoxLayout(self.grp_iva)
        self._iva_lbls = {}
        items = [
            ("iva_generado",    "IVA Generado\n(ventas)",    "#15803d"),
            ("iva_nc_ventas",   "NC en ventas\n(descuento)", "#b45309"),
            ("iva_descontable", "IVA Descontable\n(compras)","#1d4ed8"),
            ("iva_neto",        "IVA Neto",                  "#374151"),
            ("saldo_pagar",     "SALDO A PAGAR",             "#b91c1c"),
        ]
        for key, label, color in items:
            col = QVBoxLayout()
            lk  = QLabel(label); lk.setStyleSheet("color:#64748b;font-size:11px;")
            lk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lv  = QLabel("$0")
            lv.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            lv.setStyleSheet(f"color:{color};")
            lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lk); col.addWidget(lv)
            self._iva_lbls[key] = lv
            gl.addLayout(col)
            if key != "saldo_pagar":
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color:#e2e8f0;"); gl.addWidget(sep)
        lay.addWidget(self.grp_iva)
        lay.addStretch()

    def _calcular(self):
        qd1 = self.de_desde.date(); qd2 = self.de_hasta.date()
        f1  = date(qd1.year(), qd1.month(), qd1.day())
        f2  = date(qd2.year(), qd2.month(), qd2.day())
        try:
            res = self.service.resumen_iva_periodo(f1, f2)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return

        for key, lbl in self._iva_lbls.items():
            lbl.setText(_fmt(res.get(key, 0)))
        sp = res.get("saldo_pagar", 0)
        self._iva_lbls["saldo_pagar"].setStyleSheet(
            "color:#b91c1c;font-size:16px;font-weight:bold;" if sp > 0
            else "color:#15803d;font-size:16px;font-weight:bold;"
        )
        self.grp_iva.setVisible(True)


# ══════════════════════════════════════════════════════════════
# Tab 3 — Declaraciones
# ══════════════════════════════════════════════════════════════
class TabDeclaraciones(QWidget):
    def __init__(self, service: ImpuestosService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui(); self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        tb = QHBoxLayout()
        self.cb_tipo = QComboBox(); self.cb_tipo.setFixedWidth(220)
        self.cb_tipo.addItem("Todos los tipos", None)
        for tipo, label in DEC_LABELS.items():
            self.cb_tipo.addItem(label, tipo)
        self.cb_tipo.currentIndexChanged.connect(self._cargar)

        btn_nueva = QPushButton("+ Nueva declaración"); btn_nueva.setStyleSheet(BTN_PRIMARY)
        btn_nueva.clicked.connect(self._nueva)
        self.btn_presentar = QPushButton("📤 Presentar"); self.btn_presentar.setStyleSheet(BTN_WARN)
        self.btn_presentar.setEnabled(False); self.btn_presentar.clicked.connect(self._presentar)
        self.btn_pagar = QPushButton("💳 Pagar"); self.btn_pagar.setStyleSheet(BTN_SUCCESS)
        self.btn_pagar.setEnabled(False); self.btn_pagar.clicked.connect(self._pagar)
        btn_ref = QPushButton("🔄"); btn_ref.setFixedWidth(36); btn_ref.clicked.connect(self._cargar)

        tb.addWidget(QLabel("Tipo:")); tb.addWidget(self.cb_tipo); tb.addStretch()
        tb.addWidget(btn_nueva); tb.addWidget(self.btn_presentar)
        tb.addWidget(self.btn_pagar); tb.addWidget(btn_ref)
        lay.addLayout(tb)

        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels([
            "Tipo", "Período", "Vence", "Impuesto cargo",
            "Anticipos", "Saldo pagar", "No. formulario", "Estado"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(1, 150); self.tabla.setColumnWidth(2, 90)
        self.tabla.setColumnWidth(3, 115); self.tabla.setColumnWidth(4, 90)
        self.tabla.setColumnWidth(5, 110); self.tabla.setColumnWidth(6, 110)
        self.tabla.setColumnWidth(7, 100)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        self.tabla.itemDoubleClicked.connect(lambda _: self._editar())
        lay.addWidget(self.tabla)

    def _cargar(self):
        self.service.db.expire_all()
        tipo = self.cb_tipo.currentData()
        decs = self.service.listar_declaraciones(tipo=tipo)
        self.tabla.setRowCount(0)
        for d in decs:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            tipo_label = DEC_LABELS.get(d.tipo, d.tipo.value)
            tipo_item  = QTableWidgetItem(tipo_label)
            tipo_item.setData(Qt.ItemDataRole.UserRole, d.id)
            self.tabla.setItem(r, 0, tipo_item)
            periodo_str = f"{d.fecha_inicio} → {d.fecha_fin}"
            self.tabla.setItem(r, 1, QTableWidgetItem(periodo_str))
            self.tabla.setItem(r, 2, QTableWidgetItem(str(d.fecha_vence) if d.fecha_vence else ""))
            for col, val in [(3, d.impuesto_cargo), (4, d.anticipos), (5, d.saldo_pagar)]:
                it = QTableWidgetItem(_fmt(val or 0))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == 5 and (d.saldo_pagar or 0) > 0:
                    it.setForeground(QColor("#b91c1c"))
                    it.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                self.tabla.setItem(r, col, it)
            self.tabla.setItem(r, 6, QTableWidgetItem(d.numero_formulario or ""))
            estado_v = d.estado.value if hasattr(d.estado, "value") else d.estado
            est_str  = {"borrador":"Borrador","presentada":"Presentada",
                        "pagada":"Pagada","en_firme":"En firme"}.get(estado_v, estado_v)
            est_item = QTableWidgetItem(est_str)
            fg, bg   = ESTADO_COLOR.get(estado_v, ("#374151", "#f8fafc"))
            est_item.setForeground(QColor(fg)); est_item.setBackground(QColor(bg))
            self.tabla.setItem(r, 7, est_item)

            # Alertar si vence pronto y no está pagada
            if d.fecha_vence and estado_v == "presentada":
                dias_restantes = (d.fecha_vence - date.today()).days
                if 0 <= dias_restantes <= 5:
                    for col in range(8):
                        it = self.tabla.item(r, col)
                        if it: it.setBackground(QColor("#fef9c3"))

        self.btn_presentar.setEnabled(False)
        self.btn_pagar.setEnabled(False)

    def _on_sel(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        dec_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        dec = self.service.db.get(
            __import__('core.models.impuestos',
                       fromlist=['DeclaracionImpuesto']).DeclaracionImpuesto,
            dec_id)
        if not dec: return
        estado_v = dec.estado.value if hasattr(dec.estado, "value") else dec.estado
        self.btn_presentar.setEnabled(estado_v == "borrador")
        self.btn_pagar.setEnabled(estado_v == "presentada")

    def _nueva(self):
        tipo = self.cb_tipo.currentData()
        if not tipo:
            # Si no hay filtro, preguntar qué tipo
            dlg_tipo = QDialog(self); dlg_tipo.setWindowTitle("Tipo de declaración")
            dlg_tipo.setFixedSize(280, 130)
            dlay = QVBoxLayout(dlg_tipo)
            cb = QComboBox()
            for t, l in DEC_LABELS.items(): cb.addItem(l, t)
            dlay.addWidget(QLabel("Tipo:")); dlay.addWidget(cb)
            btns2 = QHBoxLayout(); btns2.addStretch()
            btn_ok = QPushButton("Continuar"); btn_ok.setStyleSheet(BTN_PRIMARY)
            btn_ok.clicked.connect(dlg_tipo.accept)
            btns2.addWidget(QPushButton("Cancelar", clicked=dlg_tipo.reject))
            btns2.addWidget(btn_ok); dlay.addLayout(btns2)
            if dlg_tipo.exec() != QDialog.DialogCode.Accepted: return
            tipo = cb.currentData()

        dlg = DialogDeclaracion(self.service, tipo, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_declaracion(dlg.datos()); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _editar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        from core.models.impuestos import DeclaracionImpuesto
        dec_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        dec    = self.service.db.get(DeclaracionImpuesto, dec_id)
        if not dec: return
        dlg = DialogDeclaracion(self.service, dec.tipo, declaracion=dec, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar_declaracion(dec_id, dlg.datos()); self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _presentar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        dec_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        dlg = QDialog(self); dlg.setWindowTitle("Presentar declaración")
        dlg.setFixedSize(340, 140)
        dlay = QFormLayout(dlg)
        f_num  = QLineEdit(); f_num.setPlaceholderText("No. de formulario DIAN")
        de_fp  = QDateEdit(QDate.currentDate()); de_fp.setCalendarPopup(True)
        dlay.addRow("No. formulario:", f_num)
        dlay.addRow("Fecha presentación:", de_fp)
        btns2 = QHBoxLayout(); btns2.addStretch()
        btn_ok = QPushButton("Presentar"); btn_ok.setStyleSheet(BTN_PRIMARY)
        btn_ok.clicked.connect(dlg.accept)
        btns2.addWidget(QPushButton("Cancelar", clicked=dlg.reject))
        btns2.addWidget(btn_ok)
        from PyQt6.QtWidgets import QWidget as W
        w = W(); w.setLayout(btns2); dlay.addRow(w)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            qd = de_fp.date()
            try:
                self.service.presentar_declaracion(
                    dec_id, f_num.text().strip(),
                    date(qd.year(), qd.month(), qd.day()))
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _pagar(self):
        fila = self.tabla.currentRow()
        if fila < 0: return
        dec_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        dlg = QDialog(self); dlg.setWindowTitle("Registrar pago")
        dlg.setFixedSize(280, 110)
        dlay = QFormLayout(dlg)
        de_pago = QDateEdit(QDate.currentDate()); de_pago.setCalendarPopup(True)
        dlay.addRow("Fecha de pago:", de_pago)
        btns2 = QHBoxLayout(); btns2.addStretch()
        btn_ok = QPushButton("Confirmar"); btn_ok.setStyleSheet(BTN_SUCCESS)
        btn_ok.clicked.connect(dlg.accept)
        btns2.addWidget(QPushButton("Cancelar", clicked=dlg.reject))
        btns2.addWidget(btn_ok)
        from PyQt6.QtWidgets import QWidget as W
        w = W(); w.setLayout(btns2); dlay.addRow(w)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            qd = de_pago.date()
            try:
                self.service.registrar_pago(
                    dec_id, date(qd.year(), qd.month(), qd.day()))
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self): self._cargar()


# ══════════════════════════════════════════════════════════════
# Widget principal: Módulo Impuestos
# ══════════════════════════════════════════════════════════════
class ImpuestosWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        self.service = ImpuestosService(self.session, empresa_id)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        titulo = QLabel("📋  Impuestos")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        lay.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 20px;font-size:13px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#2563eb;}"
        )
        self.tab_ret  = TabRetenciones(self.service)
        self.tab_iva  = TabIVA(self.service)
        self.tab_dec  = TabDeclaraciones(self.service)

        self.tabs.addTab(self.tab_ret,  "✂️ Retenciones")
        self.tabs.addTab(self.tab_iva,  "💰 IVA")
        self.tabs.addTab(self.tab_dec,  "📄 Declaraciones")
        self.tabs.currentChanged.connect(lambda _: self.session.expire_all())
        lay.addWidget(self.tabs)

    def closeEvent(self, event):
        self.session.close(); super().closeEvent(event)
