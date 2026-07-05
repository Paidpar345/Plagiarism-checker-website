import os
from flask import Flask, request, render_template, jsonify, send_file
from document_handler import process_uploaded_file
from similarity_engine import calculate_similarity_report
from web_search import extract_smart_queries, search_google, scrape_and_clean_url
from pdf_report import build_pdf_report
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB upload limit

LAST_RESULTS = {}  # simple in-memory cache keyed by a session token, for PDF export


@app.route('/')
def index():
    return render_template('index.html')


def _scrape_and_score(url, texto_documento, consulta):
    texto_web = scrape_and_clean_url(url)
    if not texto_web:
        return None
    report = calculate_similarity_report(texto_documento, texto_web)
    if report['similitud'] > 5.0:
        return {
            'consulta': consulta,
            'url': url,
            'similitud': report['similitud'],
            'frases_similares': report['frases_similares']
        }
    return None


@app.route('/api/scan', methods=['POST'])
def scan_document():
    if 'document' not in request.files:
        return jsonify({"error": "No se ha subido ningun archivo."}), 400

    file = request.files['document']
    if file.filename == '':
        return jsonify({"error": "El nombre del archivo esta vacio."}), 400

    try:
        texto_documento = process_uploaded_file(file)
        consultas = extract_smart_queries(texto_documento, num_queries=5, randomize=True)

        if not consultas:
            return jsonify({"error": "No se pudo extraer contenido legible del documento."}), 400

        seen_urls = set()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for consulta in consultas:
                urls = search_google(consulta, nb_results=5)
                for url in urls:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    futures.append(executor.submit(_scrape_and_score, url, texto_documento, consulta))

            resultados_finales = []
            for fut in as_completed(futures):
                res = fut.result()
                if res:
                    resultados_finales.append(res)

        resultados_finales = sorted(resultados_finales, key=lambda x: x['similitud'], reverse=True)

        overall = round(sum(r['similitud'] for r in resultados_finales) / len(resultados_finales), 2) if resultados_finales else 0.0

        payload = {
            "status": "success",
            "similitud_global": overall,
            "resultados": resultados_finales,
            "documento": file.filename
        }
        LAST_RESULTS['ultimo'] = payload
        return jsonify(payload), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        print(f"Error critico en el servidor: {e}")
        return jsonify({"error": "Ocurrio un error inesperado al procesar el documento."}), 500


@app.route('/api/report/pdf', methods=['GET'])
def download_pdf():
    data = LAST_RESULTS.get('ultimo')
    if not data:
        return jsonify({"error": "No hay resultados recientes para exportar."}), 404
    buffer = build_pdf_report(data)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='reporte_plagio.pdf'
    )


if __name__ == '__main__':
    app.run(debug=True)