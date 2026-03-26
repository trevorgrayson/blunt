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

    def _headers(self):
        if not self.token:
            return {}
        return {"Authorization": f"token {self.token}"}

    def fetch_open_prs(self, username=None):
        if username is None:
            username = self.username
        url = f"{API_URL}/search/issues?q=author:{username}+type:pr+state:open"
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()["items"]

    def get_pr_details(self, pr_url):
        pr_resp = requests.get(pr_url, headers=self._headers())
        pr_resp.raise_for_status()
        pr = pr_resp.json()

        reviews_url = pr_url + "/reviews"

        reviews_resp = requests.get(reviews_url, headers=self._headers())
        reviews_resp.raise_for_status()
        reviews = reviews_resp.json()
        self.reviews = reviews

        issue_comments = self._fetch_issue_comments(pr)
        review_comments = self._fetch_review_comments(pr)
        action_items = self._build_action_items(pr, reviews, issue_comments, review_comments)

        return {
            "title": pr["title"],
            "status": pr.get("mergeable_state", "unknown"),
            "comments": pr["comments"] + pr["review_comments"],
            "url": pr["html_url"],
            "review_status": get_review_status(reviews),
            "action_items": action_items,
        }

    def _fetch_issue_comments(self, pr):
        comments_url = pr.get("comments_url")
        if not comments_url:
            return []
        resp = requests.get(comments_url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _fetch_review_comments(self, pr):
        comments_url = pr.get("review_comments_url")
        if not comments_url:
            return []
        resp = requests.get(comments_url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _latest_reviews_by_user(self, reviews):
        latest = {}
        for review in sorted(reviews, key=lambda r: r.get("submitted_at") or ""):
            user = (review.get("user") or {}).get("login")
            if not user:
                continue
            latest[user] = review
        return latest

    def _snippet(self, text, limit=120):
        if not text:
            return ""
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3] + "..."

    def _build_action_items(self, pr, reviews, issue_comments, review_comments):
        action_items = []
        latest_reviews = self._latest_reviews_by_user(reviews)

        for user, review in latest_reviews.items():
            state = review.get("state")
            if state == "CHANGES_REQUESTED":
                action_items.append(f"Address changes requested by {user}.")
            elif state == "COMMENTED":
                action_items.append(f"Review feedback from {user}.")

        for comment in issue_comments:
            commenter = (comment.get("user") or {}).get("login")
            if not commenter or commenter == self.username:
                continue
            body = self._snippet(comment.get("body", ""))
            if body:
                action_items.append(f"Reply to {commenter}: {body}")
            else:
                action_items.append(f"Reply to {commenter}.")

        for comment in review_comments:
            commenter = (comment.get("user") or {}).get("login")
            if not commenter or commenter == self.username:
                continue
            path = comment.get("path")
            line = comment.get("line") or comment.get("position")
            location = f" on {path}:{line}" if path and line else ""
            body = self._snippet(comment.get("body", ""))
            if body:
                action_items.append(f"Review comment from {commenter}{location}: {body}")
            else:
                action_items.append(f"Review comment from {commenter}{location}.")

        if not action_items:
            action_items.append("No action items detected.")

        return action_items

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

        raw_prs = self.fetch_open_prs(self.username)
        prs = [pr_init(self.get_pr_details(pr["pull_request"]["url"])) for pr in raw_prs]
        return prs
