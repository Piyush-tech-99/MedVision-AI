const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

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
    body
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Analysis request failed')
  }

  return data
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
    body
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Stroke MRI analysis failed')
  }

  return data
}

// =========================================================
// DOWNLOAD STROKE SEGMENTATION
// =========================================================

export async function downloadStrokeSegmentation(downloadUrl) {
  if (!downloadUrl) {
    throw new Error('Segmentation download is not available')
  }

  const response = await fetch(`${BASE}${downloadUrl}`)

  if (!response.ok) {
    throw new Error('Could not download stroke segmentation')
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
// =========================================================

export async function downloadReport(payload) {
  const response = await fetch(`${BASE}/api/reports/demo`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error('Could not generate report')
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