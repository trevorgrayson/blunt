import os
from . import GithubPRClient
GITHUB_USERNAME = "trevorgrayson-earnin"
GITHUB_TOKEN = os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN"))
API_URL = "https://api.github.com"


if __name__ == "__main__":
    prs = GithubPRClient(GITHUB_USERNAME, GITHUB_TOKEN).load_prs()
    for pr in prs:
        print(pr["full_text"])
