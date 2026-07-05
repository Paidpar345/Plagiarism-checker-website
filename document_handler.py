import os
import docx
import pdfplumber

ALLOWED_EXTENSIONS = {'docx', 'pdf', 'txt'}
MAX_CHARS = 200_000  # safety cap so huge docs don't blow up downstream processing


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_docx(file_stream):
    try:
        doc = docx.Document(file_stream)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Error al procesar el archivo Word: {str(e)}")


def extract_text_from_pdf(file_stream):
    try:
        text_pages = []
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(layout=False, use_text_flow=True)
                if page_text:
                    text_pages.append(page_text)

        if not text_pages:
            raise ValueError("El PDF parece estar vacio o contener solo imagenes (requiere OCR).")

        return "\n".join(text_pages)
    except Exception as e:
        raise ValueError(f"Error al procesar el archivo PDF: {str(e)}")


def process_uploaded_file(file):
    if not file or file.filename == '':
        raise ValueError("No se ha proporcionado ningun archivo valido.")

    filename = file.filename
    if not allowed_file(filename):
        raise ValueError(f"Extension de archivo no permitida. Formatos aceptados: {', '.join(ALLOWED_EXTENSIONS)}")

    extension = filename.rsplit('.', 1)[1].lower()
    file.seek(0)

    if extension == 'docx':
        text = extract_text_from_docx(file)
    elif extension == 'pdf':
        text = extract_text_from_pdf(file)
    elif extension == 'txt':
        text = file.read().decode('utf-8', errors='ignore')
    else:
        raise ValueError("Tipo de archivo no soportado internamente.")

    if not text or not text.strip():
        raise ValueError("No se pudo extraer texto legible del documento.")

    return text[:MAX_CHARS]