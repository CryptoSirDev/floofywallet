"""FloofyWallet desktop preview: read-only address explorer.

Run: python -m floofywallet.desktop
Encrypted experimental test vault available; signing disabled.
"""
import sys
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QCheckBox, QSpinBox,
)

import qrcode

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
        self.history_mode = 'wallet'
        self.requested_address = None
        self.requested_mode = None
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
        self.send = self.make_send()
        self.pages.addWidget(self.send)
        self.history_page = self.make_history()
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

        wallet_card = panel()
        wallet_card.layout().addWidget(label("Your wallet address", 15, True))
        address_row = QHBoxLayout()
        self.dashboard_address = QLineEdit()
        self.dashboard_address.setReadOnly(True)
        address_row.addWidget(self.dashboard_address, 1)
        copy_address = QPushButton("Copy address")
        copy_address.clicked.connect(self.copy_receive_address)
        address_row.addWidget(copy_address)
        wallet_card.layout().addLayout(address_row)
        self.status = label("Explorer data may be delayed.", 11, muted=True)
        wallet_card.layout().addWidget(self.status)
        col.addWidget(wallet_card)

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
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(15)
        layout.addWidget(label("Receive FLOOF", 26, True))
        layout.addWidget(label("Share only this public address to receive test FLOOF. Never share your WIF.", 13, muted=True))

        card = panel()
        card.layout().addWidget(label("Your unlocked wallet address", 16, True))
        self.receive_address = QLineEdit()
        self.receive_address.setReadOnly(True)
        self.receive_address.setPlaceholderText("Unlock a test wallet to see its address")
        card.layout().addWidget(self.receive_address)

        self.receive_qr = QLabel()
        self.receive_qr.setAlignment(Qt.AlignCenter)
        self.receive_qr.setMinimumHeight(280)
        card.layout().addWidget(self.receive_qr)

        self.receive_copy = QPushButton("Copy public address")
        self.receive_copy.setObjectName("primary")
        self.receive_copy.clicked.connect(self.copy_receive_address)
        card.layout().addWidget(self.receive_copy)
        self.receive_feedback = label("", 12, muted=True)
        card.layout().addWidget(self.receive_feedback)
        layout.addWidget(card)
        layout.addWidget(label(
            "QR contains the public address only (no WIF). "
            "Explorer balances may lag behind the blockchain. Test wallets only.",
            12, muted=True))
        layout.addStretch()
        self.update_receive()
        return w

    def update_receive(self):
        address = self.wallet_address
        self.receive_address.setText(address or "")
        self.receive_copy.setEnabled(bool(address))
        self.receive_feedback.setText("")
        if not address:
            self.receive_qr.clear()
            self.receive_qr.setText("Unlock a test wallet to display its QR code.")
            return
        # Plain address, rather than an unsupported payment URI scheme.
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=8, border=4)
        qr.add_data(address)
        qr.make(fit=True)
        buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
        pixmap = QPixmap()
        if pixmap.loadFromData(buffer.getvalue(), "PNG"):
            self.receive_qr.setPixmap(pixmap.scaled(
                280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.receive_qr.setText("QR unavailable. Copy the address above.")

    def copy_receive_address(self):
        if not self.wallet_address:
            return
        QApplication.clipboard().setText(self.wallet_address)
        self.receive_feedback.setText("Public address copied to clipboard.")

    def make_send(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(15)
        layout.addWidget(label("Send FLOOF", 26, True))
        layout.addWidget(label(
            "Transaction preview only. Signing and broadcasting are disabled. "
            "Do not use real funds.", 13, muted=True))
        card = panel()
        card.layout().addWidget(label("Destination address", 15, True))
        self.send_destination = QLineEdit()
        self.send_destination.setPlaceholderText("FloofyChain mainnet address (F...)")
        card.layout().addWidget(self.send_destination)
        card.layout().addWidget(label("Amount (FLOOF)", 15, True))
        self.send_amount = QLineEdit()
        self.send_amount.setPlaceholderText("e.g. 10.00000000")
        card.layout().addWidget(self.send_amount)
        card.layout().addWidget(label("Estimated network fee (FLOOF)", 15, True))
        self.send_fee = QLineEdit()
        self.send_fee.setReadOnly(True)
        self.send_fee.setText("Unavailable — UTXOs and fee rate not verified")
        card.layout().addWidget(self.send_fee)
        self.send_utxo_status = label("UTXO data: not loaded or verified", 12, muted=True)
        card.layout().addWidget(self.send_utxo_status)
        layout.addWidget(card)
        self.send_feedback = label(
            "Network fee will be calculated automatically once verified UTXOs "
            "and fee estimation are implemented. No manual fee entry.", 12, muted=True)
        layout.addWidget(self.send_feedback)
        preview = QPushButton("Preview transaction")
        preview.setObjectName("primary")
        preview.clicked.connect(self.preview_send)
        layout.addWidget(preview)
        self.send_preview = panel()
        self.send_preview.layout().addWidget(label("No transaction preview yet.", 13, muted=True))
        layout.addWidget(self.send_preview)
        simulator = panel()
        simulator.layout().addWidget(label("Fee simulator — TEST ONLY", 16, True))
        simulator.layout().addWidget(label(
            "Illustrative legacy P2PKH sizes. Uses the observed Core 4.0.4 "
            "relay fee of 0.001 FLOOF/kB, not a live network recommendation. "
            "No real UTXOs, signatures or broadcasts.", 12, muted=True))
        simulator.layout().addWidget(label("Simulated inputs (UTXOs)", 13, True))
        self.sim_inputs = QSpinBox()
        self.sim_inputs.setRange(1, 100)
        self.sim_inputs.setValue(1)
        simulator.layout().addWidget(self.sim_inputs)
        simulator.layout().addWidget(label("Simulated outputs (recipient + optional change)", 13, True))
        self.sim_outputs = QSpinBox()
        self.sim_outputs.setRange(1, 2)
        self.sim_outputs.setValue(2)
        simulator.layout().addWidget(self.sim_outputs)
        simulate = QPushButton("Calculate illustrative fee")
        simulate.clicked.connect(self.simulate_fee)
        simulator.layout().addWidget(simulate)
        self.sim_result = label("Choose the number of inputs and outputs.", 13)
        simulator.layout().addWidget(self.sim_result)
        layout.addWidget(simulator)
        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def simulate_fee(self):
        # Legacy P2PKH approximation only: 148 bytes/input, 34/output,
        # 10 bytes overhead. Not a serialized transaction or spendable quote.
        inputs = self.sim_inputs.value()
        outputs = self.sim_outputs.value()
        size = 10 + 148 * inputs + 34 * outputs
        rate = Decimal("0.00100000")  # FLOOF/kB observed on Core 4.0.4
        atomic = (Decimal(size) * rate * Decimal(100000000) / Decimal(1000)).to_integral_value(
            rounding=ROUND_CEILING)
        fee = atomic / Decimal(100000000)
        self.sim_result.setText(
            f"Illustrative size: {size} bytes | Fee: {fee:.8f} FLOOF\\n"
            "Simulation only — does not update the Send fee or authorize spending.")

    def preview_send(self):
        address = self.send_destination.text().strip()
        amount_text = self.send_amount.text().strip()
        if not validate_address(address):
            self.send_feedback.setText("Invalid FloofyChain destination address.")
            return
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            self.send_feedback.setText("Amount must be a valid decimal number.")
            return
        unit = Decimal("0.00000001")
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(unit):
            self.send_feedback.setText("Amount must be positive with at most 8 decimal places.")
            return
        self.send_feedback.setText(
            "Fee calculation pending verified UTXOs, transaction size and network fee rate. "
            "This preview cannot be sent.")
        box = self.send_preview.layout()
        while box.count():
            item = box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        box.addWidget(label("Transaction preview — NOT BROADCAST", 16, True))
        box.addWidget(label("From: " + (self.wallet_address or "Locked"), 12))
        box.addWidget(label("To: " + address, 12))
        box.addWidget(label(f"Amount: {amount:.8f} FLOOF", 13))
        box.addWidget(label("Estimated network fee: unavailable", 13))
        box.addWidget(label("Total including fee: pending estimation", 15, True))
        disabled = QPushButton("Confirm send — unavailable in preview")
        disabled.setEnabled(False)
        box.addWidget(disabled)

    def make_history(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(36, 36, 36, 36)
        outer.setSpacing(14)
        outer.addWidget(label("Transaction history", 26, True))
        outer.addWidget(label("Confirmed transactions for your unlocked wallet address. Explorer data may be delayed.", 13, muted=True))
        modes = QHBoxLayout()
        self.wallet_history_button = QPushButton("My wallet")
        self.public_history_button = QPushButton("Explore address")
        self.wallet_history_button.clicked.connect(lambda: self.switch_history_mode("wallet"))
        self.public_history_button.clicked.connect(lambda: self.switch_history_mode("public"))
        modes.addWidget(self.wallet_history_button)
        modes.addWidget(self.public_history_button)
        outer.addLayout(modes)
        self.history_address = label("No wallet unlocked", 13, True)
        outer.addWidget(self.history_address)
        self.public_address_input = QLineEdit()
        self.public_address_input.setPlaceholderText("Paste a public FloofyChain address")
        self.public_address_input.returnPressed.connect(self.refresh_wallet_history)
        outer.addWidget(self.public_address_input)
        self.public_address_input.hide()
        refresh = QPushButton("Refresh history")
        refresh.setObjectName("primary")
        refresh.clicked.connect(self.refresh_wallet_history)
        outer.addWidget(refresh)
        self.history_note = label("No history loaded yet.", 12, muted=True)
        outer.addWidget(self.history_note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.history_rows = QWidget()
        self.history_layout = QVBoxLayout(self.history_rows)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(9)
        self.history_layout.addStretch()
        scroll.setWidget(self.history_rows)
        outer.addWidget(scroll, 1)
        return w

    def clear_history(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.history_layout.addStretch()

    def switch_history_mode(self, mode):
        self.history_mode = mode
        self.public_address_input.setVisible(mode == "public")
        self.history_address.setVisible(mode == "wallet")
        for button, active in ((self.wallet_history_button, mode == "wallet"),
                               (self.public_history_button, mode == "public")):
            button.setObjectName("selected" if active else "")
            button.style().unpolish(button)
            button.style().polish(button)
        self.clear_history()
        self.history_note.setText("Enter an address and refresh." if mode == "public"
                                  else "Click Refresh history to load your transactions.")

    def refresh_wallet_history(self):
        address = self.wallet_address if self.history_mode == "wallet" else self.public_address_input.text().strip()
        if not address or not validate_address(address):
            self.history_note.setText("Enter a valid FloofyChain address.")
            return
        self.history_note.setText("Loading confirmed transactions…")
        self.load_address(address, self.history_mode)

    def populate_history(self, transactions, txcount):
        self.clear_history()
        self.history_note.setText(
            f"Showing {len(transactions)} confirmed transaction(s) from the first explorer page "
            f"of {txcount} reported. Not a complete history if more exist."
        )
        if not transactions:
            self.history_note.setText("No confirmed transactions on the first explorer page.")
            return
        for tx in sorted(transactions, key=lambda t: (t.block_height, t.timestamp, t.txid), reverse=True):
            card = panel()
            when = datetime.fromtimestamp(tx.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            direction = "Received" if tx.amount > 0 else ("Sent" if tx.amount < 0 else "Neutral / internal")
            card.layout().addWidget(label(f"{direction}    {tx.amount:+.8f} FLOOF", 15, True))
            card.layout().addWidget(label(f"{when}    •    Block {tx.block_height}", 12, muted=True))
            tx_label = label("TXID: " + tx.txid, 11)
            tx_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            card.layout().addWidget(tx_label)
            copy_button = QPushButton("Copy TXID")
            copy_button.clicked.connect(lambda checked=False, txid=tx.txid: QApplication.clipboard().setText(txid))
            card.layout().addWidget(copy_button)
            self.history_layout.insertWidget(self.history_layout.count() - 1, card)

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
            ("Create another test wallet", self.create_wallet),
            ("Import another test WIF", self.import_wallet),
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
        # Generate and encrypt once; retry only the destination filename.
        vault = encrypt_wif(wif, password)
        suggested = ""
        while True:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save encrypted test wallet", suggested, "Floofy vault (*.floofvault)")
            if not filename:
                return False
            path = Path(filename)
            if path.suffix.lower() != ".floofvault":
                path = path.with_suffix(".floofvault")
            suggested = str(path)
            if path.exists():
                QMessageBox.warning(
                    self, "File exists",
                    "This vault already exists. Please choose another filename. "
                    "Existing vaults are never overwritten.")
                continue
            try:
                save_vault(path, vault)
            except FileExistsError:
                QMessageBox.warning(
                    self, "File exists",
                    "Another file now uses this name. Choose another filename.")
                continue
            return path

    def activate_wallet(self, path, address):
        self.wallet_address = address
        self.history_address.setText("Wallet: " + address)
        self.dashboard_address.setText(address)
        self.switch_history_mode("wallet")
        self.clear_history()
        self.history_note.setText("Loading confirmed transactions…")
        self.wallet_status.setText("Unlocked test wallet: " + address)
        self.update_receive()
        self.show_page("Dashboard")
        self.load_address(address, "wallet")

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
        self.history_address.setText("No wallet unlocked")
        self.clear_history()
        self.history_note.setText("Wallet locked; history cleared.")
        self.wallet_status.setText("Wallet locked")
        self.update_receive()
        self.dashboard_address.clear()
        self.public_address_input.clear()
        self.switch_history_mode("wallet")
        self.balance_label.setText("— FLOOF")
        self.received_label.setText("—")
        self.txcount_label.setText("—")
        self.activity.setText("No address loaded yet.")
        self.utxo_count.setText("UTXOs: —")
        self.status.setText("Wallet locked.")
        self.send_destination.clear()
        self.send_amount.clear()
        self.send_fee.setText("Unavailable — UTXOs and fee rate not verified")
        self.send_feedback.setText("Wallet locked. Transaction preview only.")
        self.send_utxo_status.setText("UTXO data: not loaded or verified")
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

    def load_address(self, address, mode="wallet"):
        address = address.strip()
        if not validate_address(address):
            QMessageBox.warning(self, "Invalid address", "Enter a valid FloofyChain mainnet address.")
            return
        if self.thread is not None:
            return
        self.status.setText("Loading explorer data…")
        self.requested_address = address
        self.requested_mode = mode
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


    def loaded(self, summary, history, utxos):
        requested = self.requested_address
        mode = self.requested_mode
        if mode == "public":
            if self.history_mode == "public" and requested == self.public_address_input.text().strip():
                self.populate_history(history, summary.txcount)
            return
        if requested != self.wallet_address or self.wallet_address is None:
            return
        if self.history_mode == "wallet":
            self.populate_history(history, summary.txcount)
        self.balance_label.setText(f"{summary.balance:.8f} FLOOF")
        self.received_label.setText(f"{summary.received:.8f}")
        self.txcount_label.setText(str(summary.txcount))
        self.utxo_count.setText(f"Unspent outputs: {len(utxos)} (spendability not verified)")
        self.send_utxo_status.setText(f"Explorer reports {len(utxos)} UTXO(s) on its first page — not verified for spending")
        if not history:
            self.activity.setText("No confirmed transactions in the first page.")
        else:
            lines = []
            for tx in history[:5]:
                when = datetime.fromtimestamp(tx.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                lines.append(f"{when}    {tx.txid[:12]}…    {tx.amount:.8f} FLOOF")
            self.activity.setText("\n\n".join(lines))
        self.status.setText(f"Explorer: {summary.source} • Read-only • Data may be stale")

    def load_failed(self, error):
        if self.requested_mode == "public":
            if self.history_mode == "public":
                self.history_note.setText("Could not load explorer history: " + error)
        elif self.requested_address == self.wallet_address:
            self.status.setText("Could not load wallet data: " + error)
            self.send_utxo_status.setText("UTXO data unavailable — fee cannot be estimated")
            if self.history_mode == "wallet":
                self.history_note.setText("Could not load explorer history: " + error)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = WalletWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
