from os import environ
import requests

# Replace with your GitHub username and token
GITHUB_USERNAME = "trevorgrayson-earnin"
GITHUB_TOKEN = environ["GH_TOKEN"]

# GitHub API endpoint
API_URL = "https://api.github.com"

def get_open_prs(username):
    url = f"{API_URL}/search/issues?q=author:{username}+type:pr+state:open"
    response = requests.get(url, auth=(username, GITHUB_TOKEN))
    response.raise_for_status()
    return response.json()["items"]

def get_pr_details(pr_url):
    response = requests.get(pr_url, auth=(GITHUB_USERNAME, GITHUB_TOKEN))
    response.raise_for_status()
    pr_data = response.json()
    return {
        "title": pr_data["title"],
        "url": pr_data["html_url"],
        "state": pr_data["state"],
        "comments": pr_data["comments"] + pr_data["review_comments"],
        "status": pr_data["mergeable_state"]
    }

def main():
    print(f"Fetching open PRs for {GITHUB_USERNAME}...\n")
    prs = get_open_prs(GITHUB_USERNAME)
    if not prs:
        print("No open PRs found.")
        return

    for pr in prs:
        pr_details = get_pr_details(pr["pull_request"]["url"])
        print(f"Title     : {pr_details['title']}")
        print(f"URL       : {pr_details['url']}")
        print(f"State     : {pr_details['state']}")
        print(f"Status    : {pr_details['status']}")
        print(f"Comments  : {pr_details['comments']}\n")

if __name__ == "__main__":
    main()

