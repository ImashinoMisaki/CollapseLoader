from collapse.modules.network.API import api
from collapse.modules.network.Servers import servers
from collapse.modules.utils.Language import lang
from collapse.modules.utils.Module import Module


class HeaderText(Module):
    def __init__(self):
        super().__init__()

        self.text = None
        self.get()

    def get(self):
        if servers.web_server != "":
            response = api.get(f"header/?lang={lang.current}", prefix=False)
            if response is not None:
                self.text = response.text
        else:
            self.text = "[i]header not available[/]"


header = HeaderText()
