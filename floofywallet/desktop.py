"""FloofyWallet desktop preview: read-only address explorer.

Run: python -m floofywallet.desktop
No key storage or transaction signing is enabled in this preview.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .addresses import validate_address
from .explorer_client import ExplorerClient, ExplorerError

ASSETS = Path(__file__).resolve().parent / "assets"
BLUE = "#0879DF"
NAVY = "#09204D"
STYLE = """
QMainWindow, QWidget#root { background: #F3FAFF; }
QFrame#sidebar { background: #FFFFFF; border-right: 1px solid #D9EAF7; }
QFrame#hero { background: #DDF3FF; border-radius: 22px; }
QFrame#panel { background: white; border: 1px solid #D8EAF7; border-radius: 18px; }
QLabel { color: #09204D; font-family: 'Segoe UI'; }
QLabel#muted { color: #6283A3; }
QLabel#big { font-size: 33px; font-weight: 800; }
QLabel#heading { font-size: 23px; font-weight: 800; }
QPushButton { background: #E8F5FF; border: 0; border-radius: 12px; padding: 12px 16px;
              color: #09204D; font: 600 12px 'Segoe UI'; text-align: left; }
QPushButton:hover { background: #D3EDFF; }
QPushButton#selected { background: #0879DF; color: white; }
QPushButton#primary { background: #0879DF; color: white; text-align: center; }
QPushButton:disabled { color: #8B9CAC; background: #E9EEF3; }
QLineEdit { background: white; color: #09204D; border: 1px solid #B7D7EE;
            border-radius: 10px; padding: 12px; font: 12px 'Segoe UI'; }
"""


def label(text, size=13, bold=False, muted=False):
    w = QLabel(text)
    w.setWordWrap(True)
    w.setStyleSheet("font-size: %dpx; font-weight: %d; color: %s;" %
                    (size, 750 if bold else 400, "#6283A3" if muted else NAVY))
    return w


def panel():
    f = QFrame()
    f.setObjectName("panel")
    f.setLayout(QVBoxLayout())
    f.layout().setContentsMargins(22, 20, 22, 20)
    f.layout().setSpacing(10)
    return f


class AddressWorker(QObject):
    finished = pyqtSignal(object, object, object)
    failed = pyqtSignal(str)

    def __init__(self, address):
        super().__init__()
        self.address = address

    def run(self):
        try:
            client = ExplorerClient()
            summary = client.get_address(self.address)
            history = client.get_address_transactions(self.address)
            utxos = client.get_address_utxos(self.address)
            self.finished.emit(summary, history, utxos)
        except (ExplorerError, ValueError, OSError) as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("Unexpected explorer response")


class WalletWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FloofyWallet — Desktop Preview")
        self.resize(1190, 760)
        self.setMinimumSize(900, 600)
        self.thread = None
        self.worker = None
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(225)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 25, 18, 20)
        side.setSpacing(10)
        side.addWidget(label("✦  FloofyWallet", 21, True))
        side.addSpacing(25)
        self.nav = {}
        for name in ("Dashboard", "Receive", "Send", "History", "Settings"):
            b = QPushButton(name)
            b.clicked.connect(lambda checked=False, n=name: self.show_page(n))
            side.addWidget(b)
            self.nav[name] = b
        side.addStretch()
        mascot = self.image_label("Floofy_Icone.png", 150, 150)
        side.addWidget(mascot, alignment=Qt.AlignHCenter)
        side.addWidget(label("Powered by FloofyChain", 11, muted=True), alignment=Qt.AlignHCenter)
        outer.addWidget(sidebar)

        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.dashboard = self.make_dashboard()
        self.pages.addWidget(self.dashboard)
        self.receive = self.make_receive()
        self.pages.addWidget(self.receive)
        self.send = self.make_simple_page("Send FLOOF", "Sending is disabled in this read-only preview. No private keys are stored.")
        self.pages.addWidget(self.send)
        self.history_page = self.make_simple_page("Transaction history", "Load an address in Dashboard to see its confirmed history.")
        self.pages.addWidget(self.history_page)
        self.settings = self.make_simple_page("Settings", "Experimental preview • Explorer data is third-party and may be stale.")
        self.pages.addWidget(self.settings)
        self.show_page("Dashboard")

    def image_label(self, filename, width, height):
        w = QLabel()
        w.setAlignment(Qt.AlignCenter)
        pix = QPixmap(str(ASSETS / filename))
        if pix.isNull():
            w.setText("🐹" if filename == "logo.png" else "😎")
            w.setStyleSheet("font-size: 60px;")
        else:
            w.setPixmap(pix.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return w

    def make_dashboard(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(28, 26, 28, 26)
        col.setSpacing(20)
        hero = QFrame()
        hero.setObjectName("hero")
        hero.setMinimumHeight(170)
        h = QHBoxLayout(hero)
        h.setContentsMargins(25, 15, 25, 15)
        words = QVBoxLayout()
        words.addWidget(label("FloofyWallet", 35, True))
        words.addWidget(label("Your FLOOF, your keys, your future.", 15))
        words.addStretch()
        h.addLayout(words, 1)
        h.addWidget(self.image_label("logo.png", 205, 150))
        col.addWidget(hero)

        search = panel()
        search.layout().addWidget(label("Explore a public FLOOF address", 15, True))
        bar = QHBoxLayout()
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Paste a public FloofyChain address (starts with F)")
        self.address_input.returnPressed.connect(self.load_address)
        bar.addWidget(self.address_input, 1)
        self.load_button = QPushButton("Load address")
        self.load_button.setObjectName("primary")
        self.load_button.clicked.connect(self.load_address)
        bar.addWidget(self.load_button)
        search.layout().addLayout(bar)
        self.status = label("Read-only preview • No wallet keys are imported.", 11, muted=True)
        search.layout().addWidget(self.status)
        col.addWidget(search)

        stats = QHBoxLayout()
        balance = panel()
        balance.layout().addWidget(label("Total balance", 14, True))
        self.balance_label = label("— FLOOF", 29, True)
        balance.layout().addWidget(self.balance_label)
        stats.addWidget(balance, 2)
        received = panel()
        received.layout().addWidget(label("Received", 14, True))
        self.received_label = label("—", 19, True)
        received.layout().addWidget(self.received_label)
        stats.addWidget(received, 1)
        txs = panel()
        txs.layout().addWidget(label("Transactions", 14, True))
        self.txcount_label = label("—", 19, True)
        txs.layout().addWidget(self.txcount_label)
        stats.addWidget(txs, 1)
        col.addLayout(stats)

        activity = panel()
        activity.layout().addWidget(label("Recent transactions", 19, True))
        self.activity = label("No address loaded yet.", 12, muted=True)
        activity.layout().addWidget(self.activity)
        self.utxo_count = label("UTXOs: —", 12, muted=True)
        activity.layout().addWidget(self.utxo_count)
        col.addWidget(activity)
        col.addStretch()
        scroll.setWidget(content)
        return scroll

    def make_receive(self):
        return self.make_simple_page(
            "Receive FLOOF",
            "Wallet creation and encrypted key storage are not implemented yet. "
            "For now, use Dashboard to inspect an existing public address.")

    def make_simple_page(self, title, description):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.addWidget(label(title, 26, True))
        layout.addWidget(label(description, 14, muted=True))
        layout.addStretch()
        return w

    def show_page(self, name):
        index = ("Dashboard", "Receive", "Send", "History", "Settings").index(name)
        self.pages.setCurrentIndex(index)
        for key, button in self.nav.items():
            button.setObjectName("selected" if key == name else "")
            button.style().unpolish(button)
            button.style().polish(button)

    def load_address(self):
        address = self.address_input.text().strip()
        if not validate_address(address):
            QMessageBox.warning(self, "Invalid address", "Enter a valid FloofyChain mainnet address.")
            return
        if self.thread is not None:
            return
        self.status.setText("Loading explorer data…")
        self.load_button.setEnabled(False)
        self.thread = QThread()
        self.worker = AddressWorker(address)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.loaded)
        self.worker.failed.connect(self.load_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.cleanup_worker)
        self.thread.start()

    def cleanup_worker(self):
        self.thread = None
        self.worker = None
        self.load_button.setEnabled(True)

    def loaded(self, summary, history, utxos):
        self.balance_label.setText(f"{summary.balance:.8f} FLOOF")
        self.received_label.setText(f"{summary.received:.8f}")
        self.txcount_label.setText(str(summary.txcount))
        self.utxo_count.setText(f"Unspent outputs: {len(utxos)} (spendability not verified)")
        if not history:
            self.activity.setText("No confirmed transactions in the first page.")
        else:
            lines = []
            for tx in history[:8]:
                when = datetime.fromtimestamp(tx.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                lines.append(f"{when}    {tx.txid[:12]}…    {tx.amount:.8f} FLOOF")
            self.activity.setText("\n\n".join(lines))
        self.status.setText(f"Explorer: {summary.source} • Read-only • Data may be stale")

    def load_failed(self, error):
        self.status.setText("Could not load address: " + error)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = WalletWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
