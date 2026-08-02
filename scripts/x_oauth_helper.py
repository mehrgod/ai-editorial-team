import base64
import hashlib
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from dotenv import load_dotenv


AUTHORIZATION_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
CALLBACK_URL = "http://127.0.0.1:8000/callback"
SCOPES = ["tweet.read", "tweet.write", "users.read", "offline.access"]


def main() -> None:
    load_dotenv()

    client_id = _required_env("X_CLIENT_ID")
    client_secret = _required_env("X_CLIENT_SECRET")
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _code_challenge(code_verifier)

    authorization_url = _authorization_url(
        client_id=client_id,
        state=state,
        code_challenge=code_challenge,
    )

    print("\nAuthorize this X account:")
    print(authorization_url)
    print("\nWaiting for callback on http://127.0.0.1:8000/callback ...")

    callback = _wait_for_callback()
    if callback.get("state") != state:
        raise SystemExit("OAuth state mismatch. Please restart the helper.")

    code = callback.get("code")
    if not code:
        error = callback.get("error") or "missing authorization code"
        raise SystemExit(f"OAuth authorization failed: {error}")

    token_response = _exchange_code_for_tokens(
        code=code,
        code_verifier=code_verifier,
        client_id=client_id,
        client_secret=client_secret,
    )

    print("\naccess_token:")
    print(token_response.get("access_token", ""))
    print("\nrefresh_token:")
    print(token_response.get("refresh_token", ""))
    print("\nexpires_in:")
    print(token_response.get("expires_in", ""))


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set in the environment or .env file.")
    return value


def _code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _authorization_url(
    *, client_id: str, state: str, code_challenge: str
) -> str:
    query = urllib_parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": CALLBACK_URL,
            "scope": " ".join(SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTHORIZATION_URL}?{query}"


def _wait_for_callback() -> dict[str, str]:
    callback_data = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed_url = urllib_parse.urlparse(self.path)
            query = urllib_parse.parse_qs(parsed_url.query)
            callback_data.update(
                {key: values[0] for key, values in query.items() if values}
            )

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(
                b"Authorization received. You can return to the terminal."
            )

        def log_message(self, format: str, *args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 8000), CallbackHandler)
    try:
        server.handle_request()
    finally:
        server.server_close()

    return callback_data


def _exchange_code_for_tokens(
    *,
    code: str,
    code_verifier: str,
    client_id: str,
    client_secret: str,
) -> dict:
    basic_auth = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")
    ).decode("ascii")
    body = urllib_parse.urlencode(
        {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": CALLBACK_URL,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")
    request = urllib_request.Request(
        TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "AI Editorial Team OAuth Helper",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=30) as response:
            raw_body = response.read().decode("utf-8")
    except Exception as exc:
        raise SystemExit(f"Token exchange failed: {exc}") from exc

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise SystemExit("Token exchange returned invalid JSON.") from exc


if __name__ == "__main__":
    main()
