import os
import tkinter as tk
from tkinter import ttk
import requests
import webbrowser

GITHUB_USERNAME = "trevorgrayson-earnin"
GITHUB_TOKEN = os.getenv("GH_TOKEN")
API_URL = "https://api.github.com"

REFRESH_INTERVAL_MS = 60 * 60 * 1000  # 1 hour


class PRViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Open PRs for {GITHUB_USERNAME}")
        self.root.geometry("800x250")

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(frame)
        self.scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = ttk.Frame(self.canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widgets = []

        self.root.bind("<r>", lambda e: self.poll_and_refresh())
        self.poll_and_refresh()

    def clear_ui(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.text_widgets.clear()

    def render_prs(self, prs):
        self.clear_ui()
        for pr in prs:
            icon = status_icon(pr["status"])
            status_tag = pr["status"]
            status_text = f"[{status_tag}]"
            review_text = pr["review_status"]
            full_text = f"{review_text}, {status_text} {icon} {pr['title'][:80]} | Comments: {pr['comments']}\n"

            text_widget = tk.Text(self.scroll_frame, height=1, wrap="word", bd=0, bg=self.root["bg"])
            text_widget.insert("1.0", full_text)

            # Apply color only to [status]
            start = full_text.index(status_text)
            end = start + len(status_text)
            tag_name = f"tag_{status_tag}"

            text_widget.tag_add(tag_name, f"1.{start}", f"1.{end}")
            text_widget.tag_config(tag_name, foreground=status_color(status_tag))

            # Make the entire line clickable
            def callback(event, url=pr["url"]):
                webbrowser.open_new_tab(url)
            text_widget.tag_add("link", "1.0", "end")
            text_widget.tag_bind("link", "<Button-1>", callback)
            text_widget.config(state="disabled", cursor="hand2", highlightthickness=0)
            text_widget.pack(fill=tk.X, pady=2)

            self.text_widgets.append(text_widget)

    def poll_and_refresh(self):
        try:
            prs = load_prs()
            self.render_prs(prs)
        except Exception as e:
            self.clear_ui()
            error_label = tk.Label(self.scroll_frame, text=f"Error: {str(e)}", fg="red")
            error_label.pack()

        self.root.after(REFRESH_INTERVAL_MS, self.poll_and_refresh)

if __name__ == "__main__":
    root = tk.Tk()
    app = PRViewerApp(root)
    root.mainloop()

