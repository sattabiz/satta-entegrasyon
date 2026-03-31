import os
import sys
import tempfile
import subprocess
import requests
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt, QThread, Signal, QEventLoop
from versiyon import APP_VERSION

GITHUB_API_URL = "https://api.github.com/repos/sattabiz/satta-entegrasyon/releases/latest"
INSTALLER_NAME = "SattaEntegrasyon-Setup.exe"

class DownloadThread(QThread):
    progress = Signal(int, int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url
        self.temp_path = os.path.join(tempfile.gettempdir(), INSTALLER_NAME)

    def run(self):
        try:
            with requests.get(self.download_url, stream=True, timeout=10) as r:
                r.raise_for_status()
                total_length_str = r.headers.get('content-length')
                if total_length_str is None:
                    with open(self.temp_path, 'wb') as f:
                        f.write(r.content)
                    self.progress.emit(100, 100)
                else:
                    total_length = int(total_length_str)
                    downloaded: int = 0
                    with open(self.temp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                self.progress.emit(downloaded, total_length)
            self.finished.emit(self.temp_path)
        except Exception as e:
            self.error.emit(str(e))

def check_and_update(parent_widget=None) -> bool:
    """
    Checks for an update, prompts the user, and handles download/install.
    Returns True if an update is initiated (the app should exit), False otherwise.
    """
    try:
        response = requests.get(GITHUB_API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        latest_tag = data.get("tag_name", "").lstrip("v")
        if not latest_tag:
            return False

        def parse_version(v: str) -> tuple:
            return tuple(map(int, v.split(".")))
            
        try:
            current_v = parse_version(APP_VERSION)
            latest_v = parse_version(latest_tag)
        except ValueError:
            current_v = APP_VERSION
            latest_v = latest_tag

        if latest_v > current_v:
            download_url: Optional[str] = None
            for asset in data.get("assets", []):
                if asset.get("name") == INSTALLER_NAME:
                    val = asset.get("browser_download_url")
                    if isinstance(val, str):
                        download_url = val
                    break
            
            if not download_url:
                return False

            reply = QMessageBox.question(
                parent_widget,
                "Yeni Sürüm Mevcut!",
                f"Satta Entegrasyon'un yeni bir sürümü ({latest_tag}) bulundu.\nŞu anki sürüm: {APP_VERSION}\n\nİndirip kurmak ister misiniz?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                progress_dialog = QProgressDialog("Güncelleme indiriliyor...", "İptal", 0, 100, parent_widget)
                progress_dialog.setWindowTitle("İndiriliyor")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setAutoClose(True)
                progress_dialog.setAutoReset(True)
                progress_dialog.resize(400, 100)
                progress_dialog.show()

                download_thread = DownloadThread(download_url)
                result: Dict[str, Any] = {"success": False, "path": ""}

                def update_progress(downloaded: int, total: int):
                    if total > 0:
                        progress_dialog.setMaximum(total)
                        progress_dialog.setValue(downloaded)

                def on_finished(path: str):
                    result["success"] = True
                    result["path"] = path
                    progress_dialog.accept()

                def on_error(err: str):
                    QMessageBox.warning(parent_widget, "Hata", f"İndirme sırasında bir hata oluştu:\n{err}")
                    progress_dialog.reject()
                
                download_thread.progress.connect(update_progress)
                download_thread.finished.connect(on_finished)
                download_thread.error.connect(on_error)
                progress_dialog.canceled.connect(download_thread.terminate)
                
                download_thread.start()
                
                loop = QEventLoop()
                progress_dialog.finished.connect(loop.quit)
                loop.exec()

                if result["success"] and os.path.exists(str(result["path"])):
                    exe_path = str(result["path"])
                    subprocess.Popen([exe_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/FORCECLOSEAPPLICATIONS"])
                    return True

    except Exception as e:
        print(f"Güncelleme kontrolü başarısız oldu: {e}")
    
    return False
