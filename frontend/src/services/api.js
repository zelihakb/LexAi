const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function cleanObject(obj = {}) {
  return Object.fromEntries(
    Object.entries(obj).filter(
      ([, value]) => String(value ?? "").trim() !== "",
    ),
  );
}

async function requestJson(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.error || "İstek tamamlanamadı.");
  }

  return data;
}

async function requestFormData(path, formData) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.error || "İstek tamamlanamadı.");
  }

  return data;
}

export async function askQuestion(question) {
  return requestJson("/ask", {
    question: String(question || "").trim(),
  });
}

export async function findDecisions(query, filters = {}) {
  const cleanFilters = cleanObject({
    year: filters.year,
    court: filters.court,
    case_no: filters.case_no,
    decision_no: filters.decision_no,
    number: filters.case_no || filters.decision_no || filters.number,
  });

  return requestJson("/find", {
    query: String(query || "").trim(),
    filters: cleanFilters,
  });
}

export async function createPetition(form = {}) {
  return requestJson("/petition", {
    petition_type: String(form.petition_type || "").trim(),
    authority: String(form.authority || "").trim(),
    applicant: String(form.applicant || "").trim(),
    opponent: String(form.opponent || "").trim(),
    event_summary: String(form.event_summary || "").trim(),
    request_summary: String(form.request_summary || "").trim(),
    extra_notes: String(form.extra_notes || "").trim(),
  });
}

export async function ocrDocumentImage(file, documentType = "Diğer") {
  const formData = new FormData();
  formData.append("image", file);
  formData.append("document_type", String(documentType || "Diğer").trim());

  return requestFormData("/document/ocr", formData);
}

export async function explainDocumentText(text, documentType = "Diğer") {
  return requestJson("/document/explain", {
    text: String(text || "").trim(),
    document_type: String(documentType || "Diğer").trim(),
  });
}