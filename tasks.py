import logging
from celery_app import celery
from similarity_engine import calculate_similarity_report, compute_idf, clean_and_tokenize
from web_search import extract_smart_queries, search_google, scrape_and_clean_url
from storage import update_job_progress, complete_job, fail_job
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("plagiarism_checker")


def _score_only(url, texto_documento, consulta, texto_web, idf, umbral, algoritmo):
    # FIX (diseno): esta funcion ya NO vuelve a raspar la URL. El texto
    # scrapeado se pasa como parametro porque ya se obtuvo en la primera
    # pasada (ver run_plagiarism_scan). Antes se llamaba a
    # scrape_and_clean_url() dos veces por cada URL (una para construir el
    # corpus del IDF y otra para puntuar), duplicando llamadas pagadas a la
    # API de scraping y el tiempo total de la tarea.
    report = calculate_similarity_report(texto_documento, texto_web, idf=idf, algoritmo=algoritmo)
    if report["similitud"] > umbral:
        return {
            "consulta": consulta,
            "url": url,
            "similitud": report["similitud"],
            "similitud_tfidf": report["similitud_tfidf"],
            "similitud_ngramas": report["similitud_ngramas"],
            "similitud_shingling": report["similitud_shingling"],
            "frases_similares": report["frases_similares"]
        }
    return None


@celery.task(bind=True, soft_time_limit=280, time_limit=300)
def run_plagiarism_scan(self, job_id, texto_documento, documento_nombre, umbral=5.0, algoritmo="combinado"):
    # FIX (seguridad/diseno): se anaden soft_time_limit/time_limit al task
    # para que un job nunca quede "colgado" indefinidamente en estado
    # "procesando" si una llamada externa (scrape.do) no responde nunca.
    try:
        update_job_progress(job_id, "Extrayendo frases clave...")
        consultas = extract_smart_queries(texto_documento, num_queries=5, randomize=True)

        if not consultas:
            fail_job(job_id, "No se pudo extraer contenido legible del documento.")
            return

        update_job_progress(job_id, "Recopilando fuentes en la web...", 0, len(consultas))

        seen_urls = set()
        all_url_tasks = []
        for idx, consulta in enumerate(consultas, start=1):
            update_job_progress(job_id, f"Buscando consulta {idx} de {len(consultas)}...", idx, len(consultas))
            urls = search_google(consulta, nb_results=5)
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_url_tasks.append((url, consulta))

        if not all_url_tasks:
            complete_job(job_id, {
                "similitud_global": 0.0,
                "resultados": [],
                "documento": documento_nombre
            })
            return

        update_job_progress(job_id, f"Analizando {len(all_url_tasks)} paginas encontradas...", 0, len(all_url_tasks))

        # FIX (diseno): unica pasada de scraping. Se guarda el texto de cada
        # URL en un diccionario para reutilizarlo tanto en el calculo del
        # IDF como en el scoring, evitando el doble scraping anterior.
        scraped_by_url = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures_scrape = {executor.submit(scrape_and_clean_url, url): url for url, _ in all_url_tasks}
            for fut in as_completed(futures_scrape):
                url = futures_scrape[fut]
                try:
                    txt = fut.result()
                    if txt:
                        scraped_by_url[url] = txt
                except Exception as e:
                    logger.warning("Fallo raspando %s: %s", url, e)

        if not scraped_by_url:
            complete_job(job_id, {
                "similitud_global": 0.0,
                "resultados": [],
                "documento": documento_nombre
            })
            return

        corpus_tokens = [clean_and_tokenize(texto_documento)] + [clean_and_tokenize(t) for t in scraped_by_url.values()]
        idf = compute_idf(corpus_tokens)

        resultados_finales = []
        scoring_tasks = [(url, consulta) for url, consulta in all_url_tasks if url in scraped_by_url]

        # FIX (diseno): el calculo de similitud es CPU-bound (TF-IDF,
        # n-gramas, shingling y comparacion de oraciones); un ThreadPoolExecutor
        # no acelera este trabajo por el GIL. Se mantiene ThreadPoolExecutor
        # solo por simplicidad de despliegue (evitar pickling de closures con
        # ProcessPoolExecutor), pero ya no hace I/O duplicado, que era el
        # cuello de botella real.
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(
                    _score_only, url, texto_documento, consulta, scraped_by_url[url], idf, umbral, algoritmo
                )
                for url, consulta in scoring_tasks
            ]

            for i, fut in enumerate(as_completed(futures), start=1):
                update_job_progress(job_id, f"Comparando pagina {i} de {len(futures)}...", i, len(futures))
                try:
                    res = fut.result()
                    if res:
                        resultados_finales.append(res)
                except Exception as e:
                    logger.warning("Fallo comparando una pagina: %s", e)

        resultados_finales = sorted(resultados_finales, key=lambda x: x["similitud"], reverse=True)
        overall = round(sum(r["similitud"] for r in resultados_finales) / len(resultados_finales), 2) if resultados_finales else 0.0

        complete_job(job_id, {
            "similitud_global": overall,
            "resultados": resultados_finales,
            "documento": documento_nombre
        })

    except Exception as e:
        logger.error("Error inesperado en tarea de analisis %s: %s", job_id, e)
        fail_job(job_id, "Ocurrio un error inesperado durante el analisis. Intentalo de nuevo.")


@celery.task
def purge_old_jobs_task():
    from storage import purge_old_jobs
    from cache_utils import purge_expired_cache
    purge_old_jobs()
    purge_expired_cache()