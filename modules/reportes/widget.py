from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView,
    QAbstractItemView, QComboBox, QFrame, QTabWidget,
    QSplitter, QDateEdit, QFileDialog, QMessageBox,
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from modules.reportes.service import ReportesService, MESES

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_EXPORT  = "background:#7c3aed;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"


def _fmt(v, decimals=0) -> str:
    try:
        v = Decimal(str(v or 0))
        if decimals == 0:
            return f"${v:,.0f}"
        return f"${v:,.2f}"
    except Exception:
        return "$0"


def _color_valor(tabla, row, col, valor):
    """Colorea celdas de valor: verde positivo, rojo negativo."""
    item = tabla.item(row, col)
    if not item:
        return
    v = Decimal(str(valor or 0))
    if v < 0:
        item.setForeground(QColor("#b91c1c"))
    elif v > 0:
        item.setForeground(QColor("#15803d"))


def _periodo_label(p) -> str:
    return f"{MESES[p.mes]} {p.anio}"


# ══════════════════════════════════════════════════════════════
# Barra de filtro de fechas reutilizable
# ══════════════════════════════════════════════════════════════
class FiltroPeriodo(QWidget):
    def __init__(self, service: ReportesService,
                 label_desde="Desde:", label_hasta="Hasta:",
                 parent=None):
        super().__init__(parent)
        self.service = service
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)

        # Acceso rápido por periodo contable
        self.cb_periodo = QComboBox(); self.cb_periodo.setFixedWidth(190)
        self.cb_periodo.addItem("— Rango personalizado —", None)
        for p in service.listar_periodos():
            self.cb_periodo.addItem(_periodo_label(p), p.id)
        self.cb_periodo.currentIndexChanged.connect(self._on_periodo)

        self.de_desde = QDateEdit()
        self.de_desde.setCalendarPopup(True)
        self.de_desde.setDate(QDate.currentDate().addDays(-30))
        self.de_desde.setFixedWidth(120)

        self.de_hasta = QDateEdit(QDate.currentDate())
        self.de_hasta.setCalendarPopup(True)
        self.de_hasta.setFixedWidth(120)

        lay.addWidget(QLabel("Periodo:"))
        lay.addWidget(self.cb_periodo)
        lay.addWidget(QLabel(f"  {label_desde}"))
        lay.addWidget(self.de_desde)
        lay.addWidget(QLabel(f"  {label_hasta}"))
        lay.addWidget(self.de_hasta)

    def _on_periodo(self):
        pid = self.cb_periodo.currentData()
        if not pid:
            return
        import calendar
        p = next((p for p in self.service.listar_periodos() if p.id == pid), None)
        if not p:
            return
        primer = date(p.anio, p.mes, 1)
        ultimo = date(p.anio, p.mes, calendar.monthrange(p.anio, p.mes)[1])
        self.de_desde.setDate(QDate(primer.year, primer.month, primer.day))
        self.de_hasta.setDate(QDate(ultimo.year, ultimo.month, ultimo.day))

    def fechas(self):
        qd1 = self.de_desde.date(); qd2 = self.de_hasta.date()
        return (
            date(qd1.year(), qd1.month(), qd1.day()),
            date(qd2.year(), qd2.month(), qd2.day()),
        )


# ══════════════════════════════════════════════════════════════
# Tab 1 — Libro Mayor / Balance de Comprobación
# ══════════════════════════════════════════════════════════════
class TabLibroMayor(QWidget):
    def __init__(self, service: ReportesService, parent=None):
        super().__init__(parent)
        self.service = service
        self._datos  = []
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        # Filtros
        fil = QHBoxLayout()
        self.filtro = FiltroPeriodo(self.service)
        self.cb_reporte = QComboBox(); self.cb_reporte.setFixedWidth(220)
        self.cb_reporte.addItem("Libro Mayor", "mayor")
        self.cb_reporte.addItem("Balance de Comprobación", "balance")
        btn_gen = QPushButton("📊 Generar"); btn_gen.setStyleSheet(BTN_PRIMARY)
        btn_gen.clicked.connect(self._generar)
        self.btn_exp = QPushButton("📥 Exportar CSV"); self.btn_exp.setStyleSheet(BTN_EXPORT)
        self.btn_exp.setEnabled(False); self.btn_exp.clicked.connect(self._exportar)
        fil.addWidget(self.filtro); fil.addWidget(self.cb_reporte)
        fil.addWidget(btn_gen); fil.addStretch(); fil.addWidget(self.btn_exp)
        lay.addLayout(fil)

        # Tabla
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels([
            "Código", "Nombre", "Saldo anterior",
            "Débitos", "Créditos", "Saldo final"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 90); self.tabla.setColumnWidth(2, 120)
        self.tabla.setColumnWidth(3, 110); self.tabla.setColumnWidth(4, 110)
        self.tabla.setColumnWidth(5, 120)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setFont(QFont("Consolas", 10))
        lay.addWidget(self.tabla)

        # Fila totales
        self.lbl_totales = QLabel()
        self.lbl_totales.setStyleSheet(
            "background:#f1f5f9;padding:6px 12px;border-radius:6px;"
            "font-size:12px;color:#1e293b;font-weight:bold;"
        )
        lay.addWidget(self.lbl_totales)

    def _generar(self):
        self.service.db.expire_all()
        f1, f2 = self.filtro.fechas()
        tipo = self.cb_reporte.currentData()
        try:
            if tipo == "mayor":
                datos = self.service.libro_mayor(f1, f2)
                self._render_mayor(datos)
            else:
                datos, totales = self.service.balance_comprobacion(f1, f2)
                self._render_mayor(datos, totales)
            self._datos = datos
            self.btn_exp.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _render_mayor(self, datos, totales=None):
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        for f in datos:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            self.tabla.setItem(r, 0, QTableWidgetItem(f["codigo"]))
            self.tabla.setItem(r, 1, QTableWidgetItem(f["nombre"]))
            for col, val in [
                (2, f["saldo_ant"]), (3, f["debitos"]),
                (4, f["creditos"]), (5, f["saldo_final"])
            ]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabla.setItem(r, col, it)
            _color_valor(self.tabla, r, 2, f["saldo_ant"])
            _color_valor(self.tabla, r, 5, f["saldo_final"])

        self.tabla.blockSignals(False)
        if totales:
            self.lbl_totales.setText(
                f"Saldo anterior: {_fmt(totales['saldo_ant_db'])} DB / "
                f"{_fmt(totales['saldo_ant_cr'])} CR  |  "
                f"Movimientos: {_fmt(totales['mov_db'])} DB / {_fmt(totales['mov_cr'])} CR  |  "
                f"Saldo final: {_fmt(totales['saldo_fin_db'])} DB / {_fmt(totales['saldo_fin_cr'])} CR"
            )
        else:
            self.lbl_totales.setText(f"{len(datos)} cuentas con movimiento")

    def _exportar(self):
        if not self._datos:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar", "libro_mayor.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Código", "Nombre", "Saldo anterior",
                                 "Débitos", "Créditos", "Saldo final"])
                for row in self._datos:
                    writer.writerow([
                        row["codigo"], row["nombre"],
                        row["saldo_ant"], row["debitos"],
                        row["creditos"], row["saldo_final"]
                    ])
            QMessageBox.information(self, "Exportado", f"✅ {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 2 — Estado de Resultados
# ══════════════════════════════════════════════════════════════
class TabEstadoResultados(QWidget):
    def __init__(self, service: ReportesService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(12)

        fil = QHBoxLayout()
        self.filtro = FiltroPeriodo(self.service)
        btn_gen = QPushButton("📊 Generar"); btn_gen.setStyleSheet(BTN_PRIMARY)
        btn_gen.clicked.connect(self._generar)
        self.btn_exp = QPushButton("📥 Exportar CSV"); self.btn_exp.setStyleSheet(BTN_EXPORT)
        self.btn_exp.setEnabled(False); self.btn_exp.clicked.connect(self._exportar)
        fil.addWidget(self.filtro); fil.addWidget(btn_gen)
        fil.addStretch(); fil.addWidget(self.btn_exp)
        lay.addLayout(fil)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        contenido = QWidget(); contenido.setStyleSheet("background:white;")
        self._cl = QVBoxLayout(contenido); self._cl.setContentsMargins(40,20,40,20)
        self._cl.setSpacing(0)
        scroll.setWidget(contenido)
        lay.addWidget(scroll)
        self._er = None

    def _generar(self):
        self.service.db.expire_all()
        f1, f2 = self.filtro.fechas()
        try:
            er = self.service.estado_resultados(f1, f2)
            self._er = er
            self._renderizar(er)
            self.btn_exp.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _renderizar(self, er: dict):
        # Limpiar layout
        while self._cl.count():
            item = self._cl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def titulo(texto, nivel=1):
            lbl = QLabel(texto)
            sizes  = {1: 15, 2: 13, 3: 12}
            bold   = QFont.Weight.Bold if nivel <= 2 else QFont.Weight.Normal
            lbl.setFont(QFont("Segoe UI", sizes.get(nivel, 12), bold))
            pads   = {1: "margin-top:16px;margin-bottom:4px;",
                      2: "margin-top:12px;",
                      3: "margin-top:2px;margin-left:20px;"}
            lbl.setStyleSheet(pads.get(nivel, ""))
            self._cl.addWidget(lbl)

        def linea(label, valor, negrita=False, color=None, indent=0):
            row = QHBoxLayout()
            lbl_l = QLabel(("  " * indent) + label)
            lbl_v = QLabel(_fmt(valor))
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight)
            if negrita:
                lbl_l.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                lbl_v.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            v = Decimal(str(valor or 0))
            c = color or ("#15803d" if v >= 0 else "#b91c1c")
            lbl_v.setStyleSheet(f"color:{c};")
            row.addWidget(lbl_l); row.addStretch(); row.addWidget(lbl_v)
            self._cl.addLayout(row)

        def separador():
            sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color:#e2e8f0;margin:6px 0;")
            self._cl.addWidget(sep)

        titulo(f"ESTADO DE RESULTADOS\n{er['fecha_inicio']}  →  {er['fecha_fin']}", 1)
        separador()

        titulo("INGRESOS", 2)
        linea("Ingresos operacionales",    er["ingresos_op"],    indent=1)
        linea("Ingresos no operacionales", er["ingresos_no_op"], indent=1)
        separador()
        linea("TOTAL INGRESOS", er["total_ingresos"], negrita=True)
        separador()

        titulo("COSTOS", 2)
        linea("Costo de ventas",    er["costo_venta"],     indent=1)
        linea("Costo de producción",er["costo_produccion"],indent=1)
        separador()
        linea("UTILIDAD BRUTA", er["utilidad_bruta"], negrita=True)
        separador()

        titulo("GASTOS OPERACIONALES", 2)
        linea("Gastos operacionales", er["gastos_op"], indent=1)
        separador()
        linea("UTILIDAD OPERACIONAL", er["utilidad_op"], negrita=True)
        separador()

        linea("UTILIDAD NETA DEL EJERCICIO", er["utilidad_neta"],
              negrita=True, color=("#15803d" if er["utilidad_neta"] >= 0 else "#b91c1c"))

        self._cl.addStretch()

    def _exportar(self):
        if not self._er:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar", "estado_resultados.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            er = self._er
            rows = [
                ["Concepto", "Valor"],
                ["Ingresos operacionales",     er["ingresos_op"]],
                ["Ingresos no operacionales",  er["ingresos_no_op"]],
                ["Total Ingresos",             er["total_ingresos"]],
                ["Costo de ventas",            er["costo_venta"]],
                ["Costo de producción",        er["costo_produccion"]],
                ["Utilidad Bruta",             er["utilidad_bruta"]],
                ["Gastos operacionales",       er["gastos_op"]],
                ["Utilidad Operacional",       er["utilidad_op"]],
                ["Utilidad Neta",              er["utilidad_neta"]],
            ]
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerows(rows)
            QMessageBox.information(self, "Exportado", f"✅ {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 3 — Balance General
# ══════════════════════════════════════════════════════════════
class TabBalanceGeneral(QWidget):
    def __init__(self, service: ReportesService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(12)

        fil = QHBoxLayout()
        self.de_corte = QDateEdit(QDate.currentDate())
        self.de_corte.setCalendarPopup(True); self.de_corte.setFixedWidth(130)
        btn_gen = QPushButton("📊 Generar"); btn_gen.setStyleSheet(BTN_PRIMARY)
        btn_gen.clicked.connect(self._generar)
        self.btn_exp = QPushButton("📥 Exportar CSV"); self.btn_exp.setStyleSheet(BTN_EXPORT)
        self.btn_exp.setEnabled(False); self.btn_exp.clicked.connect(self._exportar)
        fil.addWidget(QLabel("Fecha de corte:")); fil.addWidget(self.de_corte)
        fil.addWidget(btn_gen); fil.addStretch(); fil.addWidget(self.btn_exp)
        lay.addLayout(fil)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        contenido = QWidget(); contenido.setStyleSheet("background:white;")
        self._cl = QVBoxLayout(contenido); self._cl.setContentsMargins(40,20,40,20)
        self._cl.setSpacing(2)
        scroll.setWidget(contenido)
        lay.addWidget(scroll)
        self._bg = None

    def _generar(self):
        self.service.db.expire_all()
        qd = self.de_corte.date()
        f  = date(qd.year(), qd.month(), qd.day())
        try:
            bg = self.service.balance_general(f)
            self._bg = bg
            self._renderizar(bg)
            self.btn_exp.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _renderizar(self, bg: dict):
        while self._cl.count():
            item = self._cl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def linea(label, valor, negrita=False, color=None, indent=0):
            row = QHBoxLayout()
            lbl_l = QLabel("  " * indent + label)
            lbl_v = QLabel(_fmt(valor))
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight)
            if negrita:
                lbl_l.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                lbl_v.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            v = Decimal(str(valor or 0))
            c = color or ("#1e293b" if v >= 0 else "#b91c1c")
            lbl_v.setStyleSheet(f"color:{c};")
            row.addWidget(lbl_l); row.addStretch(); row.addWidget(lbl_v)
            self._cl.addLayout(row)

        def sep():
            s = QFrame(); s.setFrameShape(QFrame.Shape.HLine)
            s.setStyleSheet("color:#e2e8f0;margin:6px 0;")
            self._cl.addWidget(s)

        def titulo(t, sz=14):
            l = QLabel(t); l.setFont(QFont("Segoe UI", sz, QFont.Weight.Bold))
            l.setStyleSheet("color:#1e293b;margin-top:12px;")
            self._cl.addWidget(l)

        titulo(f"BALANCE GENERAL\nFecha de corte: {bg['fecha_corte']}")
        sep()

        titulo("ACTIVO", 13)
        linea("Total Activo", bg["activo"], negrita=True, color="#15803d", indent=0)
        sep()

        titulo("PASIVO + PATRIMONIO", 13)
        linea("Total Pasivo",     bg["pasivo"],     indent=1)
        linea("Total Patrimonio", bg["patrimonio"], indent=1)
        linea("  (incl. Utilidad del ejercicio)",
              bg["utilidad_ejercicio"], indent=2, color="#1d4ed8")
        sep()
        linea("TOTAL PASIVO + PATRIMONIO",
              bg["total_pasivo_patrim"], negrita=True, color="#15803d")
        sep()

        diff = bg["diferencia"]
        color_diff = "#15803d" if abs(diff) < Decimal("1") else "#b91c1c"
        linea("Diferencia (debe ser $0)", diff, negrita=True, color=color_diff)
        if abs(diff) > Decimal("1"):
            msg = QLabel("⚠️  El balance no cuadra. Revisa asientos sin contrapartida.")
            msg.setStyleSheet("color:#b91c1c;font-size:11px;margin-top:4px;")
            self._cl.addWidget(msg)

        self._cl.addStretch()

    def _exportar(self):
        if not self._bg:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar", "balance_general.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            bg = self._bg
            rows = [
                ["Concepto", "Valor"],
                ["Total Activo",             bg["activo"]],
                ["Total Pasivo",             bg["pasivo"]],
                ["Total Patrimonio",         bg["patrimonio"]],
                ["Utilidad del ejercicio",   bg["utilidad_ejercicio"]],
                ["Total Pasivo+Patrimonio",  bg["total_pasivo_patrim"]],
                ["Diferencia",               bg["diferencia"]],
            ]
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerows(rows)
            QMessageBox.information(self, "Exportado", f"✅ {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 4 — Cartera (Cuentas por cobrar / pagar)
# ══════════════════════════════════════════════════════════════
class TabCartera(QWidget):
    def __init__(self, service: ReportesService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        fil = QHBoxLayout()
        self.de_corte = QDateEdit(QDate.currentDate())
        self.de_corte.setCalendarPopup(True); self.de_corte.setFixedWidth(130)
        self.cb_tipo = QComboBox(); self.cb_tipo.setFixedWidth(180)
        self.cb_tipo.addItem("Cuentas por cobrar (clientes)", "cobrar")
        self.cb_tipo.addItem("Cuentas por pagar (proveedores)", "pagar")
        btn_gen = QPushButton("📊 Generar"); btn_gen.setStyleSheet(BTN_PRIMARY)
        btn_gen.clicked.connect(self._generar)
        self.btn_exp = QPushButton("📥 Exportar CSV"); self.btn_exp.setStyleSheet(BTN_EXPORT)
        self.btn_exp.setEnabled(False); self.btn_exp.clicked.connect(self._exportar)
        fil.addWidget(QLabel("Corte:")); fil.addWidget(self.de_corte)
        fil.addWidget(self.cb_tipo); fil.addWidget(btn_gen)
        fil.addStretch(); fil.addWidget(self.btn_exp)
        lay.addLayout(fil)

        # Resumen vencimiento
        self.grp_vcto = QGroupBox("Resumen por antigüedad")
        self.grp_vcto.setStyleSheet("QGroupBox{font-weight:bold;}")
        self.grp_vcto.setVisible(False)
        vl = QHBoxLayout(self.grp_vcto)
        self._vcto_lbls = {}
        for key, label in [
            ("vigente",  "Por vencer"),
            ("d30",      "1–30 días"),
            ("d60",      "31–60 días"),
            ("d90",      "61–90 días"),
            ("d90mas",   "+90 días"),
            ("total",    "TOTAL"),
        ]:
            col = QVBoxLayout()
            lk  = QLabel(label); lk.setStyleSheet("color:#64748b;font-size:11px;")
            lk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lv  = QLabel("$0"); lv.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lk); col.addWidget(lv)
            self._vcto_lbls[key] = lv; vl.addLayout(col)
            if key != "total":
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color:#e2e8f0;"); vl.addWidget(sep)
        lay.addWidget(self.grp_vcto)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels([
            "No. Documento", "Tercero", "Fecha", "Vence",
            "Días vencido", "Saldo"
        ])
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 120); self.tabla.setColumnWidth(2, 90)
        self.tabla.setColumnWidth(3, 90); self.tabla.setColumnWidth(4, 95)
        self.tabla.setColumnWidth(5, 120)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setFont(QFont("Segoe UI", 11))
        lay.addWidget(self.tabla)

        self._datos = []

    def _generar(self):
        self.service.db.expire_all()
        qd = self.de_corte.date()
        f  = date(qd.year(), qd.month(), qd.day())
        tipo = self.cb_tipo.currentData()
        try:
            datos = (self.service.cartera_clientes(f) if tipo == "cobrar"
                     else self.service.cartera_proveedores(f))
            self._datos = datos
            self._renderizar(datos, f)
            self.btn_exp.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _renderizar(self, datos, fecha_corte):
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)
        vcto = {"vigente": Decimal("0"), "d30": Decimal("0"), "d60": Decimal("0"),
                "d90": Decimal("0"), "d90mas": Decimal("0"), "total": Decimal("0")}

        for d in datos:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            self.tabla.setItem(r, 0, QTableWidgetItem(d["numero"]))
            self.tabla.setItem(r, 1, QTableWidgetItem(d["tercero"]))
            self.tabla.setItem(r, 2, QTableWidgetItem(str(d["fecha"])))
            self.tabla.setItem(r, 3, QTableWidgetItem(str(d["fecha_vence"]) if d["fecha_vence"] else "—"))
            dias = d["dias_vencido"]
            dias_item = QTableWidgetItem(str(dias) if dias > 0 else "—")
            if dias > 0:
                dias_item.setForeground(QColor("#b91c1c"))
                dias_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.tabla.setItem(r, 4, dias_item)
            saldo = d["saldo"]
            sal_item = QTableWidgetItem(_fmt(saldo))
            sal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(r, 5, sal_item)

            # Clasificar
            if dias == 0:
                vcto["vigente"] += saldo
            elif dias <= 30:
                vcto["d30"] += saldo
            elif dias <= 60:
                vcto["d60"] += saldo
            elif dias <= 90:
                vcto["d90"] += saldo
            else:
                vcto["d90mas"] += saldo
            vcto["total"] += saldo

        self.tabla.blockSignals(False)

        for key, lbl in self._vcto_lbls.items():
            lbl.setText(_fmt(vcto[key]))
        self._vcto_lbls["total"].setStyleSheet(
            "color:#b91c1c;font-size:13px;font-weight:bold;"
            if vcto["total"] > 0 else "color:#15803d;font-size:13px;font-weight:bold;"
        )
        self.grp_vcto.setVisible(True)

    def _exportar(self):
        if not self._datos:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar", "cartera.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Número", "Tercero", "Fecha", "Vence", "Días vencido", "Saldo"])
                for d in self._datos:
                    w.writerow([d["numero"], d["tercero"], d["fecha"],
                                 d["fecha_vence"] or "", d["dias_vencido"], d["saldo"]])
            QMessageBox.information(self, "Exportado", f"✅ {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 5 — Resumen de Ventas
# ══════════════════════════════════════════════════════════════
class TabVentas(QWidget):
    def __init__(self, service: ReportesService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.setSpacing(10)

        fil = QHBoxLayout()
        self.filtro = FiltroPeriodo(self.service)
        btn_gen = QPushButton("📊 Generar"); btn_gen.setStyleSheet(BTN_PRIMARY)
        btn_gen.clicked.connect(self._generar)
        self.btn_exp = QPushButton("📥 Exportar CSV"); self.btn_exp.setStyleSheet(BTN_EXPORT)
        self.btn_exp.setEnabled(False); self.btn_exp.clicked.connect(self._exportar)
        fil.addWidget(self.filtro); fil.addWidget(btn_gen)
        fil.addStretch(); fil.addWidget(self.btn_exp)
        lay.addLayout(fil)

        # Resumen tarjetas
        self.grp_res = QGroupBox("Resumen del período")
        self.grp_res.setStyleSheet("QGroupBox{font-weight:bold;}")
        self.grp_res.setVisible(False)
        rl = QHBoxLayout(self.grp_res)
        self._res_lbls = {}
        for key, label, color in [
            ("n_facturas",    "Facturas",         "#374151"),
            ("subtotal",      "Subtotal",          "#1d4ed8"),
            ("total_iva",     "IVA",               "#6d28d9"),
            ("total_bruto",   "Total Bruto",       "#15803d"),
            ("notas_credito", "Notas Crédito",     "#b91c1c"),
            ("total_neto",    "TOTAL NETO",        "#1d4ed8"),
        ]:
            col = QVBoxLayout()
            lk  = QLabel(label); lk.setStyleSheet("color:#64748b;font-size:11px;")
            lk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lv  = QLabel("—")
            lv.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lv.setStyleSheet(f"color:{color};")
            lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lk); col.addWidget(lv)
            self._res_lbls[key] = lv; rl.addLayout(col)
            if key != "total_neto":
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color:#e2e8f0;"); rl.addWidget(sep)
        lay.addWidget(self.grp_res)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tabla documentos
        self.tbl_docs = QTableWidget(0, 5)
        self.tbl_docs.setHorizontalHeaderLabels([
            "No.", "Fecha", "Cliente", "Subtotal", "Total"
        ])
        hh1 = self.tbl_docs.horizontalHeader()
        hh1.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_docs.setColumnWidth(0, 100); self.tbl_docs.setColumnWidth(1, 90)
        self.tbl_docs.setColumnWidth(3, 100); self.tbl_docs.setColumnWidth(4, 110)
        self.tbl_docs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_docs.verticalHeader().setVisible(False)
        self.tbl_docs.setAlternatingRowColors(True)
        self.tbl_docs.setFont(QFont("Segoe UI", 11))
        splitter.addWidget(self.tbl_docs)

        # Top clientes
        grp_tc = QGroupBox("Top 10 clientes")
        grp_tc.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl = QVBoxLayout(grp_tc)
        self.tbl_top = QTableWidget(0, 2)
        self.tbl_top.setHorizontalHeaderLabels(["Cliente", "Total"])
        self.tbl_top.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_top.setColumnWidth(1, 110)
        self.tbl_top.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_top.verticalHeader().setVisible(False)
        self.tbl_top.setAlternatingRowColors(True)
        gl.addWidget(self.tbl_top)
        splitter.addWidget(grp_tc)
        splitter.setSizes([600, 300])
        lay.addWidget(splitter)

        self._datos = None

    def _generar(self):
        self.service.db.expire_all()
        f1, f2 = self.filtro.fechas()
        try:
            res = self.service.resumen_ventas(f1, f2)
            self._datos = res
            self._renderizar(res)
            self.btn_exp.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _renderizar(self, res: dict):
        # Tarjetas
        self._res_lbls["n_facturas"].setText(str(res["n_facturas"]))
        for key in ["subtotal","total_iva","total_bruto","notas_credito","total_neto"]:
            self._res_lbls[key].setText(_fmt(res[key]))
        self.grp_res.setVisible(True)

        # Tabla documentos
        self.tbl_docs.setRowCount(0)
        for d in res["documentos"]:
            r = self.tbl_docs.rowCount(); self.tbl_docs.insertRow(r)
            self.tbl_docs.setItem(r, 0, QTableWidgetItem(d.numero))
            self.tbl_docs.setItem(r, 1, QTableWidgetItem(str(d.fecha)))
            t_nom = d.tercero.nombre if d.tercero else "—"
            self.tbl_docs.setItem(r, 2, QTableWidgetItem(t_nom))
            for col, val in [(3, d.subtotal), (4, d.total)]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_docs.setItem(r, col, it)

        # Top clientes
        self.tbl_top.setRowCount(0)
        for i, c in enumerate(res["top_clientes"]):
            r = self.tbl_top.rowCount(); self.tbl_top.insertRow(r)
            rk = QTableWidgetItem(f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}.'} {c['nombre']}")
            self.tbl_top.setItem(r, 0, rk)
            it = QTableWidgetItem(_fmt(c["total"]))
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            it.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold if i == 0 else QFont.Weight.Normal))
            self.tbl_top.setItem(r, 1, it)

    def _exportar(self):
        if not self._datos:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar", "ventas.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Número", "Fecha", "Cliente", "Subtotal", "IVA", "Total"])
                for d in self._datos["documentos"]:
                    w.writerow([
                        d.numero, d.fecha,
                        d.tercero.nombre if d.tercero else "",
                        d.subtotal, d.total_impuesto, d.total
                    ])
            QMessageBox.information(self, "Exportado", f"✅ {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Widget principal: Módulo Reportes
# ══════════════════════════════════════════════════════════════
class ReportesWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        self.service = ReportesService(self.session, empresa_id)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)

        titulo = QLabel("📊  Reportes")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        lay.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 16px;font-size:12px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#2563eb;}"
        )

        self.tabs.addTab(TabLibroMayor(self.service),       "📒 Libro Mayor")
        self.tabs.addTab(TabEstadoResultados(self.service), "📈 Estado de Resultados")
        self.tabs.addTab(TabBalanceGeneral(self.service),   "⚖️ Balance General")
        self.tabs.addTab(TabCartera(self.service),          "💳 Cartera")
        self.tabs.addTab(TabVentas(self.service),           "🛒 Ventas")

        self.tabs.currentChanged.connect(lambda _: self.session.expire_all())
        lay.addWidget(self.tabs)

    def closeEvent(self, event):
        self.session.close(); super().closeEvent(event)
