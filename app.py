import os
import re
import logging
import traceback
import secrets
import magic
from flask import Flask, request, render_template, jsonify, send_file, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from document_handler import process_uploaded_file
from pdf_report import build_pdf_report
from storage import create_job, get_job, get_job_owner_token
from tasks import run_plagiarism_scan
from similarity_engine import ALGORITHM_CHOICES
import tempfile
import shutil

app = Flask(__name__)

# FIX (seguridad): la secret_key ya no se genera aleatoriamente en cada
# arranque (rompia las sesiones al reiniciar o al usar varios workers).
# Debe fijarse via variable de entorno en produccion; en desarrollo se
# genera una vez y se persiste en un fichero local para no perderla.
_SECRET_KEY_ENV = os.environ.get("FLASK_SECRET_KEY")
if _SECRET_KEY_ENV:
    app.secret_key = _SECRET_KEY_ENV
else:
    _key_path = os.path.join(os.path.dirname(__file__), ".secret_key")
    if os.path.exists(_key_path):
        with open(_key_path, "r") as _f:
            app.secret_key = _f.read().strip()
    else:
        app.secret_key = secrets.token_hex(32)
        with open(_key_path, "w") as _f:
            _f.write(app.secret_key)

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# FIX (seguridad): forzar cookies seguras si la app corre detras de HTTPS.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FORCE_HTTPS", "0") == "1"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("app_errors.log"), logging.StreamHandler()]
)
logger = logging.getLogger("plagiarism_checker")


limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "redis://localhost:6379/1")
)


# FIX (implementacion): mapa extension -> mimetypes reales esperados, para
# poder cruzar extension declarada y contenido real del archivo (antes se
# validaban por separado y no era posible detectar un .txt que en realidad
# fuese un binario, o viceversa).
EXTENSION_TO_MIME = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
}

ALLOWED_MIME_TYPES = {m for mimes in EXTENSION_TO_MIME.values() for m in mimes}


GENERIC_ERROR_MESSAGES = {
    400: "La solicitud no es valida. Revisa el archivo e intentalo de nuevo.",
    403: "No tienes permiso para acceder a este recurso.",
    404: "El recurso solicitado no existe.",
    413: "El archivo supera el tamano maximo permitido (15 MB).",
    429: "Has alcanzado el limite de analisis permitidos. Intenta mas tarde.",
    500: "Ocurrio un error inesperado. Intentalo de nuevo mas tarde.",
}


UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def is_valid_job_id(value):
    return bool(value) and bool(UUID_RE.fullmatch(value))


def _current_owner_token():
    """FIX (seguridad - IDOR): cada navegador recibe un token de propietario
    almacenado en la sesion firmada por Flask. Se guarda junto al job en BD
    y se exige que coincida antes de devolver el estado, el reporte HTML o
    el PDF de un job. Esto evita que cualquiera con el job_id (UUID visible
    en la URL) pueda ver documentos ajenos."""
    token = session.get("owner_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["owner_token"] = token
    return token


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # FIX (seguridad/funcionalidad): el script ya no es inline (se movio a
    # /static/js/main.js), por lo que "script-src 'self'" ahora SI permite
    # que el formulario funcione, sin necesitar 'unsafe-inline'.
    csp = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
        "script-src 'self' cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' cdn.jsdelivr.net fonts.gstatic.com;"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers.pop("Server", None)
    return response


@app.errorhandler(Exception)
def handle_any_exception(e):
    if isinstance(e, HTTPException):
        code = e.code
    else:
        code = 500

    logger.error(
        "Error no controlado [%s] en %s: %s\n%s",
        code, request.path, str(e), traceback.format_exc()
    )

    message = GENERIC_ERROR_MESSAGES.get(code, "Ocurrio un error inesperado.")
    return jsonify({"error": message}), code


@app.route("/")
def index():
    return render_template("index.html", algoritmos=ALGORITHM_CHOICES)


def _validate_real_mime(file, extension):
    file.seek(0)
    header_bytes = file.read(4096)
    file.seek(0)
    try:
        mime = magic.from_buffer(header_bytes, mime=True)
    except Exception:
        raise ValueError("No se pudo verificar el tipo de archivo.")
    if mime not in ALLOWED_MIME_TYPES:
        raise ValueError("El tipo de archivo no esta permitido.")
    # FIX (seguridad): cruce extension <-> mime real. Antes un archivo con
    # extension .txt pero contenido binario (o viceversa) pasaba sin error.
    expected = EXTENSION_TO_MIME.get(extension, set())
    if expected and mime not in expected:
        raise ValueError("El contenido del archivo no coincide con su extension.")
    file.seek(0)


@app.route("/api/scan", methods=["POST"])
@limiter.limit("5 per hour")
def scan_document():
    if "document" not in request.files:
        return jsonify({"error": "No se ha subido ningún archivo."}), 400

    file = request.files["document"]
    if file.filename == "":
        return jsonify({"error": "El nombre del archivo está vacío."}), 400

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    try:
        _validate_real_mime(file, extension)
        texto_documento = process_uploaded_file(file)

        try:
            umbral = float(request.form.get("umbral", 5.0))
        except (TypeError, ValueError):
            umbral = 5.0
        umbral = max(0.0, min(umbral, 100.0))

        algoritmo = request.form.get("algoritmo", "combinado")
        if algoritmo not in ALGORITHM_CHOICES:
            algoritmo = "combinado"

        scan_mode = request.form.get("scan_mode", "web")

        safe_filename = os.path.basename(file.filename)[:120]
        owner_token = _current_owner_token()
        job_id = create_job(safe_filename, owner_token)

        # ── NUEVA RAMIFICACIÓN PARA EL CORPUS LOCAL ──
        if scan_mode == "corpus":
            corpus_files = request.files.getlist("corpus_files")
            if not corpus_files or corpus_files[0].filename == "":
                return jsonify({"error": "Debes seleccionar al menos un archivo para el corpus local."}), 400
            if len(corpus_files) > 10:
                return jsonify({"error": "No puedes subir más de 10 archivos para el corpus."}), 400

            # Crear directorio temporal único y seguro para este análisis
            corpus_dir = tempfile.mkdtemp(prefix="corpus_scan_")
            corpus_filenames = []

            for c_file in corpus_files:
                c_ext = c_file.filename.rsplit(".", 1)[-1].lower() if "." in c_file.filename else ""
                try:
                    _validate_real_mime(c_file, c_ext)
                    
                    # Medir tamaño del archivo enviado
                    c_file.seek(0, os.SEEK_END)
                    c_size = c_file.tell()
                    c_file.seek(0)
                    if c_size > 5 * 1024 * 1024: # Límite de 5MB por política de privacidad/rendimiento
                        raise ValueError(f"El archivo '{c_file.filename}' supera el límite de 5 MB.")

                    safe_c_name = os.path.basename(c_file.filename)
                    target_path = os.path.join(corpus_dir, safe_c_name)
                    c_file.save(target_path)
                    corpus_filenames.append(safe_c_name)
                except ValueError as ve:
                    # Si falla la validación de algún archivo del corpus, destruimos el temporal de inmediato
                    shutil.rmtree(corpus_dir)
                    return jsonify({"error": f"Error en archivo de corpus: {str(ve)}"}), 400

            # Encolar la tarea del corpus local creada en el paso anterior
            from tasks import run_local_corpus_scan
            run_local_corpus_scan.delay(job_id, texto_documento, safe_filename, corpus_dir, corpus_filenames, umbral, algoritmo)
        
        else:
            # Encolar búsqueda tradicional en internet
            run_plagiarism_scan.delay(job_id, texto_documento, safe_filename, umbral, algoritmo)

        return jsonify({"status": "queued", "job_id": job_id}), 202

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400


def _authorize_job(job_id):
    """FIX (seguridad - IDOR): valida formato de job_id, existencia y que el
    solicitante sea el propietario (mismo owner_token de sesion). Devuelve
    (job, error_response_or_None)."""
    if not is_valid_job_id(job_id):
        return None, (jsonify({"error": "Identificador invalido."}), 400)
    job = get_job(job_id)
    if not job:
        return None, (jsonify({"error": "Analisis no encontrado."}), 404)
    owner_token = session.get("owner_token")
    stored_owner = get_job_owner_token(job_id)
    if not owner_token or not stored_owner or owner_token != stored_owner:
        return None, (jsonify({"error": "No tienes permiso para acceder a este analisis."}), 403)
    return job, None


@app.route("/api/scan/status/<job_id>", methods=["GET"])
@limiter.exempt
def scan_status(job_id):
    job, err = _authorize_job(job_id)
    if err:
        return err
    return jsonify(job), 200


def _report_context(job, job_id):
    """Build extra template variables for report.html (issue #6).

    Returns a dict with:
    - total_fragmentos: total detected similar fragments across all sources
    - nivel_riesgo: 'alto' | 'medio' | 'bajo' based on similitud_global
    """
    resultados = job.get("resultado", {}).get("resultados", [])
    total_fragmentos = sum(
        len(r.get("frases_similares") or []) for r in resultados
    )
    s = job.get("resultado", {}).get("similitud_global", 0) or 0
    if s >= 50:
        nivel_riesgo = "alto"
    elif s >= 20:
        nivel_riesgo = "medio"
    else:
        nivel_riesgo = "bajo"
    return {"total_fragmentos": total_fragmentos, "nivel_riesgo": nivel_riesgo}


@app.route("/report/<job_id>")
def view_report(job_id):
    job, err = _authorize_job(job_id)
    if err:
        body, code = err
        return body.get_json().get("error", "Error"), code
    if job.get("status") != "completado":
        return "El analisis aun no esta listo o fallo.", 400
    ctx = _report_context(job, job_id)
    return render_template(
        "report.html",
        job=job,
        job_id=job_id,
        total_fragmentos=ctx["total_fragmentos"],
        nivel_riesgo=ctx["nivel_riesgo"],
    )


@app.route("/api/report/pdf/<job_id>", methods=["GET"])
def download_pdf(job_id):
    job, err = _authorize_job(job_id)
    if err:
        return err
    if job["status"] != "completado":
        return jsonify({"error": "No hay resultados disponibles para este analisis."}), 404
    buffer = build_pdf_report(job["resultado"])
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="reporte_plagio.pdf"
    )


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
