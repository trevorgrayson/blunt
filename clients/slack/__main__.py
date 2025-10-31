# from argparse import ArgumentParser
# from . import SLACK_TOKEN, CHANNEL_ID, send_slack_message
# 
# 
# def main():
#     parser = ArgumentParser(description="Send a Slack message as your user.")
#     parser.add_argument("message", help="The message to send")
#     args = parser.parse_args()
# 
#     if not SLACK_TOKEN or not CHANNEL_ID:
#         print("❌ Missing SLACK_USER_TOKEN or SLACK_CHANNEL_ID environment variable.")
#         return
# 
#     send_slack_message(args.message)
# 
# if __name__ == "__main__":
#     main()
import os
import html
from slack_sdk.oauth import AuthorizeUrlGenerator
from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
from slack_sdk.oauth.state_store import FileOAuthStateStore

# Issue and consume state parameter value on the server-side.
state_store = FileOAuthStateStore(expiration_seconds=300, base_dir="./data")
# Persist installation data and lookup it by IDs.
installation_store = FileInstallationStore(base_dir="./data")

# Build https://slack.com/oauth/v2/authorize with sufficient query parameters
authorize_url_generator = AuthorizeUrlGenerator(
    client_id=os.environ["SLACK_CLIENT_ID"],
    scopes=["app_mentions:read", "chat:write"],
    user_scopes=["search:read"],
)

# Generate a random value and store it on the server-side
state = state_store.issue()
# https://slack.com/oauth/v2/authorize?state=(generated value)&client_id={client_id}&scope=app_mentions:read,chat:write&user_scope=search:read
url = authorize_url_generator.generate(state)
print(url)