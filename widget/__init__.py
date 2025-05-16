from clients.github import GithubPRClient
from .rumps_dock import PollingMenuBarApp

def main():
    pr_client = GithubPRClient()
    # prs = pr_client.load_prs()

    mba = PollingMenuBarApp(pr_client)
    mba.run()
