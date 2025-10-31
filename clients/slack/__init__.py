# import argparse
# import requests
# import os
#
# # SLACK_TOKEN = os.environ.get("SLACK_CLIENT_ID")  # Export this before running
# # CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")   # Or hardcode your channel ID
# #
# # def send_slack_message(message: str):
# #     headers = {
# #         "Authorization": f"Bearer {SLACK_TOKEN}",
# #         "Content-type": "application/json"
# #     }
# #
# #     payload = {
# #         "channel": CHANNEL_ID,
# #         "text": message
# #     }
# #
# #     response = requests.post("https://slack.com/api/chat.postMessage", json=payload, headers=headers)
# #     data = response.json()
# #     if data.get("ok"):
# #         print("✅ Message sent successfully!")
# #     else:
# #         print(f"❌ Failed to send message: {data.get('error')}")
#
# import os
# import html
# from slack_sdk.oauth import AuthorizeUrlGenerator
# from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
# from slack_sdk.oauth.state_store import FileOAuthStateStore
#
# # Issue and consume state parameter value on the server-side.
# state = FileOAuthStateStore(expiration_seconds=300, base_dir="./data")
# # Persist installation data and lookup it by IDs.
# installation_store = FileInstallationStore(base_dir="./data")
#
# # Build https://slack.com/oauth/v2/authorize with sufficient query parameters
# url_generator = AuthorizeUrlGenerator(
#     client_id=os.environ["SLACK_CLIENT_ID"],
#     scopes=["app_mentions:read", "chat:write"],
#     user_scopes=["search:read"],
# )
#
#
# print("Visit this URL to install the app:")
# print(url_generator.generate(state))
#
# # -----------------------------
# # 3. Exchange the code for tokens (done in your callback handler)
# # -----------------------------
# from slack_sdk.oauth.installation_store import FileInstallationStore
# from slack_sdk.oauth.state_store import FileOAuthStateStore
# from slack_sdk.oauth import OAuthFlow
#
# installation_store = FileInstallationStore(base_dir="./data/installations")
# state_store = FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states")
#
# oauth_flow = OAuthFlow(
#     client_id=client_id,
#     client_secret=client_secret,
#     scopes=scopes,
#     installation_store=installation_store,
#     state_store=state_store,
#     redirect_uri=redirect_uri
# )
#
# # Imagine this is inside your web framework's callback handler:
# def handle_callback(code, state):
#     # Verify state and exchange code for tokens
#     installation = oauth_flow.finish(code=code, state=state)
#     print("Installation stored:", installation)
#
#     # -----------------------------
#     # 4. Use the issued token
#     # -----------------------------
#     client = WebClient(token=installation.bot_token)
#     resp = client.auth_test()
#     print(resp)
# import os
# import html
# from slack_sdk.oauth import AuthorizeUrlGenerator
# from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
# from slack_sdk.oauth.state_store import FileOAuthStateStore
#
# # Issue and consume state parameter value on the server-side.
# state_store = FileOAuthStateStore(expiration_seconds=300, base_dir="./data")
# # Persist installation data and lookup it by IDs.
# installation_store = FileInstallationStore(base_dir="./data")
#
# # Build https://slack.com/oauth/v2/authorize with sufficient query parameters
# authorize_url_generator = AuthorizeUrlGenerator(
#     client_id=os.environ["SLACK_CLIENT_ID"],
#     scopes=["app_mentions:read", "chat:write"],
#     user_scopes=["search:read"],
# )
#
# # Generate a random value and store it on the server-side
# state = state_store.issue()
# # https://slack.com/oauth/v2/authorize?state=(generated value)&client_id={client_id}&scope=app_mentions:read,chat:write&user_scope=search:read
# url = authorize_url_generator.generate(state)
# print(html.escape(url))