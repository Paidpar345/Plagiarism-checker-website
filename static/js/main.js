// FIX (seguridad/funcionalidad): este script antes vivia inline dentro de
// index.html. La cabecera Content-Security-Policy define script-src 'self'
// sin 'unsafe-inline', por lo que el navegador bloqueaba ese <script> y el
// formulario de subida quedaba completamente roto en produccion. Moverlo a
// un fichero estatico servido desde el mismo origen soluciona el problema
// sin debilitar la CSP.
const form = document.getElementById("scanForm");
const spinnerWrap = document.getElementById("spinnerWrap");
const submitBtn = document.getElementById("submitBtn");
const errorBox = document.getElementById("errorBox");
const progressBar = document.getElementById("progressBar");
const progressMsg = document.getElementById("progressMsg");
const umbralInput = document.getElementById("umbral");
const umbralValue = document.getElementById("umbralValue");
const fileInput = document.getElementById("document");
const uploadZone = document.getElementById("uploadZone");
const algoritmoSelect = document.getElementById("algoritmo");
const algoHint = document.getElementById("algoHint");
const fileNameDisplay = document.getElementById("fileNameDisplay");

umbralInput.addEventListener("input", () => {
  umbralValue.textContent = umbralInput.value;
});

const ALGO_HINTS = {
  combinado: "Combina las 3 senales para el resultado mas equilibrado.",
  tfidf: "Detecta similitud tematica; ignora el orden de las palabras.",
  ngramas: "Mejor para detectar frases reordenadas o parafraseadas.",
  shingling: "Mas estricto: solo marca coincidencias de texto casi identico.",
};
algoritmoSelect.addEventListener("change", () => {
  algoHint.textContent = ALGO_HINTS[algoritmoSelect.value] || "";
});

// FIX (seguridad/funcionalidad): validacion de extension y tamano en el
// cliente ANTES de enviar (antes solo se validaba en el backend, obligando
// a subir archivos completos de 15MB para descubrir que el formato no era
// valido).
const ALLOWED_EXT = ["pdf", "docx", "txt"];
const MAX_BYTES = 15 * 1024 * 1024;

function validateFile(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (!ALLOWED_EXT.includes(ext)) {
    return "Formato no soportado. Usa PDF, DOCX o TXT.";
  }
  if (file.size > MAX_BYTES) {
    return "El archivo supera el tamano maximo permitido (15 MB).";
  }
  return null;
}

fileInput.addEventListener("change", () => {
  if (!fileInput.files.length) {
    fileNameDisplay.textContent = "";
    return;
  }
  const file = fileInput.files[0];
  const err = validateFile(file);
  if (err) {
    showError(err);
    fileInput.value = "";
    fileNameDisplay.textContent = "";
    return;
  }
  fileNameDisplay.textContent = file.name;
});

["dragover", "dragleave", "drop"].forEach((evt) => {
  uploadZone.addEventListener(evt, (e) => {
    e.preventDefault();
    if (evt === "dragover") uploadZone.classList.add("dragover");
    if (evt === "dragleave" || evt === "drop")
      uploadZone.classList.remove("dragover");
  });
});
uploadZone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) {
    const file = e.dataTransfer.files[0];
    const err = validateFile(file);
    if (err) {
      showError(err);
      return;
    }
    fileInput.files = e.dataTransfer.files;
    fileNameDisplay.textContent = file.name;
  }
});

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("d-none");
  spinnerWrap.style.display = "none";
  submitBtn.disabled = false;
}

function pollJobStatus(jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/scan/status/${jobId}`);
      const job = await res.json();

      if (!res.ok) {
        clearInterval(interval);
        showError(job.error || "No se pudo consultar el estado del analisis.");
        return;
      }

      const progreso = job.progreso || {};
      if (
        progreso.actual != null &&
        progreso.total != null &&
        progreso.total > 0
      ) {
        const pct = Math.round((progreso.actual / progreso.total) * 100);
        progressBar.style.width = pct + "%";
      }
      progressMsg.textContent = progreso.mensaje || "Procesando...";

      if (job.status === "completado") {
        clearInterval(interval);
        window.location.href = `/report/${jobId}`;
      } else if (job.status === "error") {
        clearInterval(interval);
        showError(progreso.mensaje || "Ocurrio un error durante el analisis.");
      }
    } catch (err) {
      clearInterval(interval);
      showError("Se perdio la conexion con el servidor. Intentalo de nuevo.");
    }
  }, 1500);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.classList.add("d-none");

  if (!fileInput.files.length) {
    showError("Selecciona un archivo antes de continuar.");
    return;
  }

  const err = validateFile(fileInput.files[0]);
  if (err) {
    showError(err);
    return;
  }

  progressBar.style.width = "5%";
  progressMsg.textContent = "Iniciando...";
  spinnerWrap.style.display = "block";
  submitBtn.disabled = true;

  const formData = new FormData();
  formData.append("document", fileInput.files[0]);
  formData.append("umbral", umbralInput.value);
  formData.append("algoritmo", algoritmoSelect.value);

  try {
    const res = await fetch("/api/scan", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "No se pudo iniciar el analisis.");
      return;
    }

    pollJobStatus(data.job_id);
  } catch (err) {
    showError("No se pudo conectar con el servidor. Intentalo de nuevo.");
  }
});
