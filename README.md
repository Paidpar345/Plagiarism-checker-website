# Detector de Plagio

Aplicación web que permite subir un documento (PDF, DOCX o TXT), extraer frases aleatorias de su contenido, buscarlas en Google y comparar el texto del documento con el de las páginas web encontradas para estimar un porcentaje de similitud (plagio potencial).

---

# Arquitectura

```text
Usuario
    │
    ▼
Flask (app.py)
    │
    ▼
Celery (tasks.py) ─────────────── Redis (broker/backend)
    │
    ├── web_search.py
    │      └── Búsqueda + scraping mediante scrape.do
    │
    ├── similarity_engine.py
    │      └── TF-IDF, n-gramas y shingling
    │
    ├── storage.py
    │      └── SQLite (estado y resultados)
    │
    └── pdf_report.py
           └── Generación del informe PDF
```

El flujo es completamente asíncrono. Al subir un documento se crea un `job_id` (UUID) que se procesa en segundo plano mediante Celery mientras el navegador consulta periódicamente el estado mediante:

```
/api/scan/status/<job_id>
```

Cuando el análisis termina, el usuario es redirigido automáticamente a:

```
/report/<job_id>
```

---

# Estructura del proyecto

```text
.
├── app.py                  # Rutas Flask, seguridad y autorización
├── celery_app.py           # Configuración de Celery
├── tasks.py                # Tarea principal de análisis
├── web_search.py           # Búsqueda y scraping
├── similarity_engine.py    # Algoritmos de similitud
├── document_handler.py     # Extracción de texto
├── storage.py              # Persistencia SQLite
├── cache_utils.py          # Caché de búsquedas
├── pdf_report.py           # Generación del informe PDF
├── templates/
│   ├── index.html
│   └── report.html
├── static/
│   └── js/
│       └── main.js
├── requirements.txt
└── .env                    # Variables de entorno (NO versionar)
```

---

# Requisitos

- Python 3.10 o superior
- Redis
- Cuenta y token de **scrape.do**
- `libmagic`

Instalación de `libmagic`:

**Ubuntu / Debian**

```bash
sudo apt-get install libmagic1
```

**macOS**

```bash
brew install libmagic
```

---

# Instalación

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

---

# Dependencias principales

```text
Flask
Flask-Limiter
python-magic
python-docx
pdfplumber
requests
beautifulsoup4
python-dotenv
celery
redis
reportlab
matplotlib
```

---

# Variables de entorno

Crea un archivo `.env` en la raíz del proyecto.

```dotenv
# Token de scrape.do
SCRAPEDO_TOKEN=tu_token

# Redis
REDIS_URL=redis://localhost:6379/0

# Clave secreta de Flask
FLASK_SECRET_KEY=una_clave_larga_y_segura

# Modo debug
FLASK_DEBUG=0

# Cookies solo HTTPS
FORCE_HTTPS=0

# Zona horaria
APP_TIMEZONE=Europe/Madrid

# Workers de Celery
CELERY_CONCURRENCY=2
```

> **Importante**
>
> En producción debe definirse siempre `FLASK_SECRET_KEY`.
> Si varios procesos generan claves distintas, las sesiones dejarán de ser válidas.

---

# Puesta en marcha

Se necesitan cuatro procesos.

## 1. Redis

```bash
redis-server
```

## 2. Worker de Celery

```bash
celery -A celery_app.celery worker --loglevel=info
```

## 3. Celery Beat (opcional)

```bash
celery -A celery_app.celery beat --loglevel=info
```

## 4. Flask

```bash
python app.py
```

La aplicación estará disponible en:

```
http://localhost:5000
```

---

# Uso

1. Abrir `http://localhost:5000`.
2. Subir un archivo **PDF**, **DOCX** o **TXT** (máximo 15 MB).
3. Elegir el algoritmo y el umbral de similitud.
4. Pulsar **Analizar documento**.
5. Esperar mientras se realiza:

   - Extracción de frases
   - Búsqueda
   - Scraping
   - Comparación

6. Al finalizar se mostrará el informe.
7. El informe puede descargarse en PDF.

---

# Algoritmos de similitud

| Algoritmo | Descripción | Mejor para |
|-----------|-------------|------------|
| **Combinado** | TF-IDF (40%), N-gramas (25%) y Shingling (35%) | Uso general |
| **TF-IDF** | Similitud basada en importancia de palabras | Comparar temas |
| **N-gramas** | Solapamiento de secuencias de cuatro palabras | Detectar parafraseo |
| **Shingling** | Fingerprinting mediante hashes de ocho tokens | Detectar copia casi exacta |

---

# Seguridad

La aplicación incorpora:

- Autorización por sesión.
- Validación del tipo MIME mediante `libmagic`.
- Protección frente a ataques SSRF.
- Límites para evitar archivos maliciosos.
- Cabeceras HTTP de seguridad:
  - CSP
  - X-Frame-Options
  - X-Content-Type-Options
  - Referrer-Policy
  - Permissions-Policy
- Rate limiting:
  - Máximo **5 análisis por hora** por IP.

---

# Diseño

- Cada URL solo se scrapea una vez por análisis.
- Los resultados se almacenan en caché.
- TTL de la caché:
  - 30 minutos para errores.
  - 6–24 horas para resultados válidos.
- Celery Beat elimina automáticamente trabajos y caché antiguos.

---

# Limitaciones

- El scraping depende de **scrape.do**.
- Los PDF escaneados (solo imágenes) requieren OCR, que no está incluido.
- El cálculo de similitud consume CPU.
- Para alta carga se recomienda aumentar el número de workers de Celery en lugar de incrementar la concurrencia de cada proceso.
