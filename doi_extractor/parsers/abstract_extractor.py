"""Abstract extraction module - Web scraping for journal abstracts by DOI.
Supports both HTTP requests and Selenium for Cloudflare-protected sites."""
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import random
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Request headers to simulate browser
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Selenium availability flag
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed, browser automation unavailable")


def get_selenium_driver():
    """Create and return a Selenium Chrome driver"""
    if not SELENIUM_AVAILABLE:
        return None
    
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.set_page_load_timeout(60)
    return driver


def get_doi_redirect_url(doi: str) -> Optional[str]:
    """Get the redirect URL from DOI"""
    url = f"https://doi.org/{doi}"
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=15)
        logger.debug(f"DOI {doi} redirected to: {response.url}")
        return response.url
    except Exception as e:
        logger.error(f"Failed to resolve DOI {doi}: {e}")
        return None


def is_cloudflare_protected(soup: BeautifulSoup) -> bool:
    """Check if page is protected by Cloudflare"""
    title = soup.find('title')
    if title:
        title_text = title.get_text()
        return any(phrase in title_text for phrase in ['Just a moment', 'Validate User', 'Please wait', '请稍候'])
    return False


# ==================== Nature/Springer ====================

def get_abstract_nature(url: str) -> str:
    """Fetch abstract from Nature/Springer"""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 403:
            logger.warning("Nature: 403 Forbidden, trying Selenium...")
            return get_abstract_nature_selenium(url)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if is_cloudflare_protected(soup):
            logger.warning("Nature: Cloudflare detected, trying Selenium...")
            return get_abstract_nature_selenium(url)
        
        selectors = [
            "div.c-article-section__content",
            "div[data-test='abstract-section']",
            "section[data-title='Abstract'] div",
            "div.abstract-content",
            "#Abs1-content",
        ]
        
        for selector in selectors:
            section = soup.select_one(selector)
            if section:
                text = section.get_text(strip=True)
                if text and len(text) > 50:
                    return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting Nature abstract: {e}")
        return f"Error: {e}"


def get_abstract_nature_selenium(url: str) -> str:
    """Selenium fallback for Nature"""
    if not SELENIUM_AVAILABLE:
        return "Selenium not available"
    
    driver = None
    try:
        logger.info("🤖 Starting Selenium for Nature...")
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(5)
        
        # Check if still on Cloudflare page
        if 'Just a moment' in driver.title:
            time.sleep(10)
        
        selectors = [
            "div.c-article-section__content",
            "div[data-test='abstract-section']",
            "#Abs1-content",
        ]
        
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text and len(text) > 50:
                    logger.info(f"✅ Selenium found Nature abstract")
                    return text
            except:
                continue
        
        return "Abstract not found with Selenium"
    except Exception as e:
        logger.error(f"Selenium error for Nature: {e}")
        return f"Selenium error: {e}"
    finally:
        if driver:
            driver.quit()


# ==================== Elsevier ====================

def get_abstract_elsevier(url: str) -> str:
    """Fetch abstract from Elsevier/ScienceDirect"""
    try:
        # Convert linkinghub URLs
        if "linkinghub.elsevier.com/retrieve/pii/" in url:
            import re
            pii_match = re.search(r'/retrieve/pii/([A-Z0-9]+)', url)
            if pii_match:
                pii = pii_match.group(1)
                url = f"https://www.sciencedirect.com/science/article/pii/{pii}"
        
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 403:
            logger.warning("Elsevier: 403 Forbidden, trying Selenium...")
            return get_abstract_elsevier_selenium(url)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if is_cloudflare_protected(soup):
            logger.warning("Elsevier: Cloudflare detected, trying Selenium...")
            return get_abstract_elsevier_selenium(url)
        
        # Try meta tags
        meta_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            'meta[name="citation_abstract"]',
        ]
        
        for selector in meta_selectors:
            meta = soup.select_one(selector)
            if meta:
                content = meta.get('content', '').strip()
                if content and len(content) > 50:
                    return content
        
        # Try content selectors
        selectors = [
            "#sp0010", "#ab010", ".abstract.author", ".abstract",
        ]
        
        for selector in selectors:
            abstract = soup.select_one(selector)
            if abstract:
                text = abstract.get_text(strip=True)
                if text.startswith("Abstract"):
                    text = text[8:].strip()
                if text.startswith(":"):
                    text = text[1:].strip()
                if text and len(text) > 50:
                    return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting Elsevier abstract: {e}")
        return f"Error: {e}"


def get_abstract_elsevier_selenium(url: str) -> str:
    """Selenium fallback for Elsevier"""
    if not SELENIUM_AVAILABLE:
        return "Selenium not available"
    
    driver = None
    try:
        logger.info("🤖 Starting Selenium for Elsevier...")
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(8)
        
        selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            "#sp0010", ".abstract-text", ".abstract.author"
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('meta'):
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    content = element.get_attribute('content')
                    if content and len(content) > 50:
                        return content
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and len(text) > 50:
                        return text
            except:
                continue
        
        return "Abstract not found with Selenium"
    except Exception as e:
        logger.error(f"Selenium error for Elsevier: {e}")
        return f"Selenium error: {e}"
    finally:
        if driver:
            driver.quit()


# ==================== IEEE ====================

def get_abstract_ieee(url: str) -> str:
    """Fetch abstract from IEEE"""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 403:
            logger.warning("IEEE: 403 Forbidden, trying Selenium...")
            return get_abstract_ieee_selenium(url)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if is_cloudflare_protected(soup):
            logger.warning("IEEE: Cloudflare detected, trying Selenium...")
            return get_abstract_ieee_selenium(url)
        
        meta_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            'meta[name="citation_abstract"]',
        ]
        
        for selector in meta_selectors:
            meta = soup.select_one(selector)
            if meta:
                content = meta.get('content', '').strip()
                if content and len(content) > 100:
                    return content
        
        selectors = [
            ".abstract-text div", ".document-abstract .abstract-text", ".abstract-text",
        ]
        
        for selector in selectors:
            abstract = soup.select_one(selector)
            if abstract:
                text = abstract.get_text(strip=True)
                if text.startswith("Abstract:"):
                    text = text[9:].strip()
                if text and len(text) > 50:
                    return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting IEEE abstract: {e}")
        return f"Error: {e}"


def get_abstract_ieee_selenium(url: str) -> str:
    """Selenium fallback for IEEE"""
    if not SELENIUM_AVAILABLE:
        return "Selenium not available"
    
    driver = None
    try:
        logger.info("🤖 Starting Selenium for IEEE...")
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(5)
        
        selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            ".abstract-text", ".document-abstract"
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('meta'):
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    content = element.get_attribute('content')
                    if content and len(content) > 50:
                        return content
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and len(text) > 50:
                        return text
            except:
                continue
        
        return "Abstract not found with Selenium"
    except Exception as e:
        logger.error(f"Selenium error for IEEE: {e}")
        return f"Selenium error: {e}"
    finally:
        if driver:
            driver.quit()


# ==================== Wiley ====================

def get_abstract_wiley(url: str) -> str:
    """Fetch abstract from Wiley"""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 403:
            logger.warning("Wiley: 403 Forbidden, trying Selenium...")
            return get_abstract_wiley_selenium(url)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if is_cloudflare_protected(soup):
            logger.warning("Wiley: Cloudflare detected, trying Selenium...")
            return get_abstract_wiley_selenium(url)
        
        selectors = [
            "div.article-section__content",
            "section.article-section--abstract div",
            "div[class*='abstract']",
            ".abstract-group div",
            "meta[property='og:description']",
            "meta[name='description']",
        ]
        
        for selector in selectors:
            if selector.startswith("meta"):
                meta = soup.select_one(selector)
                if meta:
                    content = meta.get('content', '').strip()
                    if content and len(content) > 50:
                        return content
            else:
                abstract = soup.select_one(selector)
                if abstract:
                    text = abstract.get_text(strip=True)
                    if text and len(text) > 50:
                        return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting Wiley abstract: {e}")
        return f"Error: {e}"


def get_abstract_wiley_selenium(url: str) -> str:
    """Selenium fallback for Wiley"""
    if not SELENIUM_AVAILABLE:
        return "Selenium not available"
    
    driver = None
    try:
        logger.info("🤖 Starting Selenium for Wiley...")
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(8)
        
        selectors = [
            "div.article-section__content",
            "section.article-section--abstract",
            "div[class*='abstract']",
            "meta[property='og:description']",
            "meta[name='description']",
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('meta'):
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    content = element.get_attribute('content')
                    if content and len(content) > 50:
                        return content
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and len(text) > 50:
                        return text
            except:
                continue
        
        return "Abstract not found with Selenium"
    except Exception as e:
        logger.error(f"Selenium error for Wiley: {e}")
        return f"Selenium error: {e}"
    finally:
        if driver:
            driver.quit()


# ==================== ACS ====================

def get_abstract_acs(url: str) -> str:
    """Fetch abstract from ACS (American Chemical Society)"""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 403:
            logger.warning("ACS: 403 Forbidden, trying Selenium...")
            return get_abstract_acs_selenium(url)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if is_cloudflare_protected(soup):
            logger.warning("ACS: Cloudflare detected, trying Selenium...")
            return get_abstract_acs_selenium(url)
        
        selectors = [
            "meta[property='og:description']",
            "meta[name='description']",
            "p.articleBody_abstractText",
            "div.hlFld-Abstract",
            "div.article_abstract-content",
        ]
        
        for selector in selectors:
            if selector.startswith("meta"):
                meta = soup.select_one(selector)
                if meta:
                    content = meta.get('content', '').strip()
                    if content and len(content) > 50:
                        return content
            else:
                abstract = soup.select_one(selector)
                if abstract:
                    text = abstract.get_text(strip=True)
                    if text and len(text) > 50:
                        return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting ACS abstract: {e}")
        return f"Error: {e}"


def get_abstract_acs_selenium(url: str) -> str:
    """Selenium fallback for ACS"""
    if not SELENIUM_AVAILABLE:
        return "Selenium not available"
    
    driver = None
    try:
        logger.info("🤖 Starting Selenium for ACS...")
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(10)
        
        if 'Just a moment' in driver.title:
            time.sleep(15)
        
        selectors = [
            "meta[property='og:description']",
            "meta[name='description']",
            "p.articleBody_abstractText",
            "div.hlFld-Abstract",
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('meta'):
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    content = element.get_attribute('content')
                    if content and len(content) > 50:
                        return content
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and len(text) > 50:
                        return text
            except:
                continue
        
        return "Abstract not found with Selenium"
    except Exception as e:
        logger.error(f"Selenium error for ACS: {e}")
        return f"Selenium error: {e}"
    finally:
        if driver:
            driver.quit()


# ==================== OUP ====================

def get_abstract_oup(url: str) -> str:
    """Fetch abstract from Oxford University Press"""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 403:
            logger.warning("OUP: 403 Forbidden, trying Selenium...")
            return get_abstract_oup_selenium(url)
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if is_cloudflare_protected(soup):
            logger.warning("OUP: Cloudflare detected, trying Selenium...")
            return get_abstract_oup_selenium(url)
        
        selectors = [
            "section.abstract",
            "div.abstract",
            "div[class*='abstract']",
            ".abstract-content",
            "meta[property='og:description']",
            "meta[name='description']",
        ]
        
        for selector in selectors:
            if selector.startswith("meta"):
                meta = soup.select_one(selector)
                if meta:
                    content = meta.get('content', '').strip()
                    if content and len(content) > 50:
                        return content
            else:
                abstract = soup.select_one(selector)
                if abstract:
                    text = abstract.get_text(strip=True)
                    if text and len(text) > 50:
                        return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting OUP abstract: {e}")
        return f"Error: {e}"


def get_abstract_oup_selenium(url: str) -> str:
    """Selenium fallback for OUP"""
    if not SELENIUM_AVAILABLE:
        return "Selenium not available"
    
    driver = None
    try:
        logger.info("🤖 Starting Selenium for OUP...")
        driver = get_selenium_driver()
        driver.get(url)
        time.sleep(8)
        
        if 'Just a moment' in driver.title:
            time.sleep(10)
        
        selectors = [
            "section.abstract",
            "div.abstract",
            "div[class*='abstract']",
            "meta[property='og:description']",
            "meta[name='description']",
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('meta'):
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    content = element.get_attribute('content')
                    if content and len(content) > 50:
                        return content
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and len(text) > 50:
                        return text
            except:
                continue
        
        return "Abstract not found with Selenium"
    except Exception as e:
        logger.error(f"Selenium error for OUP: {e}")
        return f"Selenium error: {e}"
    finally:
        if driver:
            driver.quit()


# ==================== Generic ====================

def get_abstract_generic(url: str) -> str:
    """Generic abstract extraction for unknown publishers"""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        selectors = [
            "div[class*='abstract']",
            "section[class*='abstract']",
            "div[id*='abstract']",
            ".summary",
            ".description",
            "meta[name='description']",
        ]
        
        for selector in selectors:
            if selector.startswith("meta"):
                meta = soup.select_one(selector)
                if meta and meta.get('content'):
                    content = meta.get('content').strip()
                    if len(content) > 50:
                        return content
            else:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 50:
                        return text
        
        return "Abstract not found."
    except Exception as e:
        logger.error(f"Error extracting generic abstract: {e}")
        return f"Error: {e}"


# ==================== Main Entry Point ====================

def fetch_abstract_by_doi(doi: str) -> Tuple[Optional[str], str]:
    """
    Fetch abstract by DOI - automatically detect publisher and extract abstract
    Falls back to Selenium for Cloudflare-protected sites
    """
    url = get_doi_redirect_url(doi)
    if not url:
        return None, "Failed to resolve DOI"
    
    domain = urlparse(url).netloc.lower()
    logger.info(f"Processing DOI {doi} from domain: {domain}")
    
    # Add delay to be polite
    time.sleep(random.uniform(0.5, 2.0))
    
    # Route to appropriate parser
    if 'nature.com' in domain or 'springer.com' in domain:
        abstract = get_abstract_nature(url)
    elif 'sciencedirect.com' in domain or 'elsevier.com' in domain:
        abstract = get_abstract_elsevier(url)
    elif 'ieeexplore.ieee.org' in domain or 'ieee.org' in domain:
        abstract = get_abstract_ieee(url)
    elif 'wiley.com' in domain or 'onlinelibrary.wiley.com' in domain:
        abstract = get_abstract_wiley(url)
    elif 'acs.org' in domain or 'pubs.acs.org' in domain:
        abstract = get_abstract_acs(url)
    elif 'oup.com' in domain:
        abstract = get_abstract_oup(url)
    else:
        logger.warning(f"Unknown domain: {domain}, using generic parser")
        abstract = get_abstract_generic(url)
    
    return url, abstract
