"""
website_detector.py — Lightweight website detection for business leads.

Strategy:
1. Generate domain candidates from business name (multiple patterns)
2. DNS lookup (fast, no HTTP needed if DNS fails)
3. HTTP HEAD request to confirm the site actually loads
"""

import re
import socket
import urllib.request
import urllib.error
import time
from typing import Optional

COMMON_SUFFIXES = [
    r'\s+Inc\.?$', r'\s+LLC\.?$', r'\s+Co\.?$', r'\s+Company\.?$',
    r'\s+L\.?L\.?C\.?$', r'\s+Corp\.?$', r'\s+Corporation\.?$',
    r'\s+Services?$', r'\s+Group$', r'\s+Solutions$',
    r'\s+And\s+', r'\s+&\s+',
]

def normalize_name(name: str) -> str:
    """Clean business name down to its core domain-friendly form."""
    n = name.lower().strip()
    # Remove common suffixes
    for pat in COMMON_SUFFIXES:
        n = re.sub(pat, '', n).strip()
    # Remove special chars
    n = re.sub(r'[^a-z0-9\s]', '', n).strip()
    # Collapse spaces
    n = re.sub(r'\s+', '', n)
    return n


def generate_candidates(name: str) -> list[str]:
    """Generate likely domain names from a business name."""
    base = normalize_name(name)
    if not base:
        return []

    candidates = set()

    # Primary: just the name
    for tld in ['com', 'net', 'org', 'us']:
        candidates.add(f'{base}.{tld}')

    # With "the" prefix (common for small biz)
    candidates.add(f'the{base}.com')

    # Full original name (non-normalized, stripped)
    orig = name.lower().strip()
    orig_clean = re.sub(r'[^a-z0-9\s]', '', orig)
    orig_compact = re.sub(r'\s+', '', orig_clean)
    if orig_compact != base and len(orig_compact) > 3:
        candidates.add(f'{orig_compact}.com')

    # Handle hyphenated variants
    spaced = re.sub(r'\s+', '-', orig_clean.strip())
    if spaced and spaced != base and '-' in spaced:
        candidates.add(f'{spaced}.com')

    return list(candidates)


def dns_resolves(domain: str, timeout: float = 1.0) -> bool:
    """Quick DNS check — does the domain resolve to an IP?"""
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(domain)
        return True
    except (socket.gaierror, OSError):
        return False


def http_responds(domain: str, timeout: float = 3.0) -> Optional[str]:
    """Check if the domain actually serves a real page. Returns final URL or None."""
    for scheme in ['https', 'http']:
        url = f'{scheme}://{domain}'
        try:
            req = urllib.request.Request(
                url,
                method='HEAD',
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; PipelineBot/1.0)',
                    'Accept': 'text/html,application/xhtml+xml',
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                # Accept 2xx and 3xx (redirects mean the site exists)
                if 200 <= status < 400:
                    return resp.url  # final URL after redirects
        except urllib.error.HTTPError as e:
            if 200 <= e.code < 400:
                return url
        except Exception:
            continue
    return None


def detect_website(name: str, city: str = '', delay: float = 0.0) -> Optional[str]:
    """
    Full detection pipeline for a single business.
    
    Returns the confirmed website URL or None.
    
    The pipeline:
      1. Generate domain candidates from business name
      2. DNS check each candidate (fast — stops on first hit)
      3. HTTP HEAD check on the DNS-hit (confirms real site)
    
    With a small delay between candidates to be polite.
    """
    if not name:
        return None

    candidates = generate_candidates(name)
    
    # Also try city-specific: namecity.com, cityname.com
    if city:
        city_clean = normalize_name(city)
        base = normalize_name(name)
        if base and city_clean:
            candidates.append(f'{base}{city_clean}.com')
            candidates.append(f'{city_clean}{base}.com')

    checked = set()
    for domain in candidates:
        if domain in checked:
            continue
        checked.add(domain)

        if delay:
            time.sleep(delay)

        # Step 1: DNS check (fast)
        if not dns_resolves(domain):
            continue

        # Step 2: HTTP check (confirms it's a real site)
        url = http_responds(domain)
        if url:
            return url

    return None


if __name__ == '__main__':
    # Quick test
    tests = [
        "Christy Custom Masonry Inc",
        "RR Plumbing Roto-Rooter",
        "Smith Plumbing",
        "Joe's Electric",
    ]
    for t in tests:
        result = detect_website(t, delay=0)
        print(f'{t:40s} → {result or "NOT FOUND"}')
