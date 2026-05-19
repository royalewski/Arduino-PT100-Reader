import sys, threading, json, time, os, csv, math
import serial, serial.tools.list_ports
import matplotlib.dates as mdates
import datetime

# --- GUI backend: PySide6 albo PyQt6 (auto-fallback) ---
try:
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
        QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
        QFileDialog, QCheckBox, QSpinBox, QSizePolicy
    )
    USING_PYSIDE = True
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal, QObject
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
        QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
        QFileDialog, QCheckBox, QSpinBox, QSizePolicy
    )
    USING_PYSIDE = False

# --- Matplotlib (Qt canvas) ---
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

BAUD = 9600

# -------------------- Serial backend (wątek czytający) --------------------

class SerialBackend(QObject):
    line_received = Signal(str)
    status = Signal(str)
    connected = Signal(bool)

    def __init__(self):
        super().__init__()
        self.ser = None
        self._stop = False

    def open(self, port: str, baud: int = BAUD) -> bool:
        self.close()
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1, dsrdtr=False, rtscts=False)
            self.ser.setDTR(False)   # <- ważne
            self.ser.setRTS(False)
            self._stop = False
            t = threading.Thread(target=self._reader_loop, daemon=True)
            t.start()
            self.connected.emit(True)
            self.status.emit(f"Connected: {port} @ {baud}")
            return True
        except Exception as e:
            self.ser = None
            self.connected.emit(False)
            self.status.emit(f"ERR open: {e}")
            return False

    def close(self):
        self._stop = True
        if self.ser:
            try: self.ser.close()
            except: pass
        self.ser = None
        self.connected.emit(False)
        self.status.emit("Disconnected")

    def send_line(self, line: str):
        if not self.ser or not self.ser.is_open:
            self.status.emit("Not connected")
            return
        data = (line.strip() + "\n").encode("utf-8")
        try:
            self.ser.write(data)
        except Exception as e:
            self.status.emit(f"ERR write: {e}")

    def _reader_loop(self):
        buf = b""
        while not self._stop and self.ser and self.ser.is_open:
            try:
                chunk = self.ser.read(256)
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self.line_received.emit(line.decode(errors="replace").rstrip("\r"))
                else:
                    time.sleep(0.01)
            except Exception as e:
                self.status.emit(f"ERR read: {e}")
                break
        self.connected.emit(False)

# -------------------- CSV Logger --------------------

class CsvLogger:
    """
    Nagłówek CSV:
    timestamp_iso, epoch_ms, id, name, temp_c, source
    """
    def __init__(self):
        self.path = None
        self._file = None
        self._writer = None

    def set_path(self, path: str):
        self.close()
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        new_file = not os.path.exists(path) or os.path.getsize(path) == 0
        self._file = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if new_file:
            self._writer.writerow(["timestamp_iso", "epoch_ms", "id", "name", "temp_c", "source"])
            self._file.flush()

    def is_ready(self) -> bool:
        return self._writer is not None

    def log_temp(self, sid, name, temp, source="interval"):
        if not self.is_ready():
            return
        ts = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))
        epoch_ms = int(ts * 1000)
        try:
            tval = float(temp) if temp is not None else ""
        except:
            tval = ""
        self._writer.writerow([iso, epoch_ms, sid, name or "", tval, source])
        self._file.flush()

    def close(self):
        try:
            if self._file:
                self._file.flush()
                self._file.close()
        except:
            pass
        self._file = None
        self._writer = None

# -------------------- GUI --------------------

class PT100App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PT100 Manager (Serial)")
        self.backend = SerialBackend()
        self.backend.line_received.connect(self.on_line)
        self.backend.status.connect(self.on_status)
        self.backend.connected.connect(self.on_connected)

        # dane
        self.sensors = {}  # id(str) -> dict {name,pin,active,last_t,updated_ts}
        self.hist = {}     # id(str) -> list[(ts, temp)]
        self.csv = CsvLogger()

        layout = QVBoxLayout(self)

        # Port row
        row = QHBoxLayout()
        self.portBox = QComboBox()
        self.btnRefresh = QPushButton("Refresh Ports")
        self.btnConn = QPushButton("Connect")
        self.btnDis = QPushButton("Disconnect")
        row.addWidget(QLabel("Port:"))
        row.addWidget(self.portBox, 1)
        row.addWidget(self.btnRefresh)
        row.addWidget(self.btnConn)
        row.addWidget(self.btnDis)
        layout.addLayout(row)

        # CSV row
        csvrow = QHBoxLayout()
        self.btnPickCsv = QPushButton("Select CSV…")
        self.lblCsv = QLineEdit(); self.lblCsv.setReadOnly(True)
        self.chkAutoCsv = QCheckBox("Auto save ")
        self.btnDumpCsv = QPushButton("Save current logs")
        csvrow.addWidget(self.btnPickCsv)
        csvrow.addWidget(self.lblCsv, 1)
        csvrow.addWidget(self.chkAutoCsv)
        csvrow.addWidget(self.btnDumpCsv)
        layout.addLayout(csvrow)

        # Quick actions
        quick = QHBoxLayout()
        self.edId = QLineEdit();  self.edId.setPlaceholderText("id")
        self.edPin = QLineEdit(); self.edPin.setPlaceholderText("pin (A0)")
        self.edName = QLineEdit(); self.edName.setPlaceholderText("name")
        self.edT1 = QLineEdit();  self.edT1.setPlaceholderText("t1")
        self.edQ1 = QLineEdit();  self.edQ1.setPlaceholderText("q1")
        self.edT2 = QLineEdit();  self.edT2.setPlaceholderText("t2")
        self.edQ2 = QLineEdit();  self.edQ2.setPlaceholderText("q2")
        self.edInterval = QLineEdit(); self.edInterval.setPlaceholderText("interval ms")
        self.btnList = QPushButton("LIST")
        self.btnRead = QPushButton("READ")
        self.btnNew  = QPushButton("NEW")
        self.btnSet  = QPushButton("SET")
        self.btnDel  = QPushButton("DEL")
        for w in [self.edId, self.edPin, self.edName, self.edT1, self.edQ1, self.edT2, self.edQ2, self.edInterval,
                  self.btnList, self.btnRead, self.btnNew, self.btnSet, self.btnDel]:
            quick.addWidget(w)
        layout.addLayout(quick)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["id", "name", "pin", "active", "last temp [°C]", "updated"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch if not USING_PYSIDE else QHeaderView.Stretch)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # Plot controls + canvas
        pc = QHBoxLayout()
        self.plotSensor = QComboBox()
        self.plotWin = QSpinBox(); self.plotWin.setRange(1, 3600); self.plotWin.setValue(60)
        self.btnClearTrace = QPushButton("Clear")
        pc.addWidget(QLabel("Sensor:")); pc.addWidget(self.plotSensor)
        pc.addWidget(QLabel("Window [s]:")); pc.addWidget(self.plotWin)
        pc.addWidget(self.btnClearTrace)
        layout.addLayout(pc)

        self.fig = Figure(figsize=(5,3))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("time [HH:MM:SS]")
        self.ax.set_ylabel("temp [°C]")
        # Zwiększ margines na dole, aby podpisy czasu nie nachodziły na log
        self.fig.subplots_adjust(bottom=0.22)
        layout.addWidget(self.canvas, 2)

        # Log (mniejszy)
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setMaximumHeight(50)
        self.log.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.log, 0)

        # Signals
        self.btnRefresh.clicked.connect(self.refreshPorts)
        self.btnConn.clicked.connect(self.connectPort)
        self.btnDis.clicked.connect(self.backend.close)
        self.btnList.clicked.connect(lambda: self.backend.send_line("LIST"))
        self.btnRead.clicked.connect(self.sendRead)
        self.btnNew.clicked.connect(self.sendNew)
        self.btnSet.clicked.connect(self.sendSet)
        self.btnDel.clicked.connect(self.sendDel)
        self.table.itemSelectionChanged.connect(self.on_select_row)

        self.btnPickCsv.clicked.connect(self.pickCsv)
        self.btnDumpCsv.clicked.connect(self.dumpTableToCsv)
        self.btnClearTrace.clicked.connect(self.clearSelectedHistory)
        self.plotSensor.currentIndexChanged.connect(self.updatePlot)

        self.refreshPorts()
        self.updateButtons(False)

        # UI timer
        self.uiTimer = QTimer(self)
        self.uiTimer.setInterval(500)  # ms
        self.uiTimer.timeout.connect(self.on_ui_tick)
        self.uiTimer.start()

    # ---------- Ports ----------
    def refreshPorts(self):
        self.portBox.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.portBox.addItems(ports)

    def connectPort(self):
        port = self.portBox.currentText().strip()
        if not port:
            QMessageBox.warning(self, "Brak portu", "Wybierz port z listy.")
            return
        self.backend.open(port, BAUD)

    def on_connected(self, ok: bool):
        self.updateButtons(ok)

    def updateButtons(self, connected: bool):
        self.btnConn.setEnabled(not connected)
        self.btnDis.setEnabled(connected)
        for b in [self.btnList, self.btnRead, self.btnNew, self.btnSet, self.btnDel]:
            b.setEnabled(connected)

    # ---------- CSV ----------
    def pickCsv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Wybierz plik CSV", "pt100_log.csv", "CSV files (*.csv);;All files (*.*)")
        if not path: return
        try:
            self.csv.set_path(path)
            self.lblCsv.setText(path)
            self.log.append(f"# CSV: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Błąd CSV", str(e))

    def dumpTableToCsv(self):
        if not self.csv.is_ready():
            QMessageBox.information(self, "CSV", "Najpierw wybierz plik CSV.")
            return
        for sid, data in self.sensors.items():
            t = data.get("last_t")
            if t is not None:
                self.csv.log_temp(sid, data.get("name",""), t, source="list_export")
        self.log.append("# Tabela zapisana do CSV")

    # ---------- Commands ----------
    def getIdFromUI(self):
        sid = self.edId.text().strip()
        if not sid:
            QMessageBox.information(self, "Brak id", "Podaj id czujnika.")
            return None
        return sid

    def sendRead(self):
        sid = self.getIdFromUI()
        if sid is None: return
        self.backend.send_line(f"READ id={sid}")

    def sendDel(self):
        sid = self.getIdFromUI()
        if sid is None: return
        self.backend.send_line(f"DEL id={sid}")

    def sendNew(self):
        sid = self.getIdFromUI()
        if sid is None: return
        pin = self.edPin.text().strip() or "A0"
        name = self.edName.text().strip() or "PT100"
        parts = [f"NEW id={sid} active=1 pin={pin} name={name}"]
        if self.edT1.text().strip(): parts.append(f"t1={self.edT1.text().strip()}")
        if self.edQ1.text().strip(): parts.append(f"q1={self.edQ1.text().strip()}")
        if self.edT2.text().strip(): parts.append(f"t2={self.edT2.text().strip()}")
        if self.edQ2.text().strip(): parts.append(f"q2={self.edQ2.text().strip()}")
        if self.edInterval.text().strip(): parts.append(f"interval={self.edInterval.text().strip()}")
        cmd = " ".join(parts)
        self.log.append(f"> {cmd}")
        self.backend.send_line(cmd)

    def sendSet(self):
        sid = self.getIdFromUI()
        if sid is None: return
        parts = [f"SET id={sid}"]
        if self.edPin.text().strip(): parts.append(f"pin={self.edPin.text().strip()}")
        if self.edName.text().strip(): parts.append(f"name={self.edName.text().strip()}")
        if self.edT1.text().strip(): parts.append(f"t1={self.edT1.text().strip()}")
        if self.edQ1.text().strip(): parts.append(f"q1={self.edQ1.text().strip()}")
        if self.edT2.text().strip(): parts.append(f"t2={self.edT2.text().strip()}")
        if self.edQ2.text().strip(): parts.append(f"q2={self.edQ2.text().strip()}")
        if self.edInterval.text().strip(): parts.append(f"interval={self.edInterval.text().strip()}")
        cmd = " ".join(parts)
        self.log.append(f"> {cmd}")
        self.backend.send_line(cmd)

    # ---------- Parsing incoming ----------
    def on_line(self, line: str):
        line = line.strip()
        if not line: return
        self.log.append(line)

        # spróbuj JSON
        try:
            obj = json.loads(line)
        except Exception:
            return

        # LIST
        if isinstance(obj, dict) and "s" in obj and isinstance(obj["s"], list):
            self.apply_list(obj["s"])
            return

        # READ / auto-raport
        if isinstance(obj, dict) and ("id" in obj) and ("t" in obj):
            sid = str(obj.get("id"))
            name = obj.get("name")
            pin = obj.get("pin")  # może być int lub string
            t = obj.get("t")
            self.apply_temp(sid, name, pin, t)

            # CSV auto
            if self.chkAutoCsv.isChecked() and self.csv.is_ready():
                source = "read" if obj.get("ok") else "interval"
                self.csv.log_temp(sid, name, t, source=source)
            return

    def apply_list(self, lst):
        existing = self.sensors
        sensors = {}
        for it in lst:
            if "id" not in it: continue
            sid = str(it["id"])
            entry = {
                "name": it.get("name", ""),
                "pin":  it.get("pin", ""),
                "active": bool(it.get("active", 0)),
                "last_t": existing.get(sid, {}).get("last_t"),
                "updated_ts": existing.get(sid, {}).get("updated_ts"),
            }
            sensors[sid] = entry
            if sid not in self.hist:
                self.hist[sid] = []
        self.sensors = sensors
        self.rebuildPlotSensorList()
        self.refreshTable()
        # jeśli nic nie wybrane na wykresie, wybierz pierwszy
        if self.plotSensor.currentIndex() < 0 and self.plotSensor.count() > 0:
            self.plotSensor.setCurrentIndex(0)

    def apply_temp(self, sid, name, pin, t):
        # sid to już string
        if sid not in self.sensors:
            self.sensors[sid] = {"name": name or "",  "pin": (str(pin) if pin is not None else ""), "active": True, "last_t": t, "updated_ts": time.time()}
            if sid not in self.hist:
                self.hist[sid] = []
            # upewnij się, że wpadnie też na listę wyboru wykresu
            self.rebuildPlotSensorList()
            if self.plotSensor.currentIndex() < 0:
                # auto-wybierz pierwszy dostępny (w tym nowy)
                self.plotSensor.setCurrentIndex(0)
        else:
            if name: self.sensors[sid]["name"] = name
            if pin is not None: self.sensors[sid]["pin"] = str(pin)
            self.sensors[sid]["last_t"] = t
            self.sensors[sid]["updated_ts"] = time.time()

        # dodaj do historii z bezpiecznym castem
        try:
            val = float(t)
        except Exception:
            return  # nieprawidłowa liczba – pomiń
        self.hist.setdefault(sid, []).append((time.time(), val))
        if len(self.hist[sid]) > 20000:
            self.hist[sid] = self.hist[sid][-20000:]
        self.refreshTable()

    def refreshTable(self):
        items = sorted(self.sensors.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else str(kv[0]))
        self.table.setRowCount(len(items))
        now = time.time()
        for row, (sid, data) in enumerate(items):
            def setcell(c, text):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if not USING_PYSIDE else Qt.AlignCenter)
                self.table.setItem(row, c, item)

            setcell(0, sid)
            setcell(1, str(data.get("name","")))
            setcell(2, str(data.get("pin","")))
            setcell(3, "1" if data.get("active") else "0")

            t = data.get("last_t")
            ts = data.get("updated_ts")
            if t is None:
                setcell(4, "-"); setcell(5, "-")
            else:
                age = now - (ts or now)
                try:
                    txt = f"{float(t):.2f}"
                except Exception:
                    txt = str(t)
                setcell(4, txt)
                age_txt = "now" if age < 0.5 else f"{int(age)}s ago"
                setcell(5, age_txt)

    # ---------- Plot ----------

    def rebuildPlotSensorList(self):
        prev_data = self.plotSensor.currentData()
        self.plotSensor.blockSignals(True)
        self.plotSensor.clear()
        ids = sorted(self.sensors.keys(), key=lambda x: int(x) if x.isdigit() else x)
        for sid in ids:
            s = self.sensors[sid]
            name = s.get("name","")
            pin  = s.get("pin","")
            label = f"{sid} (pin {pin}" + (f", {name})" if name else ")")
            # userData = sid (string) – spójnie z hist/sensors
            if hasattr(self.plotSensor, "addItem"):
                self.plotSensor.addItem(label, sid)
            else:
                self.plotSensor.addItem(label)  # fallback
        # przywróć poprzedni wybór jeśli możliwe
        if prev_data is not None:
            idx = -1
            # PySide6/PyQt6 różnie zwraca currentData(), więc porównujemy tekstowo
            for i in range(self.plotSensor.count()):
                data = self.plotSensor.itemData(i) if hasattr(self.plotSensor, "itemData") else None
                if (data is not None and str(data) == str(prev_data)) or self.plotSensor.itemText(i) == str(prev_data):
                    idx = i; break
            if idx >= 0:
                self.plotSensor.setCurrentIndex(idx)
        self.plotSensor.blockSignals(False)

    def clearSelectedHistory(self):
        sid = self.plotSensor.currentData()
        if sid is None and self.plotSensor.currentIndex() >= 0:
            # fallback: weź tekst i wyciągnij id z prefixu
            text = self.plotSensor.currentText()
            sid = text.split(" ", 1)[0]
        if sid is None: return
        self.hist[sid] = []
        self.updatePlot()

    def on_ui_tick(self):
        self.refreshTable()
        self.updatePlot()

    def updatePlot(self):
        # pobierz aktualny wybór
        sid = self.plotSensor.currentData()
        if sid is None and self.plotSensor.currentIndex() >= 0:
            text = self.plotSensor.currentText()
            sid = text.split(" ", 1)[0]
        if sid is None:
            self.ax.clear()
            self.ax.set_xlabel("time [HH:MM:SS]")
            self.ax.set_ylabel("temp [°C]")
            self.fig.tight_layout()
            self.canvas.draw_idle()
            return

        window_s = max(1, int(self.plotWin.value()))
        now = time.time()
        series = self.hist.get(sid, [])
        series = [(ts, val) for (ts, val) in series if (now - ts) <= window_s]
        self.hist[sid] = series  # przycięte

        self.ax.clear()
        if series:
            xs = [datetime.datetime.fromtimestamp(ts) for ts, _ in series]
            ys = [val for _, val in series]
            self.ax.plot(xs, ys, linewidth=1.5)

            # format osi czasu: aktualne godziny HH:MM:SS + auto-lokatory
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            self.fig.autofmt_xdate(rotation=20, ha='center')  # czytelniejsze daty

            ymin, ymax = min(ys), max(ys)
            if math.isfinite(ymin) and math.isfinite(ymax) and ymin != ymax:
                pad = (ymax - ymin) * 0.1
                self.ax.set_ylim(ymin - pad, ymax + pad)

        self.ax.set_xlabel("time [HH:MM:SS]")
        self.ax.set_ylabel("temp [°C]")
        self.ax.grid(True, alpha=0.3)
        # utrzymaj większy margines na dolnej krawędzi dla etykiet czasu
        self.fig.subplots_adjust(bottom=0.22)
        self.canvas.draw_idle()

    # ---------- Selection & status ----------

    def on_select_row(self):
        row = self.table.currentRow()
        if row < 0: return
        sid = self.table.item(row, 0).text()
        name = self.table.item(row, 1).text()
        pin  = self.table.item(row, 2).text()
        self.edId.setText(sid)
        if not self.edName.text():
            self.edName.setText(name)
        if not self.edPin.text():
            self.edPin.setText(pin)
        # ustaw wykres na wybrany sensor
        idx = -1
        for i in range(self.plotSensor.count()):
            data = self.plotSensor.itemData(i) if hasattr(self.plotSensor, "itemData") else None
            if (data is not None and str(data) == sid) or self.plotSensor.itemText(i).startswith(sid):
                idx = i; break
        if idx >= 0:
            self.plotSensor.setCurrentIndex(idx)

    def on_status(self, msg: str):
        self.log.append(f"# {msg}")

# -------------------- main --------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PT100App()
    w.resize(1200, 860)
    w.show()
    sys.exit(app.exec())
