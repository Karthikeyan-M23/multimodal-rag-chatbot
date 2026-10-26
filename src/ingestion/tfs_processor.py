"""
TFS / Azure DevOps work items assigned to the signed-in user, via the
REST API (the web UI is a JavaScript app with no ticket data in its HTML).

Works with Azure DevOps Services (dev.azure.com, *.visualstudio.com) and
on-prem TFS 2015+ / Azure DevOps Server. Sign in with a Personal Access
Token (any username) or, on-prem, a Windows account (DOMAIN\\user).
"""

from html import unescape
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup

from config.settings import TFS_MAX_WORK_ITEMS
from src.ingestion.http_auth import AuthError, SignedInSession
from src.ingestion.web_processor import check_url


# Newest first; older servers reject versions they don't know with 400.
API_VERSIONS = ["7.0", "6.0", "5.0", "4.1", "3.0", "2.0", "1.0"]

BATCH_SIZE = 200

UI_SEGMENTS = {
    "_workitems", "_boards", "_backlogs", "_queries", "_sprints", "_git",
    "_apis", "_dashboards", "_build", "_release", "_wiki", "_settings", "_home",
}

# Fields shown in the ticket summary, in this order.
SUMMARY_FIELDS = [
    ("System.WorkItemType", "Type"),
    ("System.State", "State"),
    ("System.Reason", "Reason"),
    ("Microsoft.VSTS.Common.Priority", "Priority"),
    ("Microsoft.VSTS.Common.Severity", "Severity"),
    ("System.AssignedTo", "Assigned to"),
    ("System.TeamProject", "Project"),
    ("System.AreaPath", "Area"),
    ("System.IterationPath", "Iteration"),
    ("System.Tags", "Tags"),
    ("Microsoft.VSTS.Scheduling.StoryPoints", "Story points"),
    ("Microsoft.VSTS.Scheduling.OriginalEstimate", "Original estimate"),
    ("Microsoft.VSTS.Scheduling.RemainingWork", "Remaining work"),
    ("Microsoft.VSTS.Scheduling.DueDate", "Due date"),
    ("Microsoft.VSTS.Scheduling.TargetDate", "Target date"),
    ("System.CreatedBy", "Created by"),
    ("System.CreatedDate", "Created"),
    ("System.ChangedDate", "Last changed"),
    ("Microsoft.VSTS.Common.ResolvedDate", "Resolved"),
    ("Microsoft.VSTS.Common.ClosedDate", "Closed"),
]

# Long-text fields, in this order.
TEXT_FIELDS = [
    ("System.Description", "Description"),
    ("Microsoft.VSTS.TCM.ReproSteps", "Repro steps"),
    ("Microsoft.VSTS.Common.AcceptanceCriteria", "Acceptance criteria"),
    ("Microsoft.VSTS.TCM.SystemInfo", "System info"),
    ("Microsoft.VSTS.Common.Resolution", "Resolution"),
]


class TfsError(RuntimeError):
    pass


# --------------------------------------------------
# URL handling
# --------------------------------------------------

def parse_tfs_url(url: str) -> dict | None:
    """
    {"collection": <collection URL>, "project": <name or None>} for a
    TFS / Azure DevOps URL, else None.
    """

    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None

    host = parsed.hostname.lower()
    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    base = f"{parsed.scheme}://{parsed.netloc}"

    # Path segments before the first UI/API segment ("_workitems", ...).
    head = []
    for segment in segments:
        if segment.startswith("_"):
            break
        head.append(segment)

    has_ui_segment = len(head) < len(segments) and segments[len(head)].lower() in UI_SEGMENTS

    if host == "dev.azure.com":
        if not head:
            return None
        return {"collection": f"{base}/{head[0]}", "project": head[1] if len(head) > 1 else None}

    if host.endswith(".visualstudio.com"):
        # The organisation is the host; "DefaultCollection" is an optional legacy prefix.
        if head and head[0].lower() == "defaultcollection":
            head = head[1:]
        return {"collection": base, "project": head[0] if head else None}

    # On-prem TFS: http://server:8080/tfs/<Collection>/<Project>/...
    if head and head[0].lower() == "tfs":
        if len(head) < 2:
            return None
        return {"collection": f"{base}/tfs/{head[1]}", "project": head[2] if len(head) > 2 else None}

    # Azure DevOps Server 2019+ without /tfs: http://server/<Collection>/<Project>/_workitems
    if has_ui_segment and head:
        return {"collection": f"{base}/{head[0]}", "project": head[1] if len(head) > 1 else None}

    return None


def is_tfs_url(url: str) -> bool:
    return parse_tfs_url(url) is not None


# --------------------------------------------------
# REST client
# --------------------------------------------------

class TfsClient:

    def __init__(self, collection: str, username: str, password: str):

        self.collection = collection.rstrip("/")
        self.session = SignedInSession(username, password, collection)
        self.api_version = None

    def _call(self, method, path, **kwargs):
        """Request with the newest API version the server accepts."""

        url = f"{self.collection}/{path.lstrip('/')}"
        check_url(url)

        versions = [self.api_version] if self.api_version else API_VERSIONS

        for version in versions:

            separator = "&" if "?" in url else "?"
            response = self.session.request(
                method,
                f"{url}{separator}api-version={version}",
                headers={"Accept": "application/json"},
                **kwargs,
            )

            # Azure DevOps answers unauthenticated calls with a 203 sign-in page.
            if response.status_code == 203 or "json" not in response.headers.get("content-type", ""):
                if response.status_code in {200, 203}:
                    raise AuthError(
                        "TFS did not accept the sign-in. Use a Personal Access Token "
                        "(scope: Work Items - Read) as the password."
                    )

            if response.status_code == 400 and "version" in response.text.lower() and not self.api_version:
                continue

            if response.status_code == 404:
                raise TfsError(
                    "TFS collection or project not found. Paste a link like "
                    "https://dev.azure.com/<org>/<project> or "
                    "http://<server>/tfs/<Collection>/<Project>."
                )

            if response.status_code == 403:
                raise AuthError("Signed in, but this account can't read work items (403).")

            response.raise_for_status()
            self.api_version = version

            return response.json()

        raise TfsError("This TFS server does not support any known REST API version.")

    def get(self, path, **kwargs):
        return self._call("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self._call("POST", path, **kwargs)

    def me(self) -> str:
        data = self.get("_apis/connectionData")
        user = data.get("authenticatedUser", {})
        return user.get("providerDisplayName") or user.get("customDisplayName") or ""

    def assigned_ids(self, project: str | None) -> list[int]:

        scope = f"{quote(project)}/" if project else ""
        project_filter = "AND [System.TeamProject] = @project " if project else ""

        data = self.post(
            f"{scope}_apis/wit/wiql",
            json={
                "query": (
                    "SELECT [System.Id] FROM WorkItems "
                    f"WHERE [System.AssignedTo] = @Me {project_filter}"
                    "ORDER BY [System.ChangedDate] DESC"
                )
            },
        )

        return [item["id"] for item in data.get("workItems", [])]

    def work_items(self, ids: list[int]) -> list[dict]:

        items = []

        for start in range(0, len(ids), BATCH_SIZE):
            batch = ",".join(str(i) for i in ids[start:start + BATCH_SIZE])
            data = self.get(f"_apis/wit/workitems?ids={batch}&errorPolicy=omit")
            items.extend(item for item in data.get("value", []) if item)

        return items

    def comments(self, item_id: int) -> list[dict]:
        """Discussion entries from the update history (works on TFS 2015+)."""

        data = self.get(f"_apis/wit/workitems/{item_id}/updates")

        comments = []

        for update in data.get("value", []):

            history = update.get("fields", {}).get("System.History", {}).get("newValue")

            if history:
                by = update.get("revisedBy", {})
                comments.append(
                    {
                        "by": by.get("displayName") or by.get("name") or "",
                        "date": update.get("fields", {}).get("System.ChangedDate", {}).get("newValue")
                        or update.get("revisedDate", ""),
                        "text": html_to_text(history),
                    }
                )

        return comments


# --------------------------------------------------
# Formatting
# --------------------------------------------------

def html_to_text(value) -> str:

    if not value:
        return ""

    soup = BeautifulSoup(str(value), "html.parser")

    for br in soup.find_all("br"):
        br.replace_with("\n")

    for block in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4"]):
        block.insert_after("\n")

    lines = [" ".join(line.split()) for line in unescape(soup.get_text()).splitlines()]

    return "\n".join(line for line in lines if line)


def _display(value) -> str:

    if isinstance(value, dict):
        return value.get("displayName") or value.get("uniqueName") or ""

    if isinstance(value, str) and "<" in value and value.endswith(">"):
        # Older servers: "Jane Doe <DOMAIN\\jane>"
        return value.split("<")[0].strip()

    if isinstance(value, str) and len(value) >= 10 and value[4] == "-" and "T" in value:
        return value[:10]

    return "" if value is None else str(value)


def item_url(collection: str, item: dict) -> str:
    project = item.get("fields", {}).get("System.TeamProject", "")
    return f"{collection}/{quote(project)}/_workitems/edit/{item['id']}"


def format_work_item(item: dict, comments: list[dict]) -> str:

    fields = item.get("fields", {})

    lines = [f"Work item #{item['id']}: {fields.get('System.Title', '')}"]

    for key, label in SUMMARY_FIELDS:
        value = _display(fields.get(key))
        if value:
            lines.append(f"{label}: {value}")

    for key, label in TEXT_FIELDS:
        text = html_to_text(fields.get(key))
        if text:
            lines.append(f"\n{label}:\n{text}")

    if comments:
        lines.append("\nDiscussion:")
        for comment in comments:
            lines.append(f"- {_display(comment['date'])} {comment['by']}: {comment['text']}")

    return "\n".join(lines)


# --------------------------------------------------
# Entry point
# --------------------------------------------------

def extract_tfs_work_items(url: str, username: str = "", password: str = "", progress=None) -> list[dict]:

    target = parse_tfs_url(url)

    if target is None:
        raise TfsError("Not a TFS / Azure DevOps link.")

    if not password:
        raise AuthError(
            "TFS needs sign-in. Add the link again with \"Requires sign-in\" turned on "
            "and use a Personal Access Token (or your Windows password)."
        )

    client = TfsClient(target["collection"], username, password)

    if progress:
        progress("Signing in to TFS")

    me = client.me()

    if progress:
        progress("Finding work items assigned to you")

    ids = client.assigned_ids(target["project"])[:TFS_MAX_WORK_ITEMS]

    if not ids:
        raise TfsError(
            f"No work items are assigned to {me or 'this account'}"
            + (f" in project {target['project']}." if target["project"] else ".")
        )

    items = client.work_items(ids)
    documents = []

    scope = target["project"] or target["collection"].rsplit("/", 1)[-1]
    title = f"TFS · {scope} · assigned to {me}" if me else f"TFS · {scope}"

    for index, item in enumerate(items, start=1):

        if progress:
            progress(f"Reading work item {index}/{len(items)}")

        fields = item.get("fields", {})

        try:
            comments = client.comments(item["id"])
        except (TfsError, AuthError):
            raise
        except Exception:
            comments = []

        documents.append(
            {
                "text": format_work_item(item, comments),
                "metadata": {
                    "source": url,
                    "file_type": "tfs",
                    "title": title,
                    "url": item_url(target["collection"], item),
                    "work_item_id": item["id"],
                    "work_item_type": fields.get("System.WorkItemType", ""),
                    "state": fields.get("System.State", ""),
                    "section": f"#{item['id']} {fields.get('System.Title', '')}"[:120],
                },
            }
        )

    return documents
