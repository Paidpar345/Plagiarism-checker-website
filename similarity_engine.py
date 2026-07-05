import math
import re
from collections import Counter

STOP_WORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'al', 'y', 'o',
    'en', 'para', 'por', 'que', 'con', 'su', 'sus', 'es', 'son', 'lo', 'como', 'mas',
    'se', 'a', 'esta', 'este', 'estas', 'estos', 'ya', 'muy', 'pero', 'no', 'si',
    'the', 'a', 'an', 'of', 'to', 'in', 'is', 'are', 'and', 'or', 'for', 'on', 'with'
}


def clean_and_tokenize(text):
    if not text:
        return []
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = [word for word in text.split() if word and word not in STOP_WORDS]
    return tokens


def _vectorize(tokens):
    return Counter(tokens)


def cosine_similarity_tokens(tokens_a, tokens_b):
    if not tokens_a or not tokens_b:
        return 0.0

    vector_a = _vectorize(tokens_a)
    vector_b = _vectorize(tokens_b)

    intersection = set(vector_a.keys()) & set(vector_b.keys())
    dot_product = sum(vector_a[w] * vector_b[w] for w in intersection)

    magnitude_a = math.sqrt(sum(v ** 2 for v in vector_a.values()))
    magnitude_b = math.sqrt(sum(v ** 2 for v in vector_b.values()))

    if not magnitude_a or not magnitude_b:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def calculate_cosine_similarity(text_a, text_b):
    tokens_a = clean_and_tokenize(text_a)
    tokens_b = clean_and_tokenize(text_b)
    return round(cosine_similarity_tokens(tokens_a, tokens_b) * 100, 2)


def _split_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if len(s.strip()) > 20]


def calculate_similarity_report(text_a, text_b, top_n_matches=3):
    """Devuelve similitud global (coseno TF) mas las frases del documento
    original que mas se parecen a fragmentos del texto web (para citar)."""
    global_score = calculate_cosine_similarity(text_a, text_b)

    sentences_a = _split_sentences(text_a)
    sentences_b = _split_sentences(text_b)

    matches = []
    if sentences_a and sentences_b:
        sample_b = sentences_b[:80]
        for sa in sentences_a[:80]:
            tokens_sa = clean_and_tokenize(sa)
            if not tokens_sa:
                continue
            best_score = 0.0
            best_sentence_b = None
            for sb in sample_b:
                tokens_sb = clean_and_tokenize(sb)
                score = cosine_similarity_tokens(tokens_sa, tokens_sb)
                if score > best_score:
                    best_score = score
                    best_sentence_b = sb
            if best_score > 0.5:
                matches.append({
                    'frase_original': sa,
                    'frase_web': best_sentence_b,
                    'coincidencia': round(best_score * 100, 2)
                })

    matches.sort(key=lambda m: m['coincidencia'], reverse=True)

    return {
        'similitud': global_score,
        'frases_similares': matches[:top_n_matches]
    }