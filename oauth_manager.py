import asyncio
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class OAuthManager:
    def __init__(self, client_file="oauth_client.json", user_store=None):
        self.client_file = Path(client_file)
        self.user_store = user_store
        self.pending = {}

    def get_credentials(self, user):
        token_data = self.user_store.deserialize_token(user["token_json"])
        if not token_data:
            return None
        credentials = Credentials.from_authorized_user_info(token_data, SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.user_store.upsert_token(
                user["discord_id"],
                user["display_name"],
                credentials.to_json(),
            )
        return credentials if credentials.valid else None

    def create_authorization(self, discord_id, display_name):
        if not self.client_file.exists():
            raise FileNotFoundError(
                f"OAuth client file not found: {self.client_file}"
            )

        callback_queue = queue.Queue(maxsize=1)
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_file), SCOPES
        )
        server = HTTPServer(
            ("127.0.0.1", 0),
            self._callback_handler(callback_queue),
        )
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        flow.redirect_uri = redirect_uri
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        self.pending[state] = (flow, server, callback_queue, discord_id, display_name)
        threading.Thread(
            target=server.serve_forever,
            name=f"oauth-callback-{discord_id}",
            daemon=True,
        ).start()
        asyncio.create_task(self._finish_authorization(state))
        return authorization_url

    def _callback_handler(self, callback_queue):
        manager = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlparse(self.path).query)
                callback_queue.put(
                    {
                        "code": query.get("code", [None])[0],
                        "state": query.get("state", [None])[0],
                        "error": query.get("error", [None])[0],
                    }
                )
                body = (
                    "Authorization complete. You can return to Discord."
                    if query.get("code", [None])[0]
                    else "Authorization was not completed."
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))

            def log_message(self, format, *args):
                return

        return CallbackHandler

    async def _finish_authorization(self, state):
        flow, server, callback_queue, discord_id, display_name = self.pending[state]
        try:
            callback = await asyncio.to_thread(callback_queue.get, True, 600)
            if callback["error"]:
                raise RuntimeError(f"Google authorization failed: {callback['error']}")
            if callback["state"] != state or not callback["code"]:
                raise RuntimeError("Google authorization returned an invalid callback.")
            flow.fetch_token(code=callback["code"])
            self.user_store.upsert_token(
                discord_id, display_name, flow.credentials.to_json()
            )
        finally:
            server.shutdown()
            server.server_close()
            self.pending.pop(state, None)

