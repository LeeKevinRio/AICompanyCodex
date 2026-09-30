import json
import re
import urllib.request
from .domain import plain_text, salary_fields

SOURCES = {
    "appier": {"name": "Appier 招募", "url": "https://boards-api.greenhouse.io/v1/boards/appier/jobs?content=true", "ttl": 1800, "kind": "greenhouse", "company": "Appier"},
    "canonical": {"name": "Canonical 招募", "url": "https://boards-api.greenhouse.io/v1/boards/canonical/jobs?content=true", "ttl": 1800, "kind": "greenhouse", "company": "Canonical"},
    "remotive": {"name": "Remotive", "url": "https://remotive.com/api/remote-jobs", "ttl": 21600, "kind": "remotive"},
}


def fetch_source(key):
    source = SOURCES[key]
    request = urllib.request.Request(source["url"], headers={"User-Agent": "WorkApp/0.1 (personal job monitoring)", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.load(response)
    if not isinstance(payload.get("jobs"), list):
        raise ValueError("資料來源未回傳職缺列表")
    # A partial response must never make previously seen jobs look closed.
    if source["kind"] == "remotive" and payload.get("total-job-count", len(payload["jobs"])) > len(payload["jobs"]):
        raise ValueError("資料來源回傳不完整，保留前次職缺")
    return [normalize(key, item) for item in payload["jobs"]]


def normalize(key, item):
    source = SOURCES[key]
    description = plain_text(item.get("content", item.get("description", "")))
    title = item["title"]
    if source["kind"] == "greenhouse":
        location = item.get("location", {}).get("name", "未提供地點")
        company = item.get("company_name") or source["company"]
        url = item["absolute_url"]
        published = item.get("first_published") or item.get("updated_at", "")
        tags = ", ".join(dept["name"] for dept in item.get("departments", []))
        hint = (location + " " + title).lower()
        remote = "hybrid" if "hybrid" in hint else "remote" if re.search(r"remote|home.based|遠端", hint) else "onsite" if re.search(r"office.based|on.site", hint) else "unknown"
        salary = "薪資未公開"
    else:
        location = item.get("candidate_required_location") or "地區未提供"
        company, url = item["company_name"], item["url"]
        published = item.get("publication_date", "")
        tags = ", ".join(item.get("tags", []))
        remote = "remote"
        salary = item.get("salary") or "薪資未公開"
    # Worldwide means location eligibility, not simply a remote job flag.
    local_taiwan = bool(re.search(r"taiwan|taipei|taichung|kaohsiung|hsinchu|台灣|臺灣|台北|臺北|新竹|高雄|台中|臺中", location, re.I))
    taiwan = local_taiwan or bool(re.search(r"worldwide|anywhere|global", location, re.I))
    return {"id": key + ":" + str(item["id"]), "source": key, "source_name": source["name"], "title": title, "company": company, "url": url, "location": location, "taiwan": taiwan, "local_taiwan": local_taiwan, "remote": remote, "salary": salary, **salary_fields(salary), "published": published, "tags": tags, "description": description}
