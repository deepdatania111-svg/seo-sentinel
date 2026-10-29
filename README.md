
# SEO Sentinel 

An SEO audit and fix prioritization tool built with Python,
Streamlit, Requests, BeautifulSoup, and Pandas.

## Features
- Crawl a limited number of website pages
- Check robots.txt before crawling
- Detect missing titles and meta descriptions
- Detect missing H1 headings and canonical tags
- Flag images missing alt attributes
- Detect duplicate page titles and noindex directives
- Prioritize findings with explainable scores
- Export findings and page inventory to CSV

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Responsible use

Only audit websites you own or have permission to assess.
Respect robots.txt and applicable website policies.

## Limitations

This is a lightweight crawler. It does not fully render
JavaScript pages or replace professional SEO platforms.
Priority scores are heuristics, not official Google scores.
Verify findings before changing a production website.
