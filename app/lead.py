"""Router perintah tetap; pemahaman bahasa dengan AI belum dihubungkan."""

from app.desktop import DesktopAgent, Result


class LeadAgent:
    def __init__(self, desktop: DesktopAgent):
        self.desktop = desktop

    def dispatch(self, command: str, *, name: str = "", path: str = "") -> Result:
        command = command.strip().lower()
        if command == "folder":
            return self.desktop.create_folder(name)
        if command == "buka":
            return self.desktop.open_file(path)
        if command == "pesanan":
            return self.desktop.prepare_order(name, path)
        return Result("membutuhkan_bantuan", ["Perintah belum dikenal. Ketik bantuan untuk melihat pilihan."])
