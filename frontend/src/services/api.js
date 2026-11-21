
const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001'

const TOKEN_KEY = 'medvision-access-token'

// =========================================================
// AUTHENTICATION HELPERS
// =========================================================

function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

function saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function logoutUser() {
  localStorage.removeItem(TOKEN_KEY)
}

function getAuthHeaders() {
  const token = getToken()

  return token
    ? { Authorization: `Bearer ${token}` }
    : {}
}

async function handleResponse(response, fallbackMessage) {
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || fallbackMessage)
  }

  return data
}

// =========================================================
// REGISTER PATIENT
// Public registration creates patient accounts only.
// =========================================================

export async function registerUser(name, email, password) {
  const response = await fetch(`${BASE}/api/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name,
      email,
      password
    })
  })

  const data = await handleResponse(
    response,
    'Registration failed'
  )

  if (data.access_token) {
    saveToken(data.access_token)
  }

  return data
}

// =========================================================
// LOGIN PATIENT / DOCTOR
// =========================================================

export async function loginUser(email, password) {
  const response = await fetch(`${BASE}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      email,
      password
    })
  })

  const data = await handleResponse(
    response,
    'Login failed'
  )

  if (data.access_token) {
    saveToken(data.access_token)
  }

  return data
}

// =========================================================
// GET CURRENT LOGGED-IN USER
// =========================================================

export async function getCurrentUser() {
  const response = await fetch(`${BASE}/api/auth/me`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders()
    }
  })

  return handleResponse(
    response,
    'Could not retrieve user information'
  )
}

// =========================================================
// CHECK LOGIN STATUS
// =========================================================

export function isUserLoggedIn() {
  return Boolean(getToken())
}

// =========================================================
// GET AUTHENTICATED ANALYSIS HISTORY
//
// Patient: Only their own analyses.
// Doctor: All patients' analyses.
// Permissions are enforced by the backend.
// =========================================================

export async function getAnalyses() {
  const response = await fetch(`${BASE}/api/analyses`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders()
    }
  })

  return handleResponse(
    response,
    'Could not retrieve analysis history'
  )
}

// =========================================================
// IMAGE ANALYSIS
// Pneumonia, Tuberculosis, Brain Tumour
// =========================================================

export async function analyzeImage(file, modality, task) {
  const body = new FormData()

  body.append('file', file)
  body.append('modality', modality)
  body.append('task', task)

  const response = await fetch(`${BASE}/api/analyze`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders()
    },
    body
  })

  return handleResponse(
    response,
    'Analysis request failed'
  )
}

// =========================================================
// STROKE MRI ANALYSIS
// Requires DWI + ADC NIfTI files
// =========================================================

export async function analyzeStroke(dwiFile, adcFile) {
  const body = new FormData()

  body.append('dwi_file', dwiFile)
  body.append('adc_file', adcFile)

  const response = await fetch(`${BASE}/api/analyze-stroke`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders()
    },
    body
  })

  return handleResponse(
    response,
    'Stroke MRI analysis failed'
  )
}

// =========================================================
// DOWNLOAD STROKE SEGMENTATION
// =========================================================

export async function downloadStrokeSegmentation(downloadUrl) {
  if (!downloadUrl) {
    throw new Error('Segmentation download is not available')
  }

  const response = await fetch(`${BASE}${downloadUrl}`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders()
    }
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))

    throw new Error(
      data.detail || 'Could not download stroke segmentation'
    )
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = 'MedVisionAI-Stroke-Segmentation.nii.gz'

  document.body.appendChild(a)
  a.click()
  a.remove()

  URL.revokeObjectURL(url)
}

// =========================================================
// PDF REPORT DOWNLOAD
//
// Sends only analysis_id.
// Backend checks patient ownership or doctor permissions.
// =========================================================

export async function downloadReport(analysisId) {
  const id = typeof analysisId === 'object'
    ? analysisId?.analysis_id ?? analysisId?.id
    : analysisId

  if (!Number.isInteger(Number(id)) || Number(id) <= 0) {
    throw new Error('A valid analysis ID is required to generate the report')
  }

  const response = await fetch(`${BASE}/api/reports/demo`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders()
    },
    body: JSON.stringify({
      analysis_id: Number(id)
    })
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))

    throw new Error(
      data.detail || 'Could not generate report'
    )
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = 'MedVisionAI-demo-report.pdf'

  document.body.appendChild(a)
  a.click()
  a.remove()

  URL.revokeObjectURL(url)
}
