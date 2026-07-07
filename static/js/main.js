// CSP: script lives in static/js/main.js (script-src 'self', no unsafe-inline)

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

// Stages
const stages = {
  upload:  document.getElementById('stage-upload'),
  process: document.getElementById('stage-process'),
  search:  document.getElementById('stage-search'),
  report:  document.getElementById('stage-report'),
};

// ── Advanced accordion toggle ──
const advancedToggle = document.getElementById('advancedToggle');
const advancedBody   = document.getElementById('advancedBody');
advancedToggle.addEventListener('click', () => {
  const expanded = advancedToggle.getAttribute('aria-expanded') === 'true';
  advancedToggle.setAttribute('aria-expanded', String(!expanded));
  advancedBody.hidden = expanded;
});

// ── Umbral slider ──
umbralInput.addEventListener('input', () => {
  umbralValue.textContent = umbralInput.value;
  umbralInput.setAttribute('aria-valuenow', umbralInput.value);
});

// ── Algorithm hints ──
const ALGO_HINTS = {
  combinado: 'Combina múltiples señales para el resultado más completo.',
  tfidf:     'Rápido. Detecta similitud temática; ignora el orden de palabras.',
  ngramas:   'Preciso. Ideal para detectar frases reordenadas o parafraseadas.',
  shingling: 'Exhaustivo. Solo marca coincidencias de texto casi idéntico.',
};
algoritmoSelect.addEventListener('change', () => {
  algoHint.textContent = ALGO_HINTS[algoritmoSelect.value] || '';
});

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

fileInput.addEventListener('change', () => {
  if (!fileInput.files.length) { clearFileInfo(); return; }
  const file = fileInput.files[0];
  const err  = validateFile(file);
  if (err) { showError(err); fileInput.value = ''; clearFileInfo(); return; }
  clearError();
  showFileInfo(file);
});

// ── Drag & drop ──
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
const STAGE_ORDER = ['upload', 'process', 'search', 'report'];
function setStage(active) {
  const idx = STAGE_ORDER.indexOf(active);
  STAGE_ORDER.forEach((s, i) => {
    stages[s].classList.remove('active', 'done');
    if (i < idx)       stages[s].classList.add('done');
    else if (i === idx) stages[s].classList.add('active');
  });
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
      const pct = (progreso.actual != null && progreso.total > 0)
        ? Math.round((progreso.actual / progreso.total) * 100)
        : null;

      if (pct !== null) {
        progressBar.style.width = pct + '%';
        progressBar.parentElement.setAttribute('aria-valuenow', pct);
      }

      const msg = progreso.mensaje || 'Procesando...';
      progressMsg.textContent = msg;

      // Map message keywords to visual stages
      if      (/subiendo|upload/i.test(msg))     setStage('upload');
      else if (/procesando|extrayendo/i.test(msg)) setStage('process');
      else if (/buscando|web/i.test(msg))        setStage('search');
      else if (/generando|informe/i.test(msg))   setStage('report');

      if (job.status === 'completado') {
        clearInterval(interval);
        setStage('report');
        STAGE_ORDER.forEach(s => { stages[s].classList.remove('active'); stages[s].classList.add('done'); });
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
form.addEventListener('submit', async e => {
  e.preventDefault();
  clearError();

  if (!fileInput.files.length) { showError('Selecciona un archivo antes de continuar.'); return; }
  const err = validateFile(fileInput.files[0]);
  if (err) { showError(err); return; }

  progressBar.style.width = '5%';
  progressMsg.textContent = 'Iniciando...';
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
