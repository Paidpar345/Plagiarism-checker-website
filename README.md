# Detector de Plagio

Aplicacion web que permite subir un documento (PDF, DOCX o TXT), extraer
frases aleatorias de su contenido, buscarlas en Google y comparar el texto
del documento con el de las paginas web encontradas para estimar un
porcentaje de similitud (plagio potencial).

## Arquitectura

\`\`\`
Usuario -> Flask (app.py) -> Celery (tasks.py) -> Redis (broker/backend)
                                   |
                                   +--> web_search.py (busqueda + scraping via scrape.do)
                                   +--> similarity_engine.py (TF-IDF, n-gramas, shingling)
                                   +--> storage.py (SQLite: estado y resultados de cada job)
                                   +--> pdf_report.py (informe PDF descargable)
\`\`\`

El flujo es asincrono: subir un documento crea un `job_id` (UUID) que se
procesa en segundo plano con Celery mientras el navegador consulta el
estado (`/api/scan/status/<job_id>`) por polling hasta que el analisis
termina y redirige al reporte (`/report/<job_id>`).

## Estructura de archivos

\`\`\`
.
├── app.py                  # Rutas Flask, seguridad, autorizacion de jobs
├── celery_app.py           # Configuracion de Celery (broker, beat schedule)
├── tasks.py                # Tarea asincrona principal de analisis
├── web_search.py           # Busqueda en Google + scraping + limpieza de HTML
├── similarity_engine.py    # Metricas de similitud (TF-IDF, n-gramas, shingling)
├── document_handler.py     # Extraccion de texto desde PDF/DOCX/TXT
├── storage.py              # Persistencia de jobs en SQLite
├── cache_utils.py          # Cache en disco de busquedas y scraping
├── pdf_report.py           # Generacion del informe PDF descargable
├── templates/
│   ├── index.html          # Formulario de subida
│   └── report.html         # Vista de resultados
├── static/
│   └── js/
│       └── main.js         # Logica de frontend (antes inline, ahora separada)
├── requirements.txt
└── .env                    # Variables de entorno (no versionar)
\`\`\`

## Requisitos previos

- Python 3.10+
- Redis (broker y backend de Celery)
- Una cuenta y token de [scrape.do](https://scrape.do) para busqueda en
  Google y scraping de paginas (la app no llama a Google directamente)
- `libmagic` instalado a nivel de sistema (dependencia de `python-magic`)
  - Debian/Ubuntu: `sudo apt-get install libmagic1`
  - macOS: `brew install libmagic`

## Instalacion

\`\`\`bash
python -m venv venv
source venv/bin/activate       # En Windows: venv\Scripts\activate

pip install -r requirements.txt
\`\`\`

### requirements.txt (referencia)

\`\`\`
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
\`\`\`

## Variables de entorno (.env)

Crea un archivo `.env` en la raiz del proyecto:

\`\`\`dotenv
# Token de la API de scrape.do (obligatorio para busqueda y scraping)
SCRAPEDO_TOKEN=tu_token_aqui

# Redis para Celery (broker/backend) y para Flask-Limiter
REDIS_URL=redis://localhost:6379/0

# Clave secreta de Flask para firmar la sesion (obligatoria en produccion)
# Si no se define, se genera una y se persiste en .secret_key (solo para
# desarrollo local; en produccion definir siempre esta variable).
FLASK_SECRET_KEY=cambia_esto_por_una_clave_larga_y_aleatoria

# Activa el modo debug de Flask (NUNCA en produccion)
FLASK_DEBUG=0

# Fuerza que las cookies de sesion solo se envien por HTTPS
FORCE_HTTPS=0

# Zona horaria para las tareas programadas de Celery
APP_TIMEZONE=Europe/Madrid

# Numero de workers concurrentes de Celery
CELERY_CONCURRENCY=2
\`\`\`

> **Importante (seguridad):** `FLASK_SECRET_KEY` debe ser fija y secreta en
> produccion. Si se despliega con varios procesos/workers sin definir esta
> variable, cada proceso generaria una clave distinta y las sesiones de los
> usuarios (usadas para autorizar el acceso a sus propios reportes) dejarian
> de funcionar de forma consistente.

## Puesta en marcha (desarrollo)

Necesitas 3 procesos corriendo en paralelo:

\`\`\`bash
# 1. Redis (si no lo tienes como servicio del sistema)
redis-server

# 2. Worker de Celery
celery -A celery_app.celery worker --loglevel=info

# 3. (Opcional) Beat de Celery, para la purga diaria de jobs y cache antiguos
celery -A celery_app.celery beat --loglevel=info

# 4. Servidor Flask
python app.py
\`\`\`

La aplicacion queda disponible en `http://localhost:5000`.

## Uso

1. Abre `http://localhost:5000` en el navegador.
2. Sube un archivo PDF, DOCX o TXT (maximo 15 MB).
3. Ajusta el umbral de similitud minimo y el algoritmo de deteccion
   (combinado, TF-IDF, n-gramas o shingling).
4. Pulsa "Analizar documento". La barra de progreso muestra el estado en
   tiempo real (extraccion de frases, busqueda, scraping, comparacion).
5. Al finalizar, se redirige automaticamente al reporte con las fuentes
   encontradas, el porcentaje de similitud por fuente y los fragmentos de
   texto coincidentes.
6. Desde el reporte se puede descargar un informe en PDF con el resumen
   visual y el detalle de coincidencias.

## Algoritmos de similitud

| Algoritmo | Descripcion | Mejor para |
|---|---|---|
| Combinado | Promedio ponderado de TF-IDF (40%), n-gramas (25%) y shingling (35%) | Uso general, mas robusto |
| TF-IDF | Similitud tematica ponderada por rareza de palabras | Detectar temas compartidos, ignora el orden |
| N-gramas | Solapamiento de secuencias de 4 palabras | Detectar parafraseo con reordenamiento local |
| Shingling | Fingerprinting por hashes de 8 tokens (adaptativo en textos cortos) | Detectar copia casi exacta |

## Notas de seguridad implementadas

- **Autorizacion por sesion:** cada job queda asociado a un `owner_token`
  guardado en la sesion firmada del navegador; solo el propietario puede
  consultar el estado, el reporte HTML o el PDF de su propio analisis.
- **Validacion cruzada de archivos:** se verifica que el MIME real del
  archivo (via `libmagic`) coincida con la extension declarada.
- **Proteccion SSRF:** las URLs a scrapear se validan para excluir
  esquemas distintos de http/https y hosts privados/loopback.
- **Limites anti "bomba de archivos":** numero maximo de paginas PDF y de
  parrafos DOCX antes de la extraccion de texto.
- **Cabeceras de seguridad:** CSP, `X-Frame-Options`, `X-Content-Type-Options`,
  `Referrer-Policy` y `Permissions-Policy` en todas las respuestas.
- **Rate limiting:** maximo 5 analisis por hora por IP en `/api/scan`.

## Notas de diseno

- El scraping de cada URL se realiza una unica vez por analisis (el texto
  se reutiliza tanto para calcular el IDF del corpus como para el scoring
  de similitud), evitando llamadas duplicadas a la API de scraping.
- Los resultados de busqueda y scraping se cachean en disco
  (`.cache_scraped/`) con TTL corto (30 min) para fallos y TTL largo
  (6-24 h) para resultados validos.
- Los jobs y su cache se purgan automaticamente cada dia (tarea
  `purge-old-jobs-daily` programada con Celery Beat).

## Limitaciones conocidas

- El scraping depende de un servicio de terceros (scrape.do); si el token
  no esta configurado o se agota la cuota, las busquedas devolveran
  resultados vacios.
- PDFs escaneados sin capa de texto (solo imagenes) no pueden analizarse
  sin OCR, que no esta incluido en esta version.
- El calculo de similitud es CPU-bound y se ejecuta en threads; para
  cargas muy altas se recomienda escalar horizontalmente con mas workers
  de Celery en vez de aumentar la concurrencia por proceso.
