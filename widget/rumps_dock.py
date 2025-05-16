import rumps
import requests
import webbrowser
import threading
from clients.github import GithubPRClient, review_status_icon

DEFAULT_POLL_INTERVAL = 300  # seconds

def polling_client(*clients):
    try:
        prs = clients[0].load_prs()
        return [
            {"title": pr["full_text"][:80], "href": pr["url"]}
            for pr in prs[:10]
        ], True
    except Exception as e:
        return [{"title": f"Error: {e}", "href": ""}], False




class PollingMenuBarApp(rumps.App):
    def __init__(self, *clients):
        super().__init__("⏳", icon=None)  # use title to show emoji
        self.clients = clients
        self.poll_interval = DEFAULT_POLL_INTERVAL
        self.timer = rumps.Timer(self.run_poll, self.poll_interval)
        self.timer.start()

        self.run_poll()

        # Add submenu container (no callback!)
        freq_submenu = rumps.MenuItem("Set polling frequency")

        # Add actual items to the submenu
        freq_submenu.add(rumps.MenuItem("1 min", callback=lambda _: self.set_polling_frequency(60)))
        freq_submenu.add(rumps.MenuItem("5 min", callback=lambda _: self.set_polling_frequency(300)))
        freq_submenu.add(rumps.MenuItem("15 min", callback=lambda _: self.set_polling_frequency(900)))

        # Attach submenu to the main item
        self.freq_menu = freq_submenu

    def set_polling_frequency(self, seconds):
        self.poll_interval = seconds
        self.timer.stop()
        self.timer = rumps.Timer(self.run_poll, self.poll_interval)
        self.timer.start()
        self.run_poll()

    def run_poll(self, _=None):
        def fetch_and_rebuild_menu():
            self.title = "🤔"  # Polling...

            items, success = polling_client(*self.clients)
            # for item in self.menu.items():
            #     if item is rumps.separator:
            #         break
            #     self.menu.items.remove(item)
            self.menu.clear()

            for item in items:
                title = item["title"]
                if item["href"]:
                    self.menu.add(rumps.MenuItem(
                        title, callback=lambda _, url=item["href"]: webbrowser.open(url)))
                else:
                    self.menu.add(title)

            self.menu.add(rumps.separator)

            # Add to app menu
            # self.menu.add(self.freq_menu)

            self.title = review_status_icon(self.clients[0].reviews) if success else "🔴"

        threading.Thread(target=fetch_and_rebuild_menu).start()
#
# if __name__ == "__main__":
#     PollingMenuBarApp().run()

