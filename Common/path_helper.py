from pathlib import Path
import os
import sys


APP_VENDOR = "Satta"
APP_NAME = "EntegrasyonLive"


def get_base_dir() -> Path:
    """
    Uygulamanın statik dosyalarının bulunduğu ana klasörü döndürür.
    - PyInstaller ile paketlenmiş exe içinde çalışıyorsa _MEIPASS kullanır
    - Normal Python çalışmasında proje kökünü baz alır
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def project_path(*parts) -> Path:
    """
    Proje içindeki statik dosyalar için yol üretir.
    Örnek:
        project_path("App_Icons", "2.png")
    """
    return get_base_dir().joinpath(*parts)


def get_user_data_dir() -> Path:
    """
    Kullanıcıya özel yazılabilir veri klasörünü döndürür.
    Windows:
        %LOCALAPPDATA%\\Satta\\EntegrasyonLive
    macOS:
        ~/Library/Application Support/Satta/EntegrasyonLive
    Linux:
        ~/.local/share/Satta/EntegrasyonLive
    """
    if sys.platform.startswith("win"):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_VENDOR / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_VENDOR / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_VENDOR / APP_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_VENDOR / APP_NAME

    return Path.home() / ".local" / "share" / APP_VENDOR / APP_NAME


def user_data_path(*parts) -> Path:
    """
    Kullanıcıya özel ayar / session / runtime dosyaları için yol üretir.
    Örnek:
        user_data_path("app_settings.json")
        user_data_path("satta_session.json")
    """
    return get_user_data_dir().joinpath(*parts)


def ensure_directory(path_obj: Path):
    """
    Klasör yoksa oluşturur.
    """
    path_obj.mkdir(parents=True, exist_ok=True)


def ensure_parent_directory(file_path: Path):
    """
    Verilen dosyanın üst klasörü yoksa oluşturur.
    """
    ensure_directory(file_path.parent)