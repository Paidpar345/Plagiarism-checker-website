# Detector de Plagio (Flask + Scrape.do)

Aplicacion web que permite subir un documento (.docx, .pdf, .txt), extraer
frases relevantes de forma aleatoria, buscarlas en Google via Scrape.do,
raspar los primeros resultados y calcular una similitud (TF cosine) entre
el documento subido y cada pagina web encontrada. Incluye exportacion a PDF.

## Estructura

- `app.py` - Rutas Flask (`/`, `/api/scan`, `/api/report/pdf`).
- `document_handler.py` - Extraccion de texto desde PDF/DOCX/TXT.
- `web_search.py` - Extraccion de frases aleatorias, busqueda en Google (Scrape.do) y scraping/limpieza de HTML.
- `similarity_engine.py` - Similitud coseno TF + deteccion de frases mas parecidas para citar en el reporte.
- `pdf_report.py` - Generacion de reporte PDF en memoria con ReportLab.
- `templates/index.html` - Interfaz Bootstrap con carga de archivo, resultados y boton de descarga PDF.

## Configuracion

1. Crear un entorno virtual e instalar dependencias:

   pip install -r requirements.txt

2. Copiar `.env.example` a `.env` y pegar tu token real de Scrape.do:

   cp .env.example .env

   El archivo `.env` debe verse asi (sin comillas, sin espacios alrededor del `=`):

   SCRAPEDO_TOKEN=tu_token_real_aqui

3. Ejecutar la aplicacion:

   python app.py

4. Abrir http://127.0.0.1:5000 en el navegador.

## Notas de diseno

- Las busquedas y el scraping de cada URL se ejecutan en paralelo con un `ThreadPoolExecutor`.
- `extract_smart_queries` selecciona frases de 5-10 palabras de forma aleatoria ponderada por relevancia.
- El motor de similitud identifica ademas las 3 frases del documento original mas parecidas a frases de la pagina web.
- El reporte PDF se genera en memoria (`io.BytesIO`) con ReportLab y se sirve con `send_file`.
- `.env` nunca debe subirse a Git; usa `.env.example` como plantilla para otros colaboradores.

## Mejoras pendientes sugeridas

- Rate limiting con Flask-Limiter en `/api/scan`.
- Cache de scraping por URL (Redis) para no repetir llamadas a Scrape.do.
- Escapar HTML en el frontend antes de insertarlo con innerHTML (riesgo XSS).
- Mover resultados de `LAST_RESULTS` a una base de datos en vez de memoria de proceso.
