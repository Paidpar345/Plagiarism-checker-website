import os
import re
import random
import time
import logging
import requests
import urllib.parse
from bs4 import BeautifulSoup
from similarity_engine import STOP_WORDS
from cache_utils import cache_get, cache_set
from dotenv import load_dotenv
import socket
import ipaddress

load_dotenv()

logger = logging.getLogger("plagiarism_checker")

SCRAPEDO_TOKEN = os.environ.get("SCRAPEDO_TOKEN", "")
REQUEST_TIMEOUT = 20
FAILED_TTL = 60 * 30  # FIX (seguridad/implementacion): ahora si se usa.

BLOCKED_DOMAINS = {
    "pinterest.com", "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com",
}

LOW_QUALITY_PATH_PATTERNS = re.compile(
    r"/(login|signin|signup|cart|checkout|search\?|tag/|category/page)", re.IGNORECASE
)


_PRIVATE_HOST_RE = re.compile(
    r"^(localhost|127\.|10\.|172\.(1[6-9]|2\d|3[0-1])\.|192\.168\.|0\.0\.0\.0|169\.254\.|::1)"
)


def _domain_of(url):
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
        return netloc.replace("www.", "")
    except Exception:
        return ""


def is_domain_allowed(url):
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
        
    if parsed.scheme not in ("http", "https"):
        return False
        
    host = parsed.hostname or ""
    if not host:
        return False
        
    
    try:
        ip = socket.gethostbyname(host)
        if ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback:
            logger.warning("Intento SSRF bloqueado hacia IP interna: %s", ip)
            return False
    except Exception:
        
        return False

    domain = _domain_of(url)
    if any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS):
        return False
        
    if LOW_QUALITY_PATH_PATTERNS.search(url):
        return False
        
    return True


def is_content_quality_ok(text, min_words=60, max_ratio_short_lines=0.6):
    if not text:
        return False
    words = text.split()
    if len(words) < min_words:
        return False
    lines = [l for l in text.split(". ") if l.strip()]
    if not lines:
        return False
    short_lines = sum(1 for l in lines if len(l.split()) < 4)
    if len(lines) > 5 and (short_lines / len(lines)) > max_ratio_short_lines:
        return False
    return True


def extract_smart_queries(text, num_queries=5, randomize=True):
    if not text:
        return []

   
    text_limpio = re.sub(r'(?<![.!?/:])\s*\n+\s*', ' ', text)
    
    
    sentences = re.split(r"[.!?\n]+", text_limpio)
    candidate_phrases = []

    for sentence in sentences:
        words = [w for w in sentence.split() if w.strip()]
        
        # NUEVO: 3. Descartar oraciones basura (índices cortos, código fuente, puros números)
        letras = sum(c.isalpha() for c in sentence)
        if letras < 25 or len(words) < 6:
            continue
            
        if not (6 <= len(words) <= 12):
            for i in range(0, max(len(words) - 6, 0) + 1, 6):
                chunk = words[i:i + 10]
                if len(chunk) >= 6:
                    candidate_phrases.append(chunk)
        else:
            candidate_phrases.append(words)

    scored = []
    for words in candidate_phrases:
        # Calcular el valor de la frase ignorando las STOP_WORDS
        meaningful = [w for w in words if re.sub(r"[^\w]", "", w.lower()) not in STOP_WORDS and not w.isnumeric()]
        score = len(meaningful)
        # Solo queremos frases que tengan al menos 4 palabras clave reales
        if score >= 4:
            scored.append((score, " ".join(words).strip()))

    if not scored:
        return []

    if randomize:
        weights = [s for s, _ in scored]
        pool = [p for _, p in scored]
        k = min(num_queries, len(pool))
        chosen = []
        for _ in range(k):
            total = sum(weights)
            r = random.uniform(0, total)
            upto = 0
            for idx, w in enumerate(weights):
                upto += w
                if upto >= r:
                    chosen.append(pool.pop(idx))
                    weights.pop(idx)
                    break
        return chosen

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:num_queries]]


def search_google(query, nb_results=5):
    if not SCRAPEDO_TOKEN:
        logger.error("SCRAPEDO_TOKEN no configurado; no se puede buscar en Google.")
        return []

    cache_key = f"search::{query}::{nb_results}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = "https://api.scrape.do/plugin/google/search"
    params = {"token": SCRAPEDO_TOKEN, "q": query, "hl": "es"}

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            organic = data.get("organic_results") or data.get("organic", [])
            urls = [r.get("url") or r.get("link") for r in organic if r.get("url") or r.get("link")]
            urls = [u for u in urls if is_domain_allowed(u)][:nb_results]

            ttl = 60 * 60 * 6 if urls else FAILED_TTL
            cache_set(cache_key, urls, ttl=ttl)
            return urls
        logger.warning("search_google: status %s para query %r", response.status_code, query)
        cache_set(cache_key, [], ttl=FAILED_TTL)
        return []
    except Exception as e:
        logger.warning("search_google: excepcion para query %r: %s", query, e)
        return []


def scrape_and_clean_url(url):
    if not SCRAPEDO_TOKEN:
        logger.error("SCRAPEDO_TOKEN no configurado; no se puede raspar %s", url)
        return ""

    if not is_domain_allowed(url):
        return ""

    cache_key = f"scrape::{url}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        encoded_url = urllib.parse.quote(url, safe="")
        api_url = f"https://api.scrape.do/?token={SCRAPEDO_TOKEN}&url={encoded_url}"
        response = requests.get(api_url, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            logger.warning("scrape_and_clean_url: status %s para %s", response.status_code, url)
            cache_set(cache_key, "", ttl=FAILED_TTL)
            return ""

       
        raw_html = response.text
        if len(raw_html) > 5_000_000:
            raw_html = raw_html[:5_000_000]

        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav", "aside",
                          "meta", "noscript", "form", "button", "iframe"]):
            tag.decompose()

        main = soup.find("article") or soup.find("main") or soup.body
        if main is None:
            cache_set(cache_key, "", ttl=FAILED_TTL)
            return ""

        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        text = text[:50000]

        if not is_content_quality_ok(text):
            cache_set(cache_key, "", ttl=FAILED_TTL)
            return ""

        cache_set(cache_key, text, ttl=60 * 60 * 24)
        return text
    except Exception as e:
        logger.warning("scrape_and_clean_url: excepcion para %s: %s", url, e)
        return ""