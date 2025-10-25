#!/usr/bin/env python3
"""
Resilient scraper for NewsTrace.

Usage:
  cd Backend
  python3 scrapper.py "The Hindu"

Behavior:
- Detects official site from outlet name (heuristics + search).
- Crawls site (archive, author indexes) to collect article URLs.
- Extracts authors, beats, titles, pubdates; normalizes and merges duplicates.
- Writes atomic data.json progressively so partial results can be returned on timeout.
"""
import os
import sys
import re
import time
import json
import tempfile
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote, parse_qs
import urllib.robotparser as robotparser

# Paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
data_file = os.path.join(project_root, 'data.json')
HEADERS = {'User-Agent': 'Mozilla/5.0 (NewsTraceBot/1.0)'}
OUTLET = sys.argv[1].strip() if len(sys.argv) > 1 else None

# Config
MAX_ARTICLE_URLS = 800
WRITE_PROGRESS_EVERY = 5  # write partial data every N authors found
REQUEST_TIMEOUT = 8
CRAWL_DELAY = 0.2

# ------------------------------
# Utilities
# ------------------------------
def _atomic_write_json(path, obj):
    try:
        dirn = os.path.dirname(path) or '.'
        fd, tmp = tempfile.mkstemp(dir=dirn, prefix='.tmp_data_', text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def normalize_name(name: str) -> str:
    if not name or not isinstance(name, str):
        return ''
    s = name.strip()
    s = re.sub(r'^(By[:\s]+)', '', s, flags=re.I)
    s = re.sub(r'[\u200b\u200c\u200d]', '', s)
    s = re.sub(r'[\.\,\/\(\)\[\]\*\"“”\'`]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) <= 1:
        return ''
    return s.title()

def _prefer_newer(existing_date: str, candidate_date: str) -> bool:
    if not candidate_date or candidate_date == 'Unknown':
        return False
    if not existing_date or existing_date == 'Unknown':
        return True
    def parse_iso(d):
        m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', d)
        if m:
            y, mn, dd = m.groups()
            try:
                return datetime.date(int(y), int(mn), int(dd))
            except Exception:
                return None
        return None
    try:
        cd = parse_iso(candidate_date)
        ed = parse_iso(existing_date)
        if cd and ed:
            return cd > ed
    except Exception:
        pass
    return len(candidate_date) > len(existing_date)

def allowed_by_robots(url, user_agent='NewsTraceBot'):
    try:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True

# ------------------------------
# Stage 0: website detection
# ------------------------------
def detect_website(query):
    if not query:
        return None
    headers = HEADERS
    name_clean = re.sub(r'[^A-Za-z0-9 ]+', '', query).strip().lower()
    tokens = name_clean.split()
    tlds = ['.com', '.co.uk', '.org', '.in', '.net', '.news', '.co']
    candidates = []
    if tokens:
        base = ''.join(tokens)
        dash = '-'.join(tokens)
        for b in (base, dash):
            for t in tlds:
                candidates.append(f'https://www.{b}{t}')
                candidates.append(f'https://{b}{t}')
    # quick heuristics
    for c in candidates:
        try:
            r = requests.get(c, headers=headers, timeout=5)
            if r.status_code == 200:
                p = urlparse(c)
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            continue
    # fallback: DuckDuckGo / Bing
    search_q = query.replace(' ', '+') + '+official+website'
    search_urls = [
        f"https://duckduckgo.com/html/?q={search_q}",
        f"https://www.bing.com/search?q={search_q}"
    ]
    for s_url in search_urls:
        try:
            r = requests.get(s_url, headers=headers, timeout=6)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if not href:
                    continue
                # uddg param or redirect wrappers
                if 'uddg=' in href or '/l/?' in href:
                    try:
                        qs = parse_qs(urlparse(href).query)
                        candidate = None
                        if 'uddg' in qs and qs['uddg']:
                            candidate = unquote(qs['uddg'][0])
                        else:
                            m = re.search(r'uddg=([^&]+)', href)
                            candidate = unquote(m.group(1)) if m else None
                        if candidate and candidate.startswith('http'):
                            p = urlparse(candidate)
                            if p.netloc:
                                return f"{p.scheme or 'https'}://{p.netloc}"
                    except Exception:
                        pass
                if href.startswith('http') and not any(x in href for x in ['duckduckgo.com','bing.com','google.com']):
                    p = urlparse(href)
                    if p.netloc:
                        return f"{p.scheme or 'https'}://{p.netloc}"
        except Exception:
            continue
        time.sleep(0.2)
    return None

# ------------------------------
# Extraction helpers
# ------------------------------
def extract_title(soup):
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find('h1')
    return h1.get_text(strip=True) if h1 else 'Unknown'

def extract_pub_date(soup):
    time_tag = soup.find('time')
    if time_tag and time_tag.has_attr('datetime'):
        return time_tag['datetime'].strip()
    for meta in soup.find_all('meta'):
        if meta.has_attr('http-equiv'):
            continue
        prop = (meta.get('property') or '').lower()
        name = (meta.get('name') or '').lower()
        if meta.get('content'):
            content = meta['content'].strip()
            if prop in ('article:published_time','article:published','og:published_time','og:updated_time') or \
               name in ('pubdate','publishdate','publication_date','date','article:published_time','sailthru.date'):
                return content
    txt = soup.get_text(" ", strip=True)[:2000]
    m = re.search(r'\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?', txt)
    if m:
        return m.group(0)
    return 'Unknown'

def extract_authors(soup):
    authors = set()
    for meta in soup.find_all('meta', attrs={'name':'author'}) + soup.find_all('meta', attrs={'property':'article:author'}):
        if meta.has_attr('content'):
            authors.add(meta['content'].strip())
    for a in soup.find_all('a', rel=re.compile(r'author', re.I)):
        text = a.get_text(strip=True)
        if text:
            authors.add(text)
    for tag in soup.find_all(attrs={'itemprop': re.compile(r'author|creator', re.I)}):
        t = tag.get_text(strip=True)
        if t: authors.add(t)
    for sel in soup.find_all(['span','a','p','div'], class_=re.compile(r'(author|byline|writer|journalist|reporter|contributor|by)', re.I)):
        text = sel.get_text(" ", strip=True)
        text = re.sub(r'^(By|Written by|Author|Reporter|Byline)\s*[:\-]?\s*','', text, flags=re.I)
        for a in re.split(r',| and | & |;|\n', text):
            if a.strip():
                authors.add(a.strip())
    cleaned = []
    for a in authors:
        s = re.sub(r'\s+', ' ', a).strip()
        if len(s) < 2:
            continue
        low = s.lower()
        if low in ('contributors','staff','editorial','team','s'):
            continue
        cleaned.append(s)
    if not cleaned:
        return ['Unknown']
    return cleaned

def normalize_beat(raw: str) -> str:
    if not raw:
        return 'Unknown'
    s = raw.strip().lower()
    s = re.sub(r'[\s\|/,&]+', ' ', s)
    s = re.sub(r'[^a-z0-9 ]+', '', s)
    mapping = {
        'breaking news': 'Breaking',
        'breaking world news': 'Breaking',
        'breaking news india': 'Breaking',
        'world news': 'World',
        'world': 'World',
        'politics': 'Politics',
        'business': 'Business',
        'economy': 'Business',
        'technology': 'Technology',
        'tech': 'Technology',
        'sport': 'Sports',
        'sports': 'Sports',
        'editorial': 'Editorial',
        'opinion': 'Opinion',
        'analysis': 'Analysis',
        'entertainment': 'Entertainment',
        'lifestyle': 'Lifestyle',
        'science': 'Science',
        'health': 'Health',
        'travel': 'Travel',
        'news': 'News'
    }
    for k, v in mapping.items():
        if k in s:
            return v
    token = s.split()[0] if s.split() else ''
    return token.capitalize() if token else 'Unknown'

def extract_section(soup, url=None):
    meta_checks = [
        ('property', 'article:section'),
        ('name', 'section'),
        ('itemprop', 'articleSection'),
        ('name', 'news_keywords'),
        ('property', 'article:tag'),
        ('name', 'keywords')
    ]
    for attr, val in meta_checks:
        tag = soup.find('meta', attrs={attr: val})
        if tag and tag.get('content'):
            return normalize_beat(tag['content'].split(',')[0].strip())
    for el in soup.find_all(True, class_=re.compile(r'(section|topic|category|breadcrumb|tag|tags|beat|kicker|section-name)', re.I)):
        text = el.get_text(separator=' ', strip=True)
        if text and len(text) < 60:
            low = text.lower()
            if low not in ('home',):
                return normalize_beat(text)
    crumbs = soup.select('.breadcrumb a, nav[aria-label*="breadcrumb"] a, .breadcrumbs a')
    for c in crumbs:
        t = c.get_text(strip=True)
        if t and t.lower() not in ('home', ''):
            return normalize_beat(t)
    ip = soup.find(attrs={'itemprop': 'articleSection'})
    if ip:
        t = ip.get_text(strip=True)
        if t: return normalize_beat(t)
    tag_el = soup.find(['a','span','div'], class_=re.compile(r'(tag|tags|topic|kicker|section)', re.I))
    if tag_el:
        t = tag_el.get_text(strip=True)
        if t: return normalize_beat(t)
    if url:
        parts = [p for p in urlparse(url).path.split('/') if p]
        if parts:
            beats = {'politics','business','sports','technology','tech','culture','science','opinion','health','environment','world','entertainment','arts','travel','education','finance','economy','lifestyle','sport','news'}
            for p in parts:
                token = p.lower().replace('-', ' ')
                if token in beats:
                    return normalize_beat(token)
            guess = parts[0].replace('-', ' ').title()
            if guess and guess.lower() not in ('article','articles','story','content','amp'):
                return normalize_beat(guess)
    return 'Unknown'

# ------------------------------
# Crawl & extract
# ------------------------------
def find_article_links(base_url):
    session = requests.Session()
    session.headers.update(HEADERS)
    domain = urlparse(base_url).netloc.lower()
    to_visit = [base_url]
    seen = set()
    article_links = set()
    seeds = ['', '/news', '/latest', '/world', '/articles', '/section', '/topics', '/author', '/authors', '/contributors', '/staff']
    for s in seeds:
        to_visit.append(urljoin(base_url, s))
    while to_visit and len(article_links) < MAX_ARTICLE_URLS:
        url = to_visit.pop(0)
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            if not allowed_by_robots(url):
                continue
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            # find article-like links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if not href:
                    continue
                full = urljoin(url, href)
                p = urlparse(full)
                if domain not in p.netloc.lower():
                    continue
                path = p.path.lower()
                if re.search(r'/\d{4}/\d{1,2}/\d{1,2}/', path) or any(x in path for x in ['/article','/news/','/story','/opinion','/feature','/analysis','/reports','/sport','/sports']):
                    article_links.add(full.split('?')[0])
                # enqueue author/profile/index pages for broader coverage
                if any(x in path for x in ['/author','/authors','/staff','/contributors','/profile']) or len(path.strip('/').split('/')) <= 3:
                    if full not in seen:
                        to_visit.append(full)
            time.sleep(CRAWL_DELAY)
        except Exception:
            continue
    return list(article_links)[:MAX_ARTICLE_URLS]

def extract_profiles(base_url, min_profiles=30):
    urls = find_article_links(base_url)
    profiles_map = {}
    session = requests.Session()
    session.headers.update(HEADERS)
    count_written = 0
    processed = 0
    for url in urls:
        if len(profiles_map) >= min_profiles:
            break
        try:
            if not allowed_by_robots(url):
                continue
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            authors = extract_authors(soup)
            title = extract_title(soup)
            pub_date = extract_pub_date(soup)
            section = extract_section(soup, url=url)
            section = normalize_beat(section)
            for author in authors:
                norm = normalize_name(author)
                if not norm:
                    continue
                key = norm.lower()
                entry = profiles_map.get(key)
                if not entry:
                    profiles_map[key] = {
                        'name': norm,
                        'beat_counts': {section: 1} if section else {},
                        'beat': section or 'Unknown',
                        'latest_article': title or 'Unknown',
                        'article_url': url,
                        'publication_date': pub_date or 'Unknown',
                        'articles_count': 1
                    }
                else:
                    entry['articles_count'] += 1
                    if section:
                        entry['beat_counts'][section] = entry['beat_counts'].get(section, 0) + 1
                    if _prefer_newer(entry.get('publication_date', 'Unknown'), pub_date):
                        entry['publication_date'] = pub_date
                        entry['latest_article'] = title
                        entry['article_url'] = url
            processed += 1
            # write periodic partial results
            if processed % WRITE_PROGRESS_EVERY == 0:
                profiles = _finalize_profiles(profiles_map)
                payload = {"outlet_name": OUTLET, "website": base_url, "profiles": profiles}
                _atomic_write_json(data_file, payload)
                count_written += 1
        except Exception:
            continue
    profiles = _finalize_profiles(profiles_map)
    return profiles

def _finalize_profiles(profiles_map):
    profiles = []
    blacklist = set(['contributors','staff','editorial','team','unknown','s'])
    for k, v in profiles_map.items():
        name_low = (v.get('name') or '').strip().lower()
        if not name_low or name_low in blacklist:
            continue
        if v.get('beat_counts'):
            best = max(v['beat_counts'].items(), key=lambda x: x[1])[0]
            v['beat'] = best or 'Unknown'
        v.pop('beat_counts', None)
        profiles.append({
            'name': v.get('name'),
            'beat': v.get('beat', 'Unknown'),
            'latest_article': v.get('latest_article', '') or 'Unknown',
            'article_url': v.get('article_url', ''),
            'publication_date': v.get('publication_date', 'Unknown'),
            'articles_count': v.get('articles_count', 0)
        })
    profiles.sort(key=lambda x: (-x.get('articles_count', 0), x.get('name', '')))
    return profiles[:max(30, len(profiles))]

# ------------------------------
# Main
# ------------------------------
def main():
    if not OUTLET:
        print("No outlet provided", file=sys.stderr)
        sys.exit(2)
    # write initial placeholder so backend can return correct partial result on immediate timeout
    initial = {
        "outlet_name": OUTLET,
        "website": "",
        "profiles": [],
        "_note": "scraper started - partial results may be returned if timeout occurs"
    }
    _atomic_write_json(data_file, initial)
    detected = detect_website(OUTLET)
    final_profiles = []
    if detected:
        final_profiles = extract_profiles(detected, min_profiles=30)
    payload = {
        "outlet_name": OUTLET,
        "website": detected or "",
        "profiles": final_profiles
    }
    _atomic_write_json(data_file, payload)
    # print a short summary for logs
    print(f"🔎 Searching for outlet: {OUTLET}")
    print(f"🌐 Detected website: {detected}")
    print(f"🧾 Profiles extracted: {len(final_profiles)}")
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except Exception as e:
        print("Scraper error:", str(e), file=sys.stderr)
        sys.exit(1)