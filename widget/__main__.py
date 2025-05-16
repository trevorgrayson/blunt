import os
from clients.github import GithubPRClient
from .rumps_dock import PollingMenuBarApp
GITHUB_USERNAME = "trevorgrayson-earnin"
GITHUB_TOKEN = os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN"))
API_URL = "https://api.github.com"


if __name__ == "__main__":
    pr_client = GithubPRClient(GITHUB_USERNAME, GITHUB_TOKEN)
    # prs = pr_client.load_prs()

    mba = PollingMenuBarApp(pr_client)
    mba.run()
