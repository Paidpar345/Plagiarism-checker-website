import os
import logging
import docx
import pdfplumber

logger = logging.getLogger("plagiarism_checker")

ALLOWED_EXTENSIONS = {"docx", "pdf", "txt"}
MAX_CHARS = 200_000

MAX_PDF_PAGES = 300
MAX_DOCX_PARAGRAPHS = 20000

# Límites para archivos del corpus local (issue #9)
CORPUS_MAX_FILES = 10
CORPUS_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_docx(file_stream):
    try:
        doc = docx.Document(file_stream)
        paragraphs = []
        for i, para in enumerate(doc.paragraphs):
            if i >= MAX_DOCX_PARAGRAPHS:
                logger.warning("DOCX truncado: supera %s parrafos", MAX_DOCX_PARAGRAPHS)
                break
            if para.text.strip():
                paragraphs.append(para.text)
        return "\n".join(paragraphs)
    except Exception as e:
        logger.warning("Fallo al procesar DOCX: %s", e)
        raise ValueError("No se pudo procesar el archivo Word. Verifica que no este danado o protegido.")


def extract_text_from_pdf(file_stream):
    try:
        text_pages = []
        with pdfplumber.open(file_stream) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ValueError(f"El PDF supera el limite de {MAX_PDF_PAGES} paginas permitidas.")
            for page in pdf.pages:
                page_text = page.extract_text(layout=False, use_text_flow=True)
                if page_text:
                    text_pages.append(page_text)

        if not text_pages:
            raise ValueError("El PDF parece estar vacio o contener solo imagenes escaneadas.")

        return "\n".join(text_pages)
    except ValueError:
        raise
    except Exception as e:
        logger.warning("Fallo al procesar PDF: %s", e)
        raise ValueError("No se pudo procesar el archivo PDF. Verifica que no este danado o protegido.")


def process_uploaded_file(file):
    if not file or file.filename == "":
        raise ValueError("No se ha proporcionado ningun archivo valido.")

    filename = file.filename
    if not allowed_file(filename):
        raise ValueError(f"Extension no permitida. Formatos aceptados: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    extension = filename.rsplit(".", 1)[1].lower()
    file.seek(0)

    try:
        if extension == "docx":
            text = extract_text_from_docx(file)
        elif extension == "pdf":
            text = extract_text_from_pdf(file)
        elif extension == "txt":
            text = file.read().decode("utf-8", errors="ignore")
        else:
            raise ValueError("Tipo de archivo no soportado.")
    except ValueError:
        raise
    except Exception as e:
        logger.error("Error inesperado procesando archivo: %s", e)
        raise ValueError("No se pudo leer el contenido del archivo.")

    if not text or not text.strip():
        raise ValueError("No se pudo extraer texto legible del documento.")

    return text[:MAX_CHARS]


def extract_text_from_path(filepath):
    """
    Extrae texto de un archivo ya guardado en disco (usado por el pipeline
    de corpus local, issue #9). Reutiliza los mismos extractores que
    process_uploaded_file para mantener coherencia.
    """
    if not os.path.isfile(filepath):
        raise ValueError(f"Archivo no encontrado: {filepath}")

    extension = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension no permitida: {extension}")

    try:
        if extension == "docx":
            with open(filepath, "rb") as fh:
                text = extract_text_from_docx(fh)
        elif extension == "pdf":
            with open(filepath, "rb") as fh:
                text = extract_text_from_pdf(fh)
        elif extension == "txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        else:
            raise ValueError("Tipo de archivo no soportado.")
    except ValueError:
        raise
    except Exception as e:
        logger.error("Error leyendo archivo de corpus %s: %s", filepath, e)
        raise ValueError("No se pudo leer el contenido del archivo del corpus.")

    return text[:MAX_CHARS]
