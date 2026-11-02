"""FloofyWallet desktop preview: read-only address explorer.

Run: python -m floofywallet.desktop
Encrypted experimental test vault available; signing disabled.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QCheckBox,
)

from .addresses import validate_address
from .explorer_client import ExplorerClient, ExplorerError
from .vault import VaultError, generate_wallet, encrypt_wif, decrypt_wif, load_vault, save_vault, address_from_wif

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
        self.wallet_address = None
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
        self.welcome = self.make_welcome()
        self.pages.addWidget(self.welcome)
        self.dashboard = self.make_dashboard()
        self.pages.addWidget(self.dashboard)
        self.receive = self.make_receive()
        self.pages.addWidget(self.receive)
        self.send = self.make_simple_page("Send FLOOF", "Sending is disabled in this read-only preview. No private keys are stored.")
        self.pages.addWidget(self.send)
        self.history_page = self.make_simple_page("Transaction history", "Load an address in Dashboard to see its confirmed history.")
        self.pages.addWidget(self.history_page)
        self.settings = self.make_settings()
        self.pages.addWidget(self.settings)
        self.show_page("Welcome")

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

    def make_welcome(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(16)
        layout.addWidget(self.image_label("logo.png", 210, 180), alignment=Qt.AlignHCenter)
        layout.addWidget(label("Welcome to FloofyWallet", 30, True), alignment=Qt.AlignHCenter)
        layout.addWidget(label("Experimental test wallets only. No real funds.", 14, muted=True))
        for title, action in (("Create test wallet", self.create_wallet),
                              ("Import test WIF", self.import_wallet),
                              ("Unlock encrypted wallet", self.open_wallet)):
            button = QPushButton(title)
            button.setObjectName("primary")
            button.clicked.connect(action)
            layout.addWidget(button)
        layout.addStretch()
        return w

    def recovery_dialog(self, wif, address):
        dialog = QDialog(self)
        dialog.setWindowTitle("TEST recovery key — shown once")
        dialog.resize(660, 300)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Save this test WIF offline. Anyone with it controls the wallet.", 13, True))
        field = QLineEdit(wif)
        field.setReadOnly(True)
        field.setEchoMode(QLineEdit.Password)
        layout.addWidget(field)
        show = QCheckBox("Show recovery WIF")
        show.toggled.connect(lambda visible: field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password))
        layout.addWidget(show)
        copy = QPushButton("Copy WIF (clipboard is not secure)")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(wif))
        layout.addWidget(copy)
        layout.addWidget(label("Public address: " + address, 12))
        confirmed = QCheckBox("I have saved my TEST recovery WIF.")
        layout.addWidget(confirmed)
        proceed = QPushButton("Continue to wallet")
        proceed.setObjectName("primary")
        proceed.setEnabled(False)
        confirmed.toggled.connect(proceed.setEnabled)
        proceed.clicked.connect(dialog.accept)
        layout.addWidget(proceed)
        return dialog.exec_() == QDialog.Accepted

    def make_receive(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.addWidget(label("Receive FLOOF", 26, True))
        layout.addWidget(label("Experimental test wallets only. Never use real funds.", 13, muted=True))
        self.receive_address = QLineEdit()
        self.receive_address.setReadOnly(True)
        self.receive_address.setPlaceholderText("Create or unlock a test wallet in Settings")
        layout.addWidget(self.receive_address)
        copy = QPushButton("Copy public address")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.wallet_address or ""))
        layout.addWidget(copy)
        layout.addStretch()
        return w

    def make_settings(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(14)
        layout.addWidget(label("Encrypted test wallet", 26, True))
        layout.addWidget(label("Experimental and unaudited. Never import real keys or send funds.", 13, muted=True))
        self.wallet_status = label("No wallet opened", 14, True)
        layout.addWidget(self.wallet_status)
        for title, callback in (
            ("Create test wallet", self.create_wallet),
            ("Import test WIF", self.import_wallet),
            ("Unlock encrypted wallet", self.open_wallet),
            ("Lock wallet", self.lock_wallet),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addStretch()
        return w

    def password_dialog(self, title, confirm=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        form = QFormLayout(dialog)
        password = QLineEdit()
        password.setEchoMode(QLineEdit.Password)
        form.addRow("Password (12+ characters):", password)
        repeated = None
        if confirm:
            repeated = QLineEdit()
            repeated.setEchoMode(QLineEdit.Password)
            form.addRow("Confirm password:", repeated)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec_() != QDialog.Accepted:
            return None
        value = password.text()
        if len(value) < 12 or (repeated is not None and repeated.text() != value):
            QMessageBox.warning(self, "Password error", "Use 12+ characters and matching passwords.")
            return None
        return value

    def save_test_wallet(self, wif, password):
        filename, _ = QFileDialog.getSaveFileName(self, "Save encrypted test wallet", "", "Floofy vault (*.floofvault)")
        if not filename:
            return False
        path = Path(filename)
        if path.suffix.lower() != ".floofvault":
            path = path.with_suffix(".floofvault")
        if path.exists():
            QMessageBox.warning(self, "File exists", "Choose another filename. Existing vaults are never overwritten.")
            return False
        vault = encrypt_wif(wif, password)
        save_vault(path, vault)
        return path

    def activate_wallet(self, path, address):
        self.wallet_address = address
        self.wallet_status.setText("Unlocked test wallet: " + address)
        self.receive_address.setText(address)
        self.address_input.setText(address)
        self.show_page("Dashboard")
        self.load_address()

    def create_wallet(self):
        if QMessageBox.warning(self, "Test wallets only",
                "Create a disposable test wallet? Do not deposit real funds. "
                "You must record the recovery WIF offline.",
                QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        password = self.password_dialog("Create test wallet", confirm=True)
        if password is None:
            return
        try:
            wif, address = generate_wallet()
            path = self.save_test_wallet(wif, password)
            if path:
                if self.recovery_dialog(wif, address):
                    self.activate_wallet(path, address)
                else:
                    self.show_page("Welcome")
        except (OSError, ValueError, VaultError) as exc:
            QMessageBox.warning(self, "Wallet error", str(exc))

    def import_wallet(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Import disposable TEST WIF")
        form = QFormLayout(dialog)
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        form.addRow("Test WIF:", field)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec_() != QDialog.Accepted:
            return
        wif = field.text().strip()
        try:
            address_from_wif(wif)
        except ValueError:
            QMessageBox.warning(self, "Invalid WIF", "Invalid FloofyChain mainnet WIF.")
            return
        password = self.password_dialog("Encrypt imported test WIF", confirm=True)
        if password is None:
            return
        try:
            path = self.save_test_wallet(wif, password)
            if path:
                self.activate_wallet(path, address_from_wif(wif))
        except (OSError, ValueError, VaultError) as exc:
            QMessageBox.warning(self, "Wallet error", str(exc))

    def open_wallet(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open encrypted test wallet", "", "Floofy vault (*.floofvault)")
        if not filename:
            return
        password = self.password_dialog("Unlock test wallet")
        if password is None:
            return
        try:
            vault = load_vault(filename)
            wif = decrypt_wif(vault, password)
            address = address_from_wif(wif)
            del wif
            self.activate_wallet(filename, address)
        except (OSError, ValueError, VaultError) as exc:
            QMessageBox.warning(self, "Cannot unlock", str(exc))

    def lock_wallet(self):
        self.wallet_address = None
        self.wallet_status.setText("Wallet locked")
        self.receive_address.clear()
        self.address_input.clear()
        self.balance_label.setText("— FLOOF")
        self.received_label.setText("—")
        self.txcount_label.setText("—")
        self.activity.setText("No address loaded yet.")
        self.utxo_count.setText("UTXOs: —")
        self.status.setText("Wallet locked.")
        self.show_page("Welcome")

    def make_simple_page(self, title, description):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.addWidget(label(title, 26, True))
        layout.addWidget(label(description, 14, muted=True))
        layout.addStretch()
        return w

    def show_page(self, name):
        if self.wallet_address is None and name != "Welcome":
            name = "Welcome"
        index = ("Welcome", "Dashboard", "Receive", "Send", "History", "Settings").index(name)
        for button in self.nav.values():
            button.setVisible(self.wallet_address is not None)
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
