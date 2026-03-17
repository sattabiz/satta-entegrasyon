from pathlib import Path
import sys


def get_base_dir():
    """
    Uygulamanın ana çalışma klasörünü döndürür.
    PyInstaller ile paketlenmiş exe içinde çalışıyorsa _MEIPASS kullanır.
    Normal Python çalışmasında proje kökünü baz alır.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def project_path(*parts):
    """
    Proje içindeki dosya yolunu güvenli şekilde oluşturur.
    Örnek:
        project_path("Settings", "app_settings.json")
    """
    return get_base_dir().joinpath(*parts)


def ensure_directory(path_obj: Path):
    """
    Klasör yoksa oluşturur.
    """
    path_obj.mkdir(parents=True, exist_ok=True)