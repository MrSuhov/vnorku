"""
Helper functions for detecting anti-bot blocks (Qrator, Cloudflare, etc.)
"""
import logging
from typing import Tuple, Optional
from selenium import webdriver

logger = logging.getLogger(__name__)


def check_if_blocked(driver: webdriver.Chrome, expected_url: str = None) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Check if the page is blocked by anti-bot systems
    
    Args:
        driver: Selenium WebDriver instance
        expected_url: Expected URL pattern (optional, for redirect detection)
    
    Returns:
        Tuple of (is_blocked, block_type, http_status)
        - is_blocked: True if blocked
        - block_type: 'qrator', 'cloudflare', 'captcha', 'rate_limit', 'forbidden', 'other'
        - http_status: HTTP status code (403, 429, 503, etc.) or None
    """
    try:
        current_url = driver.current_url
        page_source = driver.page_source[:2000].lower()  # First 2000 chars
        page_title = driver.title.lower()
        
        # Check for common block indicators
        block_indicators = {
            'qrator': [
                '403 error',
                'access is forbidden',
                'qrator',
                'guru meditation'
            ],
            'cloudflare': [
                'cloudflare',
                'checking your browser',
                'ddos protection',
                'cf-browser-verification'
            ],
            'captcha': [
                'captcha',
                'recaptcha',
                'hcaptcha',
                'verify you are human'
            ],
            'rate_limit': [
                '429',
                'too many requests',
                'rate limit',
                'slow down'
            ],
            'forbidden': [
                '403',
                'forbidden',
                'access denied'
            ]
        }
        
        # Detect block type
        for block_type, indicators in block_indicators.items():
            for indicator in indicators:
                if indicator in page_source or indicator in page_title:
                    # Try to extract HTTP status from page
                    http_status = _extract_http_status(page_source, page_title)
                    logger.warning(f"🚫 Block detected: {block_type} (status: {http_status})")
                    logger.warning(f"   URL: {current_url}")
                    return True, block_type, http_status
        
        # Check for unexpected redirects
        if expected_url and not _url_matches_pattern(current_url, expected_url):
            logger.warning(f"⚠️ Unexpected redirect detected")
            logger.warning(f"   Expected: {expected_url}")
            logger.warning(f"   Got: {current_url}")
            # This might be a soft block or regional redirect
            # Don't immediately fail, but log it
        
        return False, None, None
        
    except Exception as e:
        logger.error(f"❌ Error checking if blocked: {e}")
        return False, None, None


def _extract_http_status(page_source: str, page_title: str) -> Optional[int]:
    """
    Try to extract HTTP status code from page content
    """
    import re
    
    # Common patterns for HTTP status in error pages
    patterns = [
        r'http (\d{3})',
        r'(\d{3}) error',
        r'error (\d{3})',
        r'status[:\s]+(\d{3})'
    ]
    
    text = f"{page_source} {page_title}".lower()
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue
    
    return None


def _url_matches_pattern(current_url: str, expected_url: str) -> bool:
    """
    Check if current URL matches expected pattern
    Handles minor variations like https/http, trailing slashes, query params
    """
    import re
    from urllib.parse import urlparse
    
    current_parsed = urlparse(current_url.lower())
    expected_parsed = urlparse(expected_url.lower())
    
    # Compare domains
    if current_parsed.netloc != expected_parsed.netloc:
        return False
    
    # Compare paths (ignore trailing slashes)
    current_path = current_parsed.path.rstrip('/')
    expected_path = expected_parsed.path.rstrip('/')
    
    # Allow for minor path variations (like /search vs /search/)
    if current_path.startswith(expected_path) or expected_path.startswith(current_path):
        return True
    
    return False


def get_html_snippet(driver: webdriver.Chrome, max_length: int = 1000) -> str:
    """
    Get first N characters of page HTML for debugging
    """
    try:
        html = driver.page_source
        return html[:max_length] if html else ""
    except Exception as e:
        logger.error(f"❌ Error getting HTML snippet: {e}")
        return ""
