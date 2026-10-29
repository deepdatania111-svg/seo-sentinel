
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="SEO Sentinel", page_icon="🔎", layout="wide")
st.title("🔎 SEO Sentinel")
st.caption("Website SEO Audit & Fix Prioritizer")

UA = "SEOSentinelAuditBot/1.0"
HEADERS = {"User-Agent": UA}
RULES = {
    "Missing title": ("High", 80, "Add a unique, descriptive page title."),
    "Missing meta description": (
        "Medium", 50, "Write a useful, page-specific description."
    ),
    "Missing H1": ("Medium", 55, "Add a clear primary heading."),
    "Missing canonical": (
        "Low", 25, "Review whether the page needs a canonical URL."
    ),
    "Image missing alt": (
        "Medium", 50, "Add appropriate alt text to informative images."
    ),
    "HTTP error": (
        "High", 85, "Verify the URL and fix or redirect the page."
    ),
    "Duplicate title": (
        "Medium", 60, "Give distinct pages meaningful titles."
    ),
    "Noindex directive": (
        "High", 90, "Confirm whether search exclusion is intentional."
    ),
}

def normalize(url):
    url, _ = urldefrag(url.strip())
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return None
    return p._replace(path=p.path or "/", fragment="").geturl()

def add_issue(rows, url, kind, evidence):
    severity, score, fix = RULES[kind]
    rows.append({
        "Severity": severity,
        "Priority score": score,
        "Issue": kind,
        "URL": url,
        "Evidence": evidence,
        "Suggested correction": fix,
    })

def audit(start_url, max_pages, delay, timeout):
    start = normalize(start_url)
    if not start:
        raise ValueError("Enter a valid HTTP or HTTPS URL.")

    parsed = urlparse(start)
    host = parsed.netloc.lower()
    root = f"{parsed.scheme}://{parsed.netloc}"

    # Check the website's crawl policy first.
    robots_url = urljoin(root, "/robots.txt")
    response = requests.get(
        robots_url, headers=HEADERS, timeout=timeout
    )
    if response.status_code in (401, 403):
        raise ValueError("robots.txt is restricted. Crawl stopped.")

    robots = RobotFileParser()
    robots.parse(response.text.splitlines()
                 if response.status_code == 200 else [])

    if not robots.can_fetch(UA, start):
        raise ValueError("robots.txt disallows crawling this URL.")

    queue = deque([start])
    discovered = {start}
    pages, findings = [], []
    titles = {}

    while queue and len(pages) < max_pages:
        url = queue.popleft()

        if not robots.can_fetch(UA, url):
            continue

        time.sleep(delay)
        try:
            res = requests.get(
                url, headers=HEADERS, timeout=timeout,
                allow_redirects=True
            )
        except requests.RequestException as exc:
            add_issue(findings, url, "HTTP error", str(exc))
            continue

        if res.status_code >= 400:
            add_issue(
                findings, url, "HTTP error",
                f"HTTP status {res.status_code}"
            )
            continue

        if "text/html" not in res.headers.get("Content-Type", ""):
            continue

        soup = BeautifulSoup(res.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else ""

        desc_tag = soup.find(
            "meta", attrs={"name": "description"}
        )
        description = (
            desc_tag.get("content") or ""
        ).strip() if desc_tag else ""

        h1s = soup.find_all("h1")
        canonical = soup.find(
            "link", rel=lambda value:
            value and "canonical" in [
                str(x).lower() for x in
                (value if isinstance(value, list) else [value])
            ]
        )
        robots_meta = soup.find(
            "meta", attrs={"name": "robots"}
        )
        robots_content = (
            robots_meta.get("content") or ""
        ).lower() if robots_meta else ""

        images = soup.find_all("img")
        missing_alt = [
            img for img in images if not img.has_attr("alt")
        ]

        pages.append({
            "URL": url,
            "HTTP status": res.status_code,
            "Title": title,
            "Meta description": description,
            "H1 count": len(h1s),
            "Canonical": canonical.get("href", "")
                if canonical else "",
            "Images": len(images),
            "Images missing alt": len(missing_alt),
        })

        if title:
            titles.setdefault(title.casefold(), []).append(url)
        else:
            add_issue(findings, url, "Missing title",
                      "No non-empty title element found.")

        if not description:
            add_issue(
                findings, url, "Missing meta description",
                "No non-empty meta description found."
            )

        if not h1s:
            add_issue(findings, url, "Missing H1",
                      "No H1 heading found.")

        if not canonical:
            add_issue(findings, url, "Missing canonical",
                      "No canonical link element found.")

        if missing_alt:
            add_issue(
                findings, url, "Image missing alt",
                f"{len(missing_alt)} of {len(images)} images "
                "lack an alt attribute."
            )

        if "noindex" in robots_content:
            add_issue(
                findings, url, "Noindex directive",
                f"Meta robots content: {robots_content}"
            )

        # Discover links on the same hostname only.
        for link in soup.find_all("a", href=True):
            target = normalize(urljoin(res.url, link["href"]))
            if not target or urlparse(target).netloc.lower() != host:
                continue
            if target not in discovered and len(discovered) < max_pages * 5:
                if robots.can_fetch(UA, target):
                    discovered.add(target)
                    queue.append(target)

    for title, urls in titles.items():
        if len(urls) > 1:
            for url in urls:
                add_issue(
                    findings, url, "Duplicate title",
                    f"Same title found on {len(urls)} crawled pages."
                )

    return pd.DataFrame(pages), pd.DataFrame(findings)

with st.sidebar:
    st.header("Audit settings")
    website = st.text_input(
        "Website URL", "https://example.com/"
    )
    limit = st.slider("Maximum pages", 1, 30, 5)
    delay = st.slider(
        "Delay between requests (seconds)", 0.5, 3.0, 1.0
    )
    timeout = st.slider("Request timeout", 5, 20, 10)
    run = st.button("Run SEO audit", type="primary")

st.warning(
    "Audit only websites you own or have permission to assess. "
    "Respect robots.txt and site policies."
)

if run:
    try:
        with st.spinner("Analyzing website..."):
            pages_df, issues_df = audit(
                website, limit, delay, timeout
            )

        a, b, c = st.columns(3)
        a.metric("Pages analyzed", len(pages_df))
        b.metric("Total findings", len(issues_df))
        c.metric(
            "High priority",
            int((issues_df["Severity"] == "High").sum())
            if not issues_df.empty else 0
        )

        if not issues_df.empty:
            issues_df = issues_df.sort_values(
                "Priority score", ascending=False
            )
            st.subheader("Prioritized fix list")
            st.dataframe(
                issues_df, use_container_width=True,
                hide_index=True
            )
            st.download_button(
                "Download findings CSV",
                issues_df.to_csv(index=False).encode("utf-8"),
                "seo_findings.csv", "text/csv"
            )
        else:
            st.success("No findings detected by these checks.")

        st.subheader("Page inventory")
        st.dataframe(
            pages_df, use_container_width=True,
            hide_index=True
        )
        st.download_button(
            "Download pages CSV",
            pages_df.to_csv(index=False).encode("utf-8"),
            "seo_pages.csv", "text/csv"
        )

    except Exception as exc:
        st.error(f"Audit could not complete: {exc}")
