import html
import re


def plain_text(value):
    for _ in range(2):
        value = html.unescape(value or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def salary_fields(text):
    """Only parse explicitly labelled currency and period. Never guess FX."""
    text = plain_text(text)
    currency = "TWD" if re.search(r"TWD|NT\$|新台幣", text, re.I) else "USD" if re.search(r"USD|US\$", text, re.I) else None
    period = "month" if re.search(r"月薪|月|month", text, re.I) else "year" if re.search(r"年薪|年|year|annual|annum", text, re.I) else None
    values = re.findall(r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*[kK]?", text)
    amounts = [float(v.strip().rstrip("kK").replace(",", "")) * (1000 if v.strip().lower().endswith("k") else 1) for v in values]
    if not currency or not period or not amounts:
        return {"salary_min": None, "salary_max": None, "currency": None, "period": None}
    return {"salary_min": min(amounts), "salary_max": max(amounts), "currency": currency, "period": period}


def validate_filters(data):
    if not isinstance(data, dict):
        raise ValueError("篩選條件必須是物件")
    region = data.get("region", "taiwan")
    remote = data.get("remote", "any")
    unit = data.get("salary_unit", "TWD/month")
    if region not in ("taiwan", "global") or remote not in ("any", "remote", "hybrid", "onsite") or unit not in ("TWD/month", "TWD/year", "USD/year", "USD/month"):
        raise ValueError("篩選條件不正確")
    minimum = float(data.get("salary_min") or 0)
    if not 0 <= minimum <= 100000000:
        raise ValueError("薪資必須介於 0 與 100,000,000")
    keyword = str(data.get("keyword", "")).strip()
    location = str(data.get("location", "")).strip()
    if len(keyword) > 200 or len(location) > 100:
        raise ValueError("關鍵字或地點過長")
    sources = data.get('sources', ['appier','canonical','remotive'])
    allowed = {'appier','canonical','remotive','104','linkedin','cake','indeed','remoteok'}
    if not isinstance(sources,list) or not sources or any(not isinstance(s,str) or s not in allowed for s in sources):
        raise ValueError('請至少選擇一個有效的職缺來源')
    return {"sources": list(dict.fromkeys(sources)), "keyword": keyword, "location": location, "region": region, "remote": remote, "salary_unit": unit, "salary_min": minimum, "include_unknown": data.get("include_unknown", False) in (True, "true", "1")}


def keyword_matches(text, keyword):
    # Latin skills must not match inside words such as community/opportunity.
    # ASCII boundaries still allow Chinese text like 熟悉Unity開發.
    term = re.escape(keyword)
    if keyword in ("unity", "unity3d", "u3d", "unity engine"):
        term = r"(?:unity(?:3d| engine)?|u3d)"
    left = r"(?<![a-z0-9_])" if re.match(r"[a-z0-9_]", keyword) else ""
    right = r"(?![a-z0-9_])" if re.search(r"[a-z0-9_+#]$", keyword) else ""
    return re.search(left + term + right, text) is not None


def matches(job, filters):
    if filters["region"] == "taiwan" and not job["taiwan"]:
        return False
    if filters["remote"] != "any" and job["remote"] != filters["remote"]:
        return False
    if filters["location"].casefold() not in job["location"].casefold():
        return False
    keywords = [v.strip().casefold() for v in re.split(r"[,，]", filters["keyword"]) if v.strip()]
    haystack = " ".join(str(job.get(k, "")) for k in ("title", "company", "description", "tags")).casefold()
    if keywords and not any(keyword_matches(haystack, keyword) for keyword in keywords):
        return False
    if filters["salary_min"]:
        currency, period = filters["salary_unit"].split("/")
        if job.get("salary_max") is None:
            return filters["include_unknown"]
        if (job.get("currency"), job.get("period")) != (currency, period):
            return False
        if job["salary_max"] < filters["salary_min"]:
            return False
    return True
