import os

from collapse.modules.network.Servers import servers

from ....developer import SHOW_HIDDEN_CLIENTS
from ...network.API import api
from ...storage.Cache import cache
from ...storage.Data import data
from ...storage.Settings import settings
from ...utils.Language import lang
from ..Module import Module
from .Client import Client
from .CustomClientManager import custom_client_manager


class ClientManager(Module):
    """Class to manage and load clients from the API"""

    def __init__(self) -> None:
        super().__init__()
        self.clients: list[Client] = []
        self.json_clients: dict = {}
        self._load_clients()

    def _load_clients(self) -> list:
        """Load clients from the API and return a list of client instances"""

        if servers.web_server != "":
            clients = api.get("clients")
            fabric_clients = api.get("fabric_clients")

        if servers.web_server == "":
            if not os.path.exists(cache.path):
                self.error(lang.t("cache.cache-not-found"))

            else:
                c = cache.get()
                creation_time = c["_meta"]["creation_time"]
                self.info(lang.t("cache.using-last-cache").format(creation_time))

                self.make_array(c["clients"])

            self.load_custom_clients()
            return

        all_clients: dict = clients.json() + fabric_clients.json()

        clients = []

        if clients is not None:
            cache.save(all_clients)
            self.make_array(all_clients)

        self.json_clients = all_clients

        self.load_custom_clients()

        return all_clients

    def make_array(self, clients: dict) -> None:
        """Adds clients to array"""
        for client in clients:
            if not client["fabric"]:
                if client["show_in_loader"] or SHOW_HIDDEN_CLIENTS:
                    self.clients.append(
                        Client(
                            name=client["name"],
                            link=data.get_url(client["filename"]),
                            main_class=client["main_class"],
                            version=client["version"],
                            internal=client["internal"],
                            working=client["working"],
                            id=client["id"],
                            fabric=client["fabric"],
                        )
                    )
            else:
                if client["show_in_loader"] or SHOW_HIDDEN_CLIENTS:
                    self.clients.append(
                        Client(
                            name=client["name"],
                            link=data.get_url(client["filename"]),
                            main_class="",
                            version=client["version"],
                            working=client["working"],
                            id=client["id"],
                            fabric=client["fabric"],
                        )
                    )

            if not settings.use_option("sort_clients"):
                self.clients.sort(key=lambda client: client.name.lower())

    def load_custom_clients(self) -> None:
        """Load custom clients into the main client list"""
        if hasattr(custom_client_manager, "clients") and custom_client_manager.clients:
            for custom_client in custom_client_manager.clients:
                custom_client.is_custom = True
                self.clients.append(custom_client)

            if not settings.use_option("sort_clients"):
                self.clients.sort(key=lambda client: client.name.lower())

    def refresh(self) -> None:
        """Refresh clients"""
        self.clients: list[Client] = []
        self._load_clients()

    def get_client_by_name(self, name: str) -> Client:
        """Get client by name"""
        for client in self.clients:
            if name.lower() in client.name.lower():
                return client


client_manager = ClientManager()
