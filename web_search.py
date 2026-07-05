import os
import re
import random
import requests
import urllib.parse
from bs4 import BeautifulSoup
from similarity_engine import STOP_WORDS
from dotenv import load_dotenv

load_dotenv()

SCRAPEDO_TOKEN = os.environ.get("SCRAPEDO_TOKEN", "")
REQUEST_TIMEOUT = 20


def extract_smart_queries(text, num_queries=5, randomize=True):
    """Extrae frases de 5-10 palabras. Si randomize=True elige aleatoriamente
    entre las frases con contenido semantico relevante, tal y como pide el
    enunciado ('extract random phrases'); si no, usa las de mayor puntuacion."""
    if not text:
        return []

    sentences = re.split(r'[.\n]', text)
    candidate_phrases = []

    for sentence in sentences:
        words = [w for w in sentence.split() if w.strip()]
        if not (5 <= len(words) <= 10):
            for i in range(0, max(len(words) - 5, 0) + 1, 6):
                chunk = words[i:i + 8]
                if len(chunk) >= 5:
                    candidate_phrases.append(chunk)
        else:
            candidate_phrases.append(words)

    scored = []
    for words in candidate_phrases:
        meaningful = [w for w in words if re.sub(r'[^\w]', '', w.lower()) not in STOP_WORDS]
        score = len(meaningful)
        if score >= 4:
            scored.append((score, " ".join(words).strip()))

    if not scored:
        return [text[:100]] if text else []

    if randomize:
        weights = [s for s, _ in scored]
        pool = [p for _, p in scored]
        k = min(num_queries, len(pool))
        chosen = []
        weights_copy = weights[:]
        pool_copy = pool[:]
        for _ in range(k):
            total = sum(weights_copy)
            r = random.uniform(0, total)
            upto = 0
            for idx, w in enumerate(weights_copy):
                upto += w
                if upto >= r:
                    chosen.append(pool_copy.pop(idx))
                    weights_copy.pop(idx)
                    break
        return chosen

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:num_queries]]


def search_google(query, nb_results=5):
    """Usa Scrape.do para buscar en Google y devolver hasta nb_results URLs."""
    if not SCRAPEDO_TOKEN:
        print("ADVERTENCIA: SCRAPEDO_TOKEN no configurado.")
        return []

    url = "https://api.scrape.do/plugin/google/search"
    params = {
        "token": SCRAPEDO_TOKEN,
        "q": query,
        "hl": "es"
    }

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            organic = data.get("organic_results") or data.get("organic", [])
            return [r.get("url") or r.get("link") for r in organic[:nb_results] if r.get("url") or r.get("link")]
        print(f"Scrape.do status {response.status_code}: {response.text[:200]}")
        return []
    except Exception as e:
        print(f"Error en Scrape.do (search): {e}")
        return []


def scrape_and_clean_url(url):
    """Usa Scrape.do para descargar el HTML de una URL y devuelve solo el texto principal."""
    if not SCRAPEDO_TOKEN:
        print("ADVERTENCIA: SCRAPEDO_TOKEN no configurado.")
        return ""

    try:
        encoded_url = urllib.parse.quote(url, safe="")
        api_url = f"https://api.scrape.do/?token={SCRAPEDO_TOKEN}&url={encoded_url}"
        response = requests.get(api_url, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside',
                          'meta', 'noscript', 'form', 'button', 'iframe']):
            tag.decompose()

        main = soup.find('article') or soup.find('main') or soup.body
        if main is None:
            return ""

        text = main.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text[:50000]
    except Exception as e:
        print(f"Error raspando {url} con Scrape.do: {e}")
        return ""