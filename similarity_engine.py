import math
import re
import hashlib
import unicodedata
from collections import Counter

# NUEVAS IMPORTACIONES PARA NLP
import torch
from sentence_transformers import SentenceTransformer, util

# Carga del modelo NLP en memoria (se hace una sola vez al iniciar el worker).
# Usamos un modelo multilingüe ligero y muy rápido.
nlp_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

STOP_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "y", "o",
    "en", "para", "por", "que", "con", "su", "sus", "es", "son", "lo", "como", "mas",
    "se", "a", "esta", "este", "estas", "estos", "ya", "muy", "pero", "no", "si",
    "the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "for", "on", "with"
}


def _strip_accents(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )


def clean_and_tokenize(text):
    if not text:
        return []
    text = _strip_accents(text.lower())
    text = re.sub(r"[^\w\s]", " ", text)
    return [w for w in text.split() if w and w not in STOP_WORDS]


def get_ngrams(tokens, n):
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _vectorize(tokens):
    return Counter(tokens)


def cosine_raw(vector_a, vector_b):
    intersection = set(vector_a.keys()) & set(vector_b.keys())
    dot_product = sum(vector_a[w] * vector_b[w] for w in intersection)
    mag_a = math.sqrt(sum(v ** 2 for v in vector_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vector_b.values()))
    if not mag_a or not mag_b:
        return 0.0
    return dot_product / (mag_a * mag_b)


def compute_idf(corpus_token_lists):
    n_docs = len(corpus_token_lists)
    if n_docs == 0:
        return {}
    df = Counter()
    for tokens in corpus_token_lists:
        for w in set(tokens):
            df[w] += 1
    return {w: math.log((n_docs + 1) / (c + 1)) + 1 for w, c in df.items()}


def tfidf_vector(tokens, idf):
    tf = Counter(tokens)
    return {w: freq * idf.get(w, 1.0) for w, freq in tf.items()}


def tfidf_cosine_similarity(text_a, text_b, idf=None):
    tokens_a = clean_and_tokenize(text_a)
    tokens_b = clean_and_tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    if idf:
        vec_a = tfidf_vector(tokens_a, idf)
        vec_b = tfidf_vector(tokens_b, idf)
    else:
        vec_a = _vectorize(tokens_a)
        vec_b = _vectorize(tokens_b)
    return round(cosine_raw(vec_a, vec_b) * 100, 2)


def ngram_similarity(text_a, text_b, n=4):
    tokens_a = clean_and_tokenize(text_a)
    tokens_b = clean_and_tokenize(text_b)
    ngrams_a = set(get_ngrams(tokens_a, n))
    ngrams_b = set(get_ngrams(tokens_b, n))
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = ngrams_a & ngrams_b
    union = ngrams_a | ngrams_b
    return round((len(intersection) / len(union)) * 100, 2) if union else 0.0


def shingle_fingerprint(text, k=8):
    tokens = clean_and_tokenize(text)
    shingles = get_ngrams(tokens, k)
    return {hashlib.md5(s.encode("utf-8")).hexdigest() for s in shingles}


def _adaptive_shingle_size(text_a, text_b, base_k=8, min_k=4):
    len_a = len(clean_and_tokenize(text_a))
    len_b = len(clean_and_tokenize(text_b))
    shortest = min(len_a, len_b)
    if shortest < 40:
        return min_k
    if shortest < 120:
        return min_k + 2
    return base_k


def shingle_overlap_ratio(text_a, text_b, k=None):
    if k is None:
        k = _adaptive_shingle_size(text_a, text_b)
    fp_a = shingle_fingerprint(text_a, k)
    fp_b = shingle_fingerprint(text_b, k)
    if not fp_a or not fp_b:
        return 0.0
    intersection = fp_a & fp_b
    smaller = min(len(fp_a), len(fp_b))
    return round((len(intersection) / smaller) * 100, 2) if smaller else 0.0


def semantic_similarity(text_a, text_b):
    """Calcula la similitud de significado entre dos textos usando Inteligencia Artificial."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    
    # El modelo convierte los textos en vectores (embeddings)
    embedding_a = nlp_model.encode(text_a, convert_to_tensor=True)
    embedding_b = nlp_model.encode(text_b, convert_to_tensor=True)
    
    # Comparamos los vectores usando Similitud Coseno
    cosine_score = util.cos_sim(embedding_a, embedding_b)
    
    # Extraemos el valor y lo convertimos a porcentaje
    return round(cosine_score.item() * 100, 2)


def _split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 20]


ALGORITHM_CHOICES = {
    "combinado": "Combinado (IA Semántica + TF-IDF + N-gramas + Shingling)",
    "tfidf": "Solo TF-IDF (similitud tematica)",
    "ngramas": "Solo N-gramas (deteccion de parafraseo)",
    "shingling": "Solo Shingling (copia exacta / fingerprinting)",
}


def calculate_similarity_report(text_a, text_b, idf=None, top_n_matches=3, algoritmo="combinado"):
    """
    Calcula la similitud integrando IA semántica para detectar paráfrasis profunda
    y engaños por sinónimos o traducciones.
    """
    tfidf_score = tfidf_cosine_similarity(text_a, text_b, idf=idf)
    ngram_score = ngram_similarity(text_a, text_b, n=4)
    shingle_score = shingle_overlap_ratio(text_a, text_b)
    
    # Calculamos la similitud semántica general
    semantic_score = semantic_similarity(text_a, text_b)

    if algoritmo == "tfidf":
        combined_score = tfidf_score
    elif algoritmo == "ngramas":
        combined_score = ngram_score
    elif algoritmo == "shingling":
        combined_score = shingle_score
    else:
        # Ponderación del algoritmo combinado:
        # IA Semántica (40%), N-gramas (25%), Shingling (20%), TF-IDF (15%)
        combined_score = round(
            (semantic_score * 0.40) + (tfidf_score * 0.15) + (ngram_score * 0.25) + (shingle_score * 0.20), 2
        )

    sentences_a = _split_sentences(text_a)
    sentences_b = _split_sentences(text_b)

    matches = []
    if sentences_a and sentences_b:
        sample_b = sentences_b[:80]
        # Codificamos todas las frases de la web de golpe por eficiencia de la CPU/GPU
        embeddings_b = nlp_model.encode(sample_b, convert_to_tensor=True)
        
        for sa in sentences_a[:80]:
            tokens_sa = clean_and_tokenize(sa)
            if not tokens_sa:
                continue
            
            # Codificamos la frase del documento evaluado
            emb_a = nlp_model.encode(sa, convert_to_tensor=True)
            
            # Comparamos la frase del usuario contra TODAS las de la web de una sola vez
            cos_scores = util.cos_sim(emb_a, embeddings_b)[0]
            
            # Obtenemos el mejor resultado
            best_idx = torch.argmax(cos_scores).item()
            best_score = cos_scores[best_idx].item()
            
            # Si el significado coincide en más de un 75%, se marca como plagio probable
            if best_score > 0.75:
                matches.append({
                    "frase_original": sa,
                    "frase_web": sample_b[best_idx],
                    "coincidencia": round(best_score * 100, 2)
                })

    matches.sort(key=lambda m: m["coincidencia"], reverse=True)

    return {
        "similitud": combined_score,
        "similitud_tfidf": tfidf_score,
        "similitud_ngramas": ngram_score,
        "similitud_shingling": shingle_score,
        "similitud_semantica": semantic_score, # Nueva métrica añadida al diccionario
        "frases_similares": matches[:top_n_matches]
    }


def build_highlighted_html(original_text, matches):
    import html as html_module
    escaped = html_module.escape(original_text)
    for m in matches:
        frase = m.get("frase_original", "")
        if not frase:
            continue
        escaped_frase = html_module.escape(frase)
        if escaped_frase in escaped:
            escaped = escaped.replace(
                escaped_frase,
                f'<mark title="Coincidencia: {m.get("coincidencia", 0)}%">{escaped_frase}</mark>',
                1
            )
    return escaped.replace("\n", "<br>")