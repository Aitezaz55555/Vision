"""
VISION AI - Browser Automation Module
Handles web navigation, queries on Google / YouTube, ChatGPT access,
and safe URL opening in the user's default Windows browser.
"""

import urllib.parse
import webbrowser
from typing import Tuple, Optional


KNOWN_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "chatgpt": "https://chatgpt.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "gmail": "https://mail.google.com",
    "maps": "https://maps.google.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "linkedin": "https://www.linkedin.com",
}


def sanitize_url(raw_url: str) -> Optional[str]:
    """
    Validates and sanitizes a URL before opening.
    Rejects dangerous schemes like javascript:, data:, file:, etc.
    """
    cleaned = raw_url.strip()
    if not cleaned:
        return None

    # Block dangerous schemes
    lowered = cleaned.lower()
    if lowered.startswith(("javascript:", "data:", "vbscript:", "file:", "powershell:")):
        return None

    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        cleaned = "https://" + cleaned

    try:
        parsed = urllib.parse.urlparse(cleaned)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return cleaned
    except Exception:
        pass
    return None


def open_website(site_or_url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Opens a website by natural name or URL.
    Returns (success: bool, spoken_reply: str, site_key: Optional[str]).
    """
    key = site_or_url.lower().strip().replace(" ", "")
    display = site_or_url.strip()

    # Check known website alias
    if key in KNOWN_WEBSITES:
        url = KNOWN_WEBSITES[key]
        webbrowser.open(url)
        name = key.replace("chatgpt", "ChatGPT").title()
        return True, f"Opening {name}.", key

    # Check if a domain like 'github.com' or standard URL
    target_url = sanitize_url(site_or_url)
    if target_url:
        webbrowser.open(target_url)
        return True, f"Opening website.", key

    return False, f"Sorry Sir, I could not open {display}.", None


def search_web(query: str, platform: str = "google") -> Tuple[bool, str]:
    """
    Performs a web search on Google or YouTube.
    """
    q = query.strip()
    if not q:
        return False, "What should I search for?"

    encoded = urllib.parse.quote(q)
    plat = platform.lower().strip()

    if plat in ("youtube", "yt"):
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        return True, f"Searching YouTube for {q}."
    else:
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        return True, f"Searching Google for {q}."
