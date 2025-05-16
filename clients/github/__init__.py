from os import environ
import requests

GITHUB_USERNAME = environ.get("GITHUB_USER", "trevorgrayson-earnin")
GITHUB_TOKEN = environ.get("GITHUB_TOKEN")
API_URL = environ.get("GITHUB_URL", "https://api.github.com")

"🌊"

def review_status_icon(reviews):
    states = [r["state"] for r in reviews]
    if "CHANGES_REQUESTED" in states:
        return "❌"
    elif "COMMENTED" in states:
        return "💬"
    elif "APPROVED" in states:
        return "✅"
    return "⚪"


def status_icon(status):
    if status == "approved":
        return "✅"
    elif status == "clean":
        return "⚪"
    elif status in ("dirty", "behind"):
        return "🔴"
    return "⚪" # 🟡


def status_color(status):
    if status == "approved":
        return "green"
    elif status == "clean":
        return "goldenrod"
    elif status in ("dirty", "behind"):
        return "red"
    return "gray"


def get_review_status(reviews):
    states = [r["state"] for r in reviews]
    if "CHANGES_REQUESTED" in states:
        return "❌ changes requested"
    elif "COMMENTED" in states:
        return "💬 commented"
    elif "APPROVED" in states:
        return "✅ approved"
    return "👀 review required"


class GithubPRClient:
    def __init__(self, token=GITHUB_TOKEN, username=GITHUB_USERNAME):
        self.token = token
        self.username = username

    def fetch_open_prs(self, username=None):
        if username is None:
            username = self.username
        url = f"{API_URL}/search/issues?q=author:{username}+type:pr+state:open"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()["items"]

    def get_pr_details(self, pr_url):

        headers = {"Authorization": f"token {GITHUB_TOKEN}"}

        pr_resp = requests.get(pr_url, headers=headers)
        pr_resp.raise_for_status()
        pr = pr_resp.json()

        reviews_url = pr_url + "/reviews"

        reviews_resp = requests.get(reviews_url, headers=headers)
        reviews_resp.raise_for_status()
        reviews = reviews_resp.json()
        self.reviews = reviews

        return {
            "title": pr["title"],
            "status": pr.get("mergeable_state", "unknown"),
            "comments": pr["comments"] + pr["review_comments"],
            "url": pr["html_url"],
            "review_status": get_review_status(reviews)
        }

    def load_prs(self):
        def pr_init(pr):
            icon = status_icon(pr["status"])
            status_tag = pr["status"]
            status_text = f"[{status_tag}]"
            review_text = pr["review_status"]
            review_icon = review_status_icon(self.reviews)
            if pr['comments'] > 0:
                full_text = f"💬({pr['comments']})"
            else:
                full_text = f"{review_icon}"
            full_text += f"{pr['title'][:80]} {status_text}"  # {review_text}, {status_text} {icon}\n"
            pr["full_text"] = full_text
            return pr

        raw_prs = self.fetch_open_prs(GITHUB_USERNAME)
        prs = [pr_init(self.get_pr_details(pr["pull_request"]["url"])) for pr in raw_prs]
        return prs
