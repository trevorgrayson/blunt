import os
from . import GithubPRClient

GITHUB_USERNAME = os.getenv("GITHUB_USER", "trevorgrayson-earnin")
GITHUB_TOKEN = os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN"))


if __name__ == "__main__":
    prs = GithubPRClient(GITHUB_TOKEN, GITHUB_USERNAME).load_prs()
    for pr in prs:
        print(pr["full_text"])
        for item in pr.get("action_items", []):
            print(f"  - {item}")
