// CSP: script lives in static/js/main.js (script-src 'self', no unsafe-inline)

// ── Theme toggle (issue #13) ── runs before paint to avoid flash
(function() {
  var root  = document.documentElement;
  var saved = localStorage.getItem('theme') || 'dark';
  root.setAttribute('data-theme', saved);
  root.setAttribute('data-bs-theme', saved);
})();

// ── DOM refs ──
const form            = document.getElementById('scanForm');
const spinnerWrap     = document.getElementById('spinnerWrap');
const submitBtn       = document.getElementById('submitBtn');
const errorBox        = document.getElementById('errorBox');
const errorMsg        = document.getElementById('errorMsg');
const progressBar     = document.getElementById('progressBar');
const progressMsg     = document.getElementById('progressMsg');
const umbralInput     = document.getElementById('umbral');
const umbralValue     = document.getElementById('umbralValue');
const fileInput       = document.getElementById('document');
const uploadZone      = document.getElementById('uploadZone');
const algoritmoSelect = document.getElementById('algoritmo');
const algoHint        = document.getElementById('algoHint');
const fileInfo        = document.getElementById('fileInfo');
const fiName          = document.getElementById('fiName');
const fiMeta          = document.getElementById('fiMeta');
const fiBadge         = document.getElementById('fiBadge');
const themeToggle     = document.getElementById('themeToggle');
const themeIcon       = document.getElementById('themeIcon');

const MOON_SVG = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
const SUN_SVG  = '<circle cx="12" cy="12" r="5"/>' +
  '<line x1="12" y1="1" x2="12" y2="3"/>' +
  '<line x1="12" y1="21" x2="12" y2="23"/>' +
  '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>' +
  '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>' +
  '<line x1="1" y1="12" x2="3" y2="12"/>' +
  '<line x1="21" y1="12" x2="23" y2="12"/>' +
  '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>' +
  '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';

// Sync icon to current saved theme on load
if (themeIcon) {
  const current = localStorage.getItem('theme') || 'dark';
  themeIcon.innerHTML = current === 'dark' ? MOON_SVG : SUN_SVG;
}

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const root    = document.documentElement;
    const current = root.getAttribute('data-theme') || 'dark';
    const next    = current === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    root.setAttribute('data-bs-theme', next);
    localStorage.setItem('theme', next);
    if (themeIcon) themeIcon.innerHTML = next === 'dark' ? MOON_SVG : SUN_SVG;
    themeToggle.setAttribute('aria-label',
      next === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
  });
}

// ── Advanced accordion toggle ──
const advancedToggle = document.getElementById('advancedToggle');
const advancedBody   = document.getElementById('advancedBody');
if (advancedToggle && advancedBody) {
  advancedToggle.addEventListener('click', () => {
    const expanded = advancedToggle.getAttribute('aria-expanded') === 'true';
    advancedToggle.setAttribute('aria-expanded', String(!expanded));
    advancedBody.hidden = expanded;
  });
}

// ── Umbral slider ──
if (umbralInput) {
  umbralInput.addEventListener('input', () => {
    umbralValue.textContent = umbralInput.value;
    umbralInput.setAttribute('aria-valuenow', umbralInput.value);
  });
}

// ── Algorithm hints ──
const ALGO_HINTS = {
  combinado: 'Combina múltiples señales para el resultado más completo.',
  tfidf:     'Rápido. Detecta similitud temática; ignora el orden de palabras.',
  ngramas:   'Preciso. Ideal para detectar frases reordenadas o parafraseadas.',
  shingling: 'Exhaustivo. Solo marca coincidencias de texto casi idéntico.',
};
if (algoritmoSelect) {
  algoritmoSelect.addEventListener('change', () => {
    if (algoHint) algoHint.textContent = ALGO_HINTS[algoritmoSelect.value] || '';
  });
}

// ── File validation ──
const ALLOWED_EXT = ['pdf', 'docx', 'txt'];
const MAX_BYTES   = 15 * 1024 * 1024;
const EXT_LABELS  = { pdf: 'PDF', docx: 'Word', txt: 'Texto plano' };

function validateFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_EXT.includes(ext)) return 'Formato no soportado. Usa PDF, DOCX o TXT.';
  if (file.size > MAX_BYTES)       return 'El archivo supera el tamaño máximo permitido (15 MB).';
  return null;
}

function formatBytes(bytes) {
  if (bytes < 1024)        return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function showFileInfo(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  fiName.textContent  = file.name;
  fiMeta.textContent  = formatBytes(file.size) + '  ·  ' + (EXT_LABELS[ext] || ext.toUpperCase());
  fiBadge.textContent = 'LISTO';
  fileInfo.classList.add('show');
}

function clearFileInfo() {
  fileInfo.classList.remove('show');
  fiName.textContent = '';
  fiMeta.textContent = '';
}

if (fileInput) {
  fileInput.addEventListener('change', () => {
    if (!fileInput.files.length) { clearFileInfo(); return; }
    const file = fileInput.files[0];
    const err  = validateFile(file);
    if (err) { showError(err); fileInput.value = ''; clearFileInfo(); return; }
    clearError();
    showFileInfo(file);
  });
}

// ── Drag & drop ──
if (uploadZone) {
  ['dragover', 'dragleave', 'drop'].forEach(evt => {
    uploadZone.addEventListener(evt, e => {
      e.preventDefault();
      if (evt === 'dragover')                     uploadZone.classList.add('dragover');
      if (evt === 'dragleave' || evt === 'drop')  uploadZone.classList.remove('dragover');
    });
  });
  uploadZone.addEventListener('drop', e => {
    if (!e.dataTransfer.files.length) return;
    const file = e.dataTransfer.files[0];
    const err  = validateFile(file);
    if (err) { showError(err); return; }
    fileInput.files = e.dataTransfer.files;
    clearError();
    showFileInfo(file);
  });
}

// ── Error helpers ──
function showError(message) {
  errorMsg.textContent = message;
  errorBox.classList.remove('d-none');
  spinnerWrap.style.display = 'none';
  submitBtn.disabled = false;
}
function clearError() {
  errorBox.classList.add('d-none');
  errorMsg.textContent = '';
}

// ── Stage helpers ──
const stages = {
  upload:  document.getElementById('stage-upload'),
  process: document.getElementById('stage-process'),
  search:  document.getElementById('stage-search'),
  report:  document.getElementById('stage-report'),
};
const STAGE_ORDER = ['upload', 'process', 'search', 'report'];

const STAGE_PATTERNS = [
  { re: /subiendo|uploading/i,                       stage: 'upload'  },
  { re: /procesando|extrayendo|frases clave/i,       stage: 'process' },
  { re: /buscando|consulta|web|páginas encontradas/i, stage: 'search' },
  { re: /generando|informe|comparando página/i,      stage: 'report'  },
];

function setStage(active) {
  const idx = STAGE_ORDER.indexOf(active);
  STAGE_ORDER.forEach((s, i) => {
    if (!stages[s]) return;
    stages[s].classList.remove('active', 'done');
    if (i < idx)        stages[s].classList.add('done');
    else if (i === idx) stages[s].classList.add('active');
  });
}

function resetStages() {
  STAGE_ORDER.forEach(s => { if (stages[s]) stages[s].classList.remove('active', 'done'); });
}

function detectStageFromMessage(msg) {
  for (const { re, stage } of STAGE_PATTERNS) {
    if (re.test(msg)) return stage;
  }
  return null;
}

// ── Progress bar helper ──
function setProgress(pct, min = 5) {
  const clamped = Math.min(95, Math.max(min, pct));
  progressBar.style.width = clamped + '%';
  progressBar.setAttribute('aria-valuenow', clamped);
}

// ── Progress polling ──
function pollJobStatus(jobId) {
  setStage('upload');
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/scan/status/${jobId}`);
      const job = await res.json();

      if (!res.ok) {
        clearInterval(interval);
        showError(job.error || 'No se pudo consultar el estado del análisis.');
        return;
      }

      const progreso = job.progreso || {};

      if (progreso.actual != null && progreso.total > 0) {
        setProgress(Math.round((progreso.actual / progreso.total) * 100));
      }

      const msg = progreso.mensaje || 'Procesando...';
      progressMsg.textContent = msg;

      const detected = detectStageFromMessage(msg);
      if (detected) setStage(detected);

      if (job.status === 'completado') {
        clearInterval(interval);
        STAGE_ORDER.forEach(s => { if (stages[s]) { stages[s].classList.remove('active'); stages[s].classList.add('done'); } });
        progressBar.style.width = '100%';
        progressBar.setAttribute('aria-valuenow', 100);
        progressMsg.textContent = 'Informe generado. Redirigiendo...';
        window.location.href = `/report/${jobId}`;
      } else if (job.status === 'error') {
        clearInterval(interval);
        showError(progreso.mensaje || 'Ocurrió un error durante el análisis.');
      }
    } catch (err) {
      clearInterval(interval);
      showError('Se perdió la conexión con el servidor. Inténtalo de nuevo.');
    }
  }, 3000);
}

// ── Form submit ──
if (form) {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    clearError();

    if (!fileInput.files.length) { showError('Selecciona un archivo antes de continuar.'); return; }
    const err = validateFile(fileInput.files[0]);
    if (err) { showError(err); return; }

    resetStages();
    setProgress(5);
    progressMsg.textContent = 'Subiendo documento...';
    spinnerWrap.style.display = 'block';
    submitBtn.disabled = true;
    setStage('upload');

    const formData = new FormData();
    formData.append('document',  fileInput.files[0]);
    formData.append('umbral',    umbralInput.value);
    formData.append('algoritmo', algoritmoSelect.value);

    try {
      const res  = await fetch('/api/scan', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) { showError(data.error || 'No se pudo iniciar el análisis.'); return; }
      pollJobStatus(data.job_id);
    } catch (err) {
      showError('No se pudo conectar con el servidor. Inténtalo de nuevo.');
    }
  });
}
