import os
import shutil
import zipfile

import requests
from rich.progress import (BarColumn, DownloadColumn, Progress, TextColumn,
                           TransferSpeedColumn)

from ...config import CODENAME, ROOT_DIR, VERSION
from ..network.Network import network
from ..network.Servers import servers
from ..storage.Cache import cache
from ..storage.Settings import settings
from ..utils.Fixes import console
from ..utils.Language import lang
from ..utils.Module import Module


class DataManager(Module):
    """Used to manage loader data"""

    def __init__(self) -> None:
        super().__init__()
        self.root_dir = ROOT_DIR

        servers.check_servers()

        self.server = servers.cdn_server
        self.web_server = servers.web_server

        if not self.server:
            self.critical(lang.t("data.no-server"))

        self.version = VERSION
        self.codename = CODENAME
        self.boolean_states = {True: f" [green]\\[+][/]", False: ""}
        self.ignored_files = [settings.config_path, cache.path]

        os.makedirs(self.root_dir, exist_ok=True)

    def get_local(self, path: str) -> str:
        """Get file locally"""
        return os.path.join(self.root_dir, path)

    def get_url(self, path: str) -> str:
        """Gets a link from the web"""
        return self.server + path

    def clear(self) -> str:
        """Clears the data folder"""
        for file in os.listdir(self.root_dir):
            file_path = os.path.join(self.root_dir, file)
            if file_path not in self.ignored_files:
                try:
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    else:
                        os.remove(file_path)
                except PermissionError:
                    self.error(f"Permission denied: {file_path}")

    def download(self, path: str, destination: str = None, raw: bool = False) -> None:
        """Downloads file using path"""
        filename = os.path.basename(path)
        path_dir = os.path.join(self.root_dir, os.path.splitext(filename)[0])
        dest = destination if destination else os.path.join(self.root_dir, filename)

        if self._is_downloaded(filename, path, path_dir):
            return

        self.debug(lang.t("data.download.to").format(filename, dest))

        self._download_file(path, filename, dest, raw)
        self._extract_file(filename, dest, path_dir, raw)

    def is_downloaded(self, filename: str) -> bool:
        if os.path.exists(data.get_local(os.path.splitext(filename)[0])):
            return True

        return False

    def _is_downloaded(self, filename: str, path: str, path_dir: str) -> bool:
        """Checks if the file is already downloaded."""
        jar = os.path.splitext(filename)[0] + ".jar"

        if (
            not filename.endswith(".jar")
            and os.path.isdir(path_dir)
            and not path.startswith("http")
        ):
            self.debug(lang.t("data.download.already-downloaded").format(filename))
            return True

        if filename.endswith(".jar") and os.path.exists(os.path.join(path_dir, jar)):
            self.debug(lang.t("data.download.already-downloaded").format(filename))
            return True

        return False

    def _download_file(
        self, path: str, filename: str, dest: str, raw: bool = False
    ) -> None:
        """Downloads the file from the given path and shows download progress"""
        if not raw:
            os.makedirs(self.root_dir + os.path.splitext(filename)[0], exist_ok=True)

        headers = (
            {"Range": f"bytes={os.path.getsize(dest)}-"} if os.path.exists(dest) else {}
        )

        try:
            response = network.get(
                self.get_url(filename) if not path.startswith("http") else path,
                headers=headers,
                stream=True,
            )
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
        except requests.exceptions.RequestException as e:
            self.error(lang.t("data.download.error").format(filename, e))
            return

        with Progress(
            TextColumn(f"[blue]{filename}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("", total=total_size)

            with open(dest, "ab") as f:
                for chunk in response.iter_content(1024):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

            progress.stop()

    def _extract_file(self, filename: str, dest: str, path_dir: str, raw: bool) -> None:
        """Extracts the downloaded file based on its type"""
        try:
            if filename.endswith(".zip"):
                with zipfile.ZipFile(dest, "r") as zip_file:
                    zip_file.extractall(path_dir)
                os.remove(dest)
            elif filename.endswith(".jar"):
                if not raw:
                    os.rename(dest, os.path.join(path_dir, filename))
        except (zipfile.BadZipFile, OSError) as e:
            self.error(lang.t("data.download.extract-error").format(filename, e))
            if os.path.exists(dest):
                os.remove(dest)


data = DataManager()
