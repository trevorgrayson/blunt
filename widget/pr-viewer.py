import os
import curses
import requests

GITHUB_USERNAME = "trevorgrayson-earnin"
GITHUB_TOKEN = os.getenv("GH_TOKEN")
API_URL = "https://api.github.com"

def fetch_open_prs(username):
    url = f"{API_URL}/search/issues?q=author:{username}+type:pr+state:open"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["items"]

def get_pr_details(pr_url):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp = requests.get(pr_url, headers=headers)
    resp.raise_for_status()
    pr = resp.json()
    return {
        "title": pr["title"],
        "status": pr.get("mergeable_state", "unknown"),
        "comments": pr["comments"] + pr["review_comments"]
    }

def display_prs(stdscr, prs):
    curses.curs_set(0)
    stdscr.clear()
    stdscr.addstr(0, 0, f"Open PRs for {GITHUB_USERNAME}:", curses.A_BOLD)

    for i, pr in enumerate(prs, start=2):
        line = f"{i-1:2d}. {pr['title'][:50]:50} | Status: {pr['status']:<10} | Comments: {pr['comments']}"
        stdscr.addstr(i, 0, line)

    stdscr.addstr(i + 2, 0, "Press any key to exit...")
    stdscr.refresh()
    stdscr.getch()

def main(stdscr):
    try:
        raw_prs = fetch_open_prs(GITHUB_USERNAME)
        prs = [get_pr_details(pr["pull_request"]["url"]) for pr in raw_prs]
        display_prs(stdscr, prs)
    except Exception as e:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Error: {str(e)}", curses.A_BOLD)
        stdscr.refresh()
        stdscr.getch()

if __name__ == "__main__":
    curses.wrapper(main)

