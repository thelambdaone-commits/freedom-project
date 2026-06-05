import re
import json
from typing import Optional
from datetime import datetime

from scrapling.fetchers import StealthyFetcher, StealthySession

from bot.utils.config import settings
from bot.db.repository import save_session, get_session, save_domain, get_domains


DASHBOARD_URL = "https://dash.domain.digitalplat.org"
LOGIN_URL = f"{DASHBOARD_URL}/auth/login"
REGISTER_URL = f"{DASHBOARD_URL}/panel/register"
MANAGER_URL = f"{DASHBOARD_URL}/panel/manager"


class DigitalPlatAgent:
    def __init__(self, telegram_id: int):
        self.telegram_id = telegram_id
        self._session = None

    async def _get_session(self) -> StealthySession:
        if self._session is None:
            self._session = StealthySession(
                headless=True,
                solve_cloudflare=True,
                network_idle=True,
                timeout=60000,
            )
        return self._session

    async def _restore_or_create_session(self) -> StealthySession:
        session = await self._get_session()
        saved = await get_session(self.telegram_id, "digitalplat")
        if saved:
            for cookie in saved.get("cookies", []):
                session._set_cookie(cookie)
        return session

    async def _save_session_state(self):
        if not self._session:
            return
        await save_session(self.telegram_id, "digitalplat", {})

    async def login(self, email: str, password: str) -> dict:
        session = await self._get_session()

        try:
            page = session.fetch(
                LOGIN_URL,
                headless=True,
                solve_cloudflare=True,
                network_idle=True,
            )

            email_input = page.css("#email") or page.css("input[name='email']") or page.css("input[type='email']")
            if not email_input:
                raise RuntimeError("Could not find email input on login page")
            email_input[0].attrib["value"] = email

            next_btn = page.css("button:has-text('Next')") or page.css("button[onclick*='nextStep']")
            if next_btn:
                from scrapling.fetchers import DynamicFetcher
                page = DynamicFetcher.fetch(LOGIN_URL, headless=True, solve_cloudflare=True)
                page.evaluate(f"document.getElementById('email').value = '{email}'")
                page.evaluate("nextStep()")

                password_input = page.css("#password") or page.css("input[name='password']") or page.css("input[type='password']")
                if password_input:
                    page.evaluate(f"document.getElementById('password').value = '{password}'")

                submit = page.css("button[type='submit']")
                if submit:
                    submit[0].click()
                    import time
                    time.sleep(3)
                    current_url = page.url

                    await save_session(self.telegram_id, "digitalplat", {
                        "cookies": [],
                        "logged_in": True,
                        "last_url": current_url,
                    })

                    return {"status": "success", "url": current_url}

            return {"status": "failed", "reason": "Could not complete login flow"}
        except Exception as e:
            raise RuntimeError(f"DigitalPlat login error: {e}")

    async def check_availability(self, domain_name: str, extension: str) -> dict:
        session = await self._get_session()
        ext_map = {
            "us.kg": ".us.kg",
            "xx.kg": ".xx.kg",
            "dpdns.org": ".dpdns.org",
            "qzz.io": ".qzz.io",
        }
        ext = ext_map.get(extension.replace(".", ""), f".{extension}")

        check_url = f"{DASHBOARD_URL}/panel/register/check?name={domain_name}&domain={ext}"
        try:
            page = session.fetch(check_url, headless=True, solve_cloudflare=True, network_idle=True)
            text = page.text

            if "available" in text.lower() or "disponible" in text.lower():
                return {"available": True, "domain": f"{domain_name}{ext}"}
            elif "taken" in text.lower() or "unavailable" in text.lower() or "already" in text.lower():
                return {"available": False, "domain": f"{domain_name}{ext}"}
            else:
                return {"available": "unknown", "domain": f"{domain_name}{ext}", "response": text[:500]}
        except Exception as e:
            raise RuntimeError(f"Check availability error: {e}")

    async def register_domain(self, domain_name: str, extension: str) -> dict:
        session = await self._get_session()
        ext_map = {
            "us.kg": ".us.kg",
            "xx.kg": ".xx.kg",
            "dpdns.org": ".dpdns.org",
            "qzz.io": ".qzz.io",
        }
        ext = ext_map.get(extension.replace(".", ""), f".{extension}")

        try:
            page = session.fetch(
                f"{DASHBOARD_URL}/panel/register",
                headless=True,
                solve_cloudflare=True,
                network_idle=True,
            )

            name_input = page.css("input[name='name']")
            if name_input:
                name_input[0].attrib["value"] = domain_name

            domain_select = page.css("select[name='domain']")
            if domain_select:
                from scrapling.fetchers import DynamicFetcher
                page = DynamicFetcher.fetch(
                    f"{DASHBOARD_URL}/panel/register",
                    headless=True, solve_cloudflare=True, network_idle=True,
                )
                page.evaluate(f"document.querySelector('input[name=\"name\"]').value = '{domain_name}'")
                page.evaluate(f"document.querySelector('select[name=\"domain\"]').value = '{ext}'")

                checkbox = page.css("#termsCheckbox")
                if checkbox:
                    page.evaluate("document.getElementById('termsCheckbox').checked = true")

                submit = page.css("#submitBtn") or page.css("button[type='submit']")
                if submit:
                    import time
                    submit[0].click()
                    time.sleep(3)

                    await save_domain(self.telegram_id, f"{domain_name}{ext}", ext)
                    return {
                        "status": "submitted",
                        "domain": f"{domain_name}{ext}",
                        "url": page.url,
                    }

            return {"status": "failed", "reason": "Could not fill registration form"}
        except Exception as e:
            raise RuntimeError(f"Register domain error: {e}")

    async def list_my_domains(self) -> list[dict]:
        session = await self._get_session()
        try:
            page = session.fetch(
                f"{DASHBOARD_URL}/panel/manager",
                headless=True, solve_cloudflare=True, network_idle=True,
            )
            domains = []
            for link in page.css("a[href^='/panel/manager/']"):
                domain_text = link.text.strip()
                if domain_text:
                    domains.append({"domain": domain_text, "url": f"{DASHBOARD_URL}{link.attrib.get('href', '')}"})
            return domains
        except Exception as e:
            raise RuntimeError(f"List domains error: {e}")

    async def get_domain_status(self, domain: str) -> dict:
        session = await self._get_session()
        try:
            page = session.fetch(
                f"{DASHBOARD_URL}/panel/manager/{domain}",
                headless=True, solve_cloudflare=True, network_idle=True,
            )
            text = page.text
            ns_match = re.findall(r'ns\d+\.[\w.]+', text)
            return {
                "domain": domain,
                "nameservers": ns_match[:4] if ns_match else [],
                "content_preview": text[:1000],
            }
        except Exception as e:
            raise RuntimeError(f"Domain status error: {e}")

    async def close(self):
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
