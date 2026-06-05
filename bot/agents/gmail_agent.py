import os
import pickle
from datetime import datetime
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bot.db.repository import get_token, save_token
from bot.utils.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailAgent:
    def __init__(self, telegram_id: int):
        self.telegram_id = telegram_id
        self.service = None

    async def _load_credentials(self) -> Optional[Credentials]:
        token_data = await get_token(self.telegram_id, "gmail")
        if token_data:
            return Credentials.from_authorized_user_info(token_data, SCOPES)
        return None

    async def _save_credentials(self, creds: Credentials):
        info = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }
        await save_token(self.telegram_id, "gmail", info)

    async def ensure_authenticated(self) -> bool:
        creds = await self._load_credentials()

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            await self._save_credentials(creds)

        if not creds or not creds.valid:
            return False

        self.service = build("gmail", "v1", credentials=creds)
        return True

    def get_auth_url(self) -> str:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "redirect_uris": [settings.gmail_redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            SCOPES,
        )
        return flow.authorization_url()[0]

    async def handle_callback(self, code: str) -> bool:
        try:
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": settings.gmail_client_id,
                        "client_secret": settings.gmail_client_secret,
                        "redirect_uris": [settings.gmail_redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                SCOPES,
            )
            flow.fetch_token(code=code)
            await self._save_credentials(flow.credentials)
            self.service = build("gmail", "v1", credentials=flow.credentials)
            return True
        except Exception as e:
            raise RuntimeError(f"Gmail auth callback failed: {e}")

    async def list_emails(self, max_results: int = 10, query: str = "") -> list[dict]:
        if not self.service:
            raise RuntimeError("Not authenticated")
        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=query)
                .execute()
            )
            messages = results.get("messages", [])
            emails = []
            for msg in messages:
                details = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="metadata")
                    .execute()
                )
                headers = {h["name"]: h["value"] for h in details.get("payload", {}).get("headers", [])}
                emails.append({
                    "id": msg["id"],
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": details.get("snippet", ""),
                    "label_ids": details.get("labelIds", []),
                })
            return emails
        except HttpError as e:
            raise RuntimeError(f"Gmail API error: {e}")

    async def read_email(self, msg_id: str) -> dict:
        if not self.service:
            raise RuntimeError("Not authenticated")
        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            parts = msg.get("payload", {}).get("parts", [])
            body = ""
            for part in parts:
                if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                    import base64
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break
            return {
                "id": msg["id"],
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "body": body,
                "snippet": msg.get("snippet", ""),
                "label_ids": msg.get("labelIds", []),
            }
        except HttpError as e:
            raise RuntimeError(f"Gmail API error: {e}")

    async def send_email(self, to: str, subject: str, body: str) -> str:
        if not self.service:
            raise RuntimeError("Not authenticated")
        import base64
        from email.mime.text import MIMEText

        try:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            sent = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
            return sent["id"]
        except HttpError as e:
            raise RuntimeError(f"Gmail send error: {e}")

    async def modify_email(self, msg_id: str, add_labels: list[str] = None, remove_labels: list[str] = None):
        if not self.service:
            raise RuntimeError("Not authenticated")
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        try:
            self.service.users().messages().modify(userId="me", id=msg_id, body=body).execute()
        except HttpError as e:
            raise RuntimeError(f"Gmail modify error: {e}")

    async def delete_email(self, msg_id: str):
        if not self.service:
            raise RuntimeError("Not authenticated")
        try:
            self.service.users().messages().trash(userId="me", id=msg_id).execute()
        except HttpError as e:
            raise RuntimeError(f"Gmail delete error: {e}")

    async def list_labels(self) -> list[dict]:
        if not self.service:
            raise RuntimeError("Not authenticated")
        try:
            results = self.service.users().labels().list(userId="me").execute()
            return results.get("labels", [])
        except HttpError as e:
            raise RuntimeError(f"Gmail labels error: {e}")

    async def search_emails(self, query: str, max_results: int = 20) -> list[dict]:
        return await self.list_emails(max_results=max_results, query=query)
