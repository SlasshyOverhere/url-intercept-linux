"""Qt system-tray application."""

import subprocess

from PyQt6.QtCore import QObject, QPointF, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QCursor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

from . import browser, config, logger, processes, schemes, service as service_mod


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)

    p.setBrush(QColor("#0a0a0a"))
    p.drawPolygon(QPolygonF([QPointF(14, 17), QPointF(50, 17), QPointF(37, 34), QPointF(27, 34)]))
    p.drawRoundedRect(28, 33, 8, 4, 2, 2)

    p.drawRoundedRect(25, 41, 14, 7, 3, 3)
    p.end()
    return QIcon(pm)


class _UrlBridge(QObject):
    url = pyqtSignal(str, dict)


class _Worker(QThread):
    result = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        self.result.emit(self.fn())


class TrayApp:
    def __init__(self, qapp, cfg):
        self.qapp = qapp
        self.cfg = cfg
        self._workers = []

        self.tray = QSystemTrayIcon(make_icon())
        self.tray.setToolTip("Linux URL Interceptor")
        menu = QMenu()
        menu.aboutToShow.connect(self._rebuild_menu)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        self.svc = service_mod.Service(cfg)
        self.bridge = _UrlBridge()
        self.bridge.url.connect(self.svc.handle)
        self.svc.dispatch = lambda u, s: self.bridge.url.emit(u, s)
        self.svc.start()

    # ---- tray events -------------------------------------------------

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.tray.contextMenu().popup(QCursor.pos())

    # ---- menu ---------------------------------------------------------

    def _rebuild_menu(self):
        self.cfg = config.load()
        menu = self.tray.contextMenu()
        menu.clear()

        def add_check(label, key, on_toggle):
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(self.cfg.get(key, False))
            act.triggered.connect(lambda ch, k=key: self._set_flag(k, ch))
            return act

        add_check("Interception enabled", "enabled", None)
        add_check("Copy URL to clipboard", "copy_to_clipboard", None)
        add_check("Open intercepted links in browser", "open_in_browser", None)
        add_check("Resolve redirect chain", "resolve_redirect_chain", None)
        menu.addSeparator()

        fwd = menu.addMenu("Forward browser")
        group = QActionGroup(self.qapp)
        group.setExclusive(True)
        chosen = self.cfg.get("forward_browser", "auto")

        auto = fwd.addAction("Auto (original handler)")
        auto.setCheckable(True)
        auto.setChecked(chosen in (None, "", "auto"))
        group.addAction(auto)
        auto.triggered.connect(lambda ch, v="auto": self._set_forward(v))

        for b in browser.list_browsers():
            act = fwd.addAction(b["name"])
            act.setCheckable(True)
            act.setChecked(chosen == b["id"])
            group.addAction(act)
            act.triggered.connect(lambda ch, v=b["id"]: self._set_forward(v))
        menu.addSeparator()

        menu.addAction("Excluded apps...", self._excluded_dialog)
        menu.addSeparator()

        if schemes.is_installed():
            menu.addAction(
                "Restore original http/https handler",
                lambda: self._run_scheme(schemes.uninstall, "Original handler restored."),
            )
        else:
            menu.addAction(
                "Install as default http/https handler",
                lambda: self._run_scheme(schemes.install, "Installed. URLs launched by apps now pass through the interceptor."),
            )

        start = menu.addAction("Launch at login")
        start.setCheckable(True)
        start.setChecked(schemes.autostart_path().exists())
        start.triggered.connect(self._toggle_autostart)
        menu.addSeparator()

        menu.addAction("Interception status...", self._status_dialog)
        menu.addAction("Open logs folder", lambda: self._open_folder(config.logs_dir()))
        menu.addAction("Open config folder", lambda: self._open_folder(config.config_dir()))
        menu.addSeparator()
        menu.addAction("Exit", self._exit)

    def _set_flag(self, key, value):
        self.cfg[key] = value
        config.save(self.cfg)
        logger.runtime_log(f"set {key}={value}")

    def _set_forward(self, value):
        self.cfg["forward_browser"] = value
        config.save(self.cfg)
        logger.runtime_log(f"forward browser -> {value}")

    def _toggle_autostart(self, checked):
        self.cfg["launch_at_startup"] = checked
        config.save(self.cfg)
        schemes.set_autostart(checked)

    # ---- dialogs ------------------------------------------------------

    def _excluded_dialog(self):
        self.cfg = config.load()
        dlg = QDialog()
        dlg.setWindowTitle("Excluded apps")
        dlg.resize(620, 440)
        lay = QVBoxLayout(dlg)

        hint = QLabel(
            "Excluded apps are trusted: their links open in the browser AND are copied to the "
            "clipboard. Links from every other app are only copied. Pick running apps on the left "
            "or type a process name below."
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)

        row = QHBoxLayout()

        run_label = QLabel("Running apps")
        run_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        running = QListWidget()
        running.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        running.addItems(processes.list_running_processes())
        run_col = QVBoxLayout()
        run_col.addWidget(run_label)
        run_col.addWidget(running, 1)
        add_btn = QPushButton("Add selected ->")
        run_col.addWidget(add_btn)

        exc_label = QLabel("Excluded apps")
        exc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        excluded_list = QListWidget()
        excluded_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        excluded_list.addItems(sorted(self.cfg.get("excluded_apps", [])))
        exc_col = QVBoxLayout()
        exc_col.addWidget(exc_label)
        exc_col.addWidget(excluded_list, 1)
        remove_btn = QPushButton("Remove selected")
        exc_col.addWidget(remove_btn)

        row.addLayout(run_col, 1)
        row.addLayout(exc_col, 1)
        lay.addLayout(row)

        def _existing(name):
            return excluded_list.findItems(name, Qt.MatchFlag.MatchExactly)

        def add_selected():
            for item in running.selectedItems():
                name = item.text().strip().lower()
                if name and not _existing(name):
                    excluded_list.addItem(name)

        def remove_selected():
            for item in excluded_list.selectedItems():
                excluded_list.takeItem(excluded_list.row(item))

        add_btn.clicked.connect(add_selected)
        remove_btn.clicked.connect(remove_selected)

        manual_row = QHBoxLayout()
        manual = QLineEdit()
        manual.setPlaceholderText("Type a process name to trust (e.g. telegram-desktop)")
        manual_add = QPushButton("Add")
        manual_row.addWidget(manual, 1)
        manual_row.addWidget(manual_add)
        lay.addLayout(manual_row)

        def add_manual():
            name = manual.text().strip().lower()
            if name and not _existing(name):
                excluded_list.addItem(name)
            manual.clear()

        manual_add.clicked.connect(add_manual)
        manual.returnPressed.connect(add_manual)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        lay.addWidget(btns)

        def on_ok():
            names = sorted(
                {
                    excluded_list.item(i).text().strip().lower()
                    for i in range(excluded_list.count())
                    if excluded_list.item(i).text().strip()
                }
            )
            self.cfg["excluded_apps"] = names
            config.save(self.cfg)
            logger.runtime_log(f"excluded apps -> {names}")
            dlg.accept()

        btns.accepted.connect(on_ok)
        btns.rejected.connect(dlg.reject)
        dlg.exec()

    def _status_dialog(self):
        http = schemes.query("http")
        https = schemes.query("https")
        installed = schemes.is_installed()
        msg = (
            f"Current http handler:  {http or 'none'}\n"
            f"Current https handler: {https or 'none'}\n\n"
            f"Interceptor is {'installed' if installed else 'NOT installed'} as the default handler."
        )
        QMessageBox.information(None, "Interception status", msg)

    def _open_folder(self, path):
        try:
            import os

            os.makedirs(path, exist_ok=True)
        except OSError:
            pass
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ---- actions ------------------------------------------------------

    def _run_scheme(self, fn, ok_msg, err_msg="Operation failed."):
        self.qapp.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def job():
            return fn(config.load())

        def done(res):
            self.qapp.restoreOverrideCursor()
            self.cfg = config.load()
            if res:
                QMessageBox.information(None, "Linux URL Interceptor", ok_msg)
            else:
                QMessageBox.warning(None, "Linux URL Interceptor", err_msg)
            self._rebuild_menu()

        w = _Worker(job)
        w.result.connect(done)
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        w.start()

    def _exit(self):
        self.shutdown()
        self.qapp.quit()

    def shutdown(self):
        self.svc.stop()
        self.tray.hide()
