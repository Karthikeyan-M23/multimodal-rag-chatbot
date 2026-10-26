"""
Signing in to protected sites with a username and password.

Supports HTTP Basic and Windows sign-in (NTLM / Negotiate, used by
on-prem TFS, SharePoint and IIS intranets). Sites that use an HTML login
form or single sign-on (MFA, OAuth redirects) cannot be signed in to
this way.
"""

from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth


class AuthError(RuntimeError):
    pass


LOGIN_FAILED = (
    "Sign-in failed. Check the username and password. "
    "For TFS / Azure DevOps you can use a Personal Access Token as the password; "
    "for Windows sign-in use DOMAIN\\username."
)


def _ntlm(username, password):

    try:
        from requests_ntlm import HttpNtlmAuth
    except ImportError:
        raise AuthError("Windows sign-in needs the requests_ntlm package (pip install requests_ntlm).")

    return HttpNtlmAuth(username, password)


def _challenges(response) -> str:
    return response.headers.get("WWW-Authenticate", "").lower()


class SignedInSession:
    """
    requests.Session wrapper. The first request goes out without
    credentials; on a 401 the server's challenge decides between Windows
    sign-in (NTLM / Negotiate) and Basic, which is then reused. This way a
    password is never sent as Basic to a server that wants NTLM.
    Credentials are only ever sent to the host they were given for.
    """

    def __init__(self, username: str = "", password: str = "", url: str = ""):

        self.session = requests.Session()
        self.username = username or ""
        self.password = password or ""
        self.host = (urlparse(url).hostname or "").lower()
        self.auth = None

    @property
    def has_credentials(self) -> bool:
        return bool(self.password)

    def _same_host(self, url) -> bool:
        return (urlparse(url).hostname or "").lower() == self.host

    def _choose_auth(self, response):

        challenge = _challenges(response)

        if "ntlm" in challenge or "negotiate" in challenge:
            return _ntlm(self.username, self.password)

        return HTTPBasicAuth(self.username, self.password)

    def request(self, method, url, **kwargs):

        kwargs.setdefault("timeout", 30)

        may_sign_in = self.has_credentials and self._same_host(url)
        auth = self.auth if may_sign_in else None

        response = self.session.request(method, url, auth=auth, **kwargs)

        if response.status_code != 401 or not may_sign_in:
            return response

        if self.auth is None:
            self.auth = self._choose_auth(response)
            response = self.session.request(method, url, auth=self.auth, **kwargs)

        if response.status_code == 401:
            raise AuthError(LOGIN_FAILED)

        return response

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


def looks_like_login_page(html: str) -> bool:
    """A 200 response that is really a sign-in form (or SSO page)."""

    lowered = html[:200_000].lower()

    return 'type="password"' in lowered or "type='password'" in lowered or (
        "login.microsoftonline.com" in lowered
    )
