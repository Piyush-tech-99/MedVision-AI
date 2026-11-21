
import { useEffect, useMemo, useState } from 'react'
import {
  Activity, Brain, FileImage, FileText, HeartPulse, LayoutDashboard,
  ShieldCheck, UploadCloud, X, LoaderCircle, AlertCircle, History,
  ChartNoAxesCombined, Settings, Info, ChevronRight, Download, ScanLine,
  Stethoscope, Clock3, Search, Menu, Image as ImageIcon, Sparkles,
  CheckCircle2, LockKeyhole
} from 'lucide-react'

import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid
} from 'recharts'

import {
  analyzeImage,
  analyzeStroke,
  downloadReport,
  downloadStrokeSegmentation
} from './services/api'

const tasks = {
  'Chest X-ray': [
    'Pneumonia screening',
    'Tuberculosis screening'
  ],
  'Brain MRI': [
    'Brain tumour screening',
    'Stroke screening'
  ]
}

const CHART_COLORS = ['#3978d5', '#20a779', '#e5a348', '#8b70ce', '#e47777']

const chartTooltipStyle = {
  border: '1px solid #e8edf4',
  borderRadius: '10px',
  fontSize: '12px',
  boxShadow: '0 5px 20px rgba(30,50,80,0.08)'
}

const nav = [
  { id: 'dashboard', label: 'Home', icon: LayoutDashboard, group: 'WORKSPACE' },
  { id: 'analysis', label: 'New Analysis', icon: ScanLine, group: 'WORKSPACE' },
  { id: 'history', label: 'Analysis History', icon: History, group: 'WORKSPACE' },
  { id: 'analytics', label: 'Analytics', icon: ChartNoAxesCombined, group: 'INSIGHTS' },
  { id: 'reports', label: 'Reports', icon: FileText, group: 'INSIGHTS' },
  { id: 'models', label: 'Model Information', icon: Brain, group: 'SYSTEM' },
  { id: 'settings', label: 'Settings', icon: Settings, group: 'SYSTEM' }
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [modality, setModality] = useState('Chest X-ray')
  const [task, setTask] = useState(tasks['Chest X-ray'][0])

  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')

  const [dwiFile, setDwiFile] = useState(null)
  const [adcFile, setAdcFile] = useState(null)

  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('medvision-history') || '[]')
    } catch {
      return []
    }
  })

  const [search, setSearch] = useState('')
  const [mobileNav, setMobileNav] = useState(false)

  // Persistent guest token for this browser workspace.
  const [guestToken] = useState(() => {
    const storageKey = 'medvision-guest-token'
    let token = localStorage.getItem(storageKey)

    if (!token) {
      token = globalThis.crypto?.randomUUID
        ? globalThis.crypto.randomUUID()
        : `mv-${Date.now()}-${Math.random().toString(36).slice(2)}`

      localStorage.setItem(storageKey, token)
    }

    return token
  })

  const isStrokeWorkflow =
    modality === 'Brain MRI' && task === 'Stroke screening'

  useEffect(() => {
    localStorage.setItem('medvision-history', JSON.stringify(history))
  }, [history])

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  function clearImageSelection() {
    setFile(null)
    setPreview('')
  }

  function chooseModality(value) {
    setModality(value)
    setTask(tasks[value][0])
    setResult(null)
    setError('')
    clearImageSelection()
    setDwiFile(null)
    setAdcFile(null)
  }

  function handleTaskChange(value) {
    setTask(value)
    setResult(null)
    setError('')
    clearImageSelection()
    setDwiFile(null)
    setAdcFile(null)
  }

  function onFile(e) {
    const selected = e.target.files?.[0]
    e.target.value = ''

    setError('')
    setResult(null)

    if (!selected) return

    if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) {
      setError('Please choose a JPG, PNG or WEBP image.')
      return
    }

    if (selected.size > 15 * 1024 * 1024) {
      setError('File is larger than 15 MB.')
      return
    }

    if (preview) URL.revokeObjectURL(preview)

    setFile(selected)
    setPreview(URL.createObjectURL(selected))
  }

  function onMriFile(e, type) {
    const selected = e.target.files?.[0]
    e.target.value = ''

    setError('')
    setResult(null)

    if (!selected) return

    const lowerName = selected.name.toLowerCase()
    const validExtension =
      lowerName.endsWith('.nii') || lowerName.endsWith('.nii.gz')

    if (!validExtension) {
      setError('Please select a NIfTI file (.nii or .nii.gz).')
      return
    }

    if (selected.size > 200 * 1024 * 1024) {
      setError('MRI file is larger than 200 MB.')
      return
    }

    if (type === 'dwi') {
      setDwiFile(selected)
    } else {
      setAdcFile(selected)
    }
  }

  async function runAnalysis() {
    setBusy(true)
    setError('')
    setResult(null)

    try {
      let data
      let record

      if (isStrokeWorkflow) {
        if (!dwiFile || !adcFile) {
          setError('Please upload both DWI and ADC MRI files.')
          return
        }

        data = await analyzeStroke(dwiFile, adcFile, guestToken)

        setResult(data)

        record = {
          id: Date.now(),
          analysis_code: data.analysis_code || null,
          date: new Date().toISOString(),
          modality: 'Brain MRI',
          task: 'Stroke screening',
          filename: `${dwiFile.name} + ${adcFile.name}`,
          status: data.status || 'ANALYSIS_COMPLETED',
          message: data.message,
          result: data.result,
          segmentation_download_url: data.segmentation_download_url
        }
      } else {
        if (!file) {
          setError('Upload an image first.')
          return
        }

        data = await analyzeImage(file, modality, task, guestToken)

        setResult(data)

        record = {
          id: Date.now(),
          analysis_code: data.analysis_code || null,
          date: new Date().toISOString(),
          modality,
          task,
          filename: file.name,
          status: data.status || 'DEMO_ONLY',
          message: data.message,
          result: data.result
        }
      }

      setHistory(old => [record, ...old].slice(0, 50))
    } catch (err) {
      setError(
        err.message ||
        'Could not connect to the backend. Is FastAPI running?'
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleStrokeDownload(url) {
    try {
      setError('')
      await downloadStrokeSegmentation(url)
    } catch (err) {
      setError(err.message || 'Could not download the segmentation file.')
    }
  }

  async function makeReport(record = null) {
    const source = record || {
      modality,
      task,
      filename: isStrokeWorkflow
        ? `${dwiFile?.name || 'DWI'} + ${adcFile?.name || 'ADC'}`
        : file?.name,
      analysis_code: result?.analysis_code || null,
      result: result?.result || {
        status: 'DEMO_ONLY',
        message: 'No prediction result available.'
      }
    }

    try {
      await downloadReport({
        modality: source.modality,
        task: source.task,
        filename: source.filename,
        analysis_code: source.analysis_code || null,
        result: source.result || {
          status: source.status,
          message: source.message
        }
      })
    } catch (err) {
      setError(err.message || 'Report could not be generated.')
    }
  }

  function openPage(id) {
    setPage(id)
    setMobileNav(false)
    setError('')
  }

  const filteredHistory = useMemo(
    () => history.filter(x =>
      `${x.analysis_code || ''} ${x.filename} ${x.modality} ${x.task}`
        .toLowerCase()
        .includes(search.toLowerCase())
    ),
    [history, search]
  )

  const currentTitle = nav.find(n => n.id === page)?.label || 'Home'

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark">
            <HeartPulse size={22} />
          </div>

          <div>
            <b>MedVision <span>AI</span></b>
            <small>IMAGING INTELLIGENCE</small>
          </div>

          <button
            className="mobile-close"
            onClick={() => setMobileNav(false)}
          >
            <X size={18} />
          </button>
        </div>

        {['WORKSPACE', 'INSIGHTS', 'SYSTEM'].map(group => (
          <div className="nav-group" key={group}>
            <div className="nav-label">{group}</div>

            {nav.filter(n => n.group === group).map(item => (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? 'active' : ''}`}
                onClick={() => openPage(item.id)}
              >
                <item.icon size={17} />
                <span>{item.label}</span>
                {item.id === 'reports' && (
                  <span className="nav-count">PDF</span>
                )}
              </button>
            ))}
          </div>
        ))}

        <div className="sidebar-bottom">
          <div className="status-line"><i /> Prototype environment</div>
          <small>Academic demonstration · v1.1</small>
          <div className="privacy-note">
            <LockKeyhole size={14} /> Local demo workspace
          </div>
        </div>
      </aside>

      {mobileNav && (
        <button
          className="nav-scrim"
          onClick={() => setMobileNav(false)}
          aria-label="Close navigation"
        />
      )}

      <main className="main-area">
        <header className="topbar">
          <div className="top-left">
            <button
              className="hamburger"
              onClick={() => setMobileNav(true)}
            >
              <Menu />
            </button>

            <div>
              <span className="eyebrow">MEDICAL IMAGING WORKSPACE</span>
              <h1>{currentTitle}</h1>
            </div>
          </div>

          <div className="top-actions">
            <span className="demo-pill">
              <ShieldCheck size={14} /> Academic demo
            </span>
            <div className="avatar">MV</div>
          </div>
        </header>

        {error && (
          <div className="global-error">
            <AlertCircle size={16} />
            {error}
            <button onClick={() => setError('')}>
              <X size={15} />
            </button>
          </div>
        )}

        {page === 'dashboard' && (
          <Dashboard history={history} onNavigate={openPage} />
        )}

        {page === 'analysis' && (
          <AnalysisPage
            modality={modality}
            task={task}
            file={file}
            preview={preview}
            result={result}
            busy={busy}
            isStrokeWorkflow={isStrokeWorkflow}
            dwiFile={dwiFile}
            adcFile={adcFile}
            chooseModality={chooseModality}
            onFile={onFile}
            onMriFile={onMriFile}
            setTask={handleTaskChange}
            runAnalysis={runAnalysis}
            makeReport={makeReport}
            setFile={setFile}
            setPreview={setPreview}
            setResult={setResult}
            setDwiFile={setDwiFile}
            setAdcFile={setAdcFile}
            onStrokeDownload={handleStrokeDownload}
          />
        )}

        {page === 'history' && (
          <HistoryPage
            history={filteredHistory}
            search={search}
            setSearch={setSearch}
            onReport={makeReport}
          />
        )}

        {page === 'analytics' && <AnalyticsPage history={history} />}

        {page === 'reports' && (
          <ReportsPage history={history} onReport={makeReport} />
        )}

        {page === 'models' && <ModelsPage />}

        {page === 'settings' && <SettingsPage />}

        <footer className="app-footer">
          <span>MedVision AI</span>
          <i>•</i> Academic prototype <i>•</i> Not for clinical use
          <span className="footer-right">
            Built for medical-imaging research and learning
          </span>
        </footer>
      </main>
    </div>
  )
}

function PageIntro({ eyebrow, title, desc, action }) {
  return (
    <div className="page-intro">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        <p>{desc}</p>
      </div>
      {action}
    </div>
  )
}

function Dashboard({ history, onNavigate }) {
  return (
    <div className="page-content">
      <section className="hero-banner">
        <div className="hero-copy">
          <span className="hero-kicker">
            <Sparkles size={13} /> AI-ASSISTED IMAGING WORKFLOW
          </span>
          <h2>See more in every scan.</h2>
          <p>
            A structured workspace for medical image review,
            explainability research and report generation.
          </p>
          <button
            className="hero-button"
            onClick={() => onNavigate('analysis')}
          >
            Start new analysis <ChevronRight size={16} />
          </button>
        </div>

        <div className="hero-graphic">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="scan-symbol">
            <Brain size={54} />
            <Activity size={27} />
          </div>
          <span className="graphic-tag">IMAGE INTELLIGENCE</span>
        </div>
      </section>

      <div className="stats-grid">
        <Stat icon={FileImage} label="Analyses processed" value={history.length} note="This browser workspace" />
        <Stat icon={FileText} label="Reports available" value={history.length} note="Demo PDF reports" />
        <Stat icon={Brain} label="Active modalities" value="02" note="X-ray and MRI workflow" />
        <Stat icon={ShieldCheck} label="System status" value="Connected" note="Backend model workflows" />
      </div>

      <div className="dashboard-grid">
        <section className="content-card modality-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">IMAGING LIBRARY</span>
              <h3>Choose a modality</h3>
              <p>Start with one of the currently prepared workflows.</p>
            </div>
            <span className="live-tag">2 AVAILABLE</span>
          </div>

          <div className="modality-grid">
            <ModalityTile
              icon={FileImage}
              title="Chest X-ray"
              sub="Pneumonia · Tuberculosis"
              onClick={() => onNavigate('analysis')}
            />
            <ModalityTile
              icon={Brain}
              title="Brain MRI"
              sub="Tumour · Stroke research"
              onClick={() => onNavigate('analysis')}
            />
            <ModalityTile icon={ScanLine} title="CT Scan" sub="Planned workflow" soon />
            <ModalityTile icon={Activity} title="Ultrasound" sub="Planned workflow" soon />
          </div>
        </section>

        <section className="content-card quick-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">QUICK ACCESS</span>
              <h3>Workspace tools</h3>
              <p>Continue with your research workflow.</p>
            </div>
          </div>

          <QuickLink icon={ScanLine} title="New scan analysis" desc="Upload and validate a scan" onClick={() => onNavigate('analysis')} />
          <QuickLink icon={History} title="Analysis history" desc="Review saved sessions" onClick={() => onNavigate('history')} />
          <QuickLink icon={ChartNoAxesCombined} title="Model information" desc="Review model readiness and limits" onClick={() => onNavigate('models')} />
        </section>
      </div>

      <section className="content-card recent-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">RECENT ACTIVITY</span>
            <h3>Latest analyses</h3>
          </div>
          <button className="text-button" onClick={() => onNavigate('history')}>
            View all <ChevronRight size={15} />
          </button>
        </div>

        {history.length
          ? <HistoryTable items={history.slice(0, 4)} />
          : <EmptyState icon={Clock3} title="No analyses yet" text="Your completed sessions will appear here." />
        }
      </section>

      <SafetyStrip />
    </div>
  )
}

function Stat({ icon: Icon, label, value, note }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={18} /></div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-note">{note}</div>
    </div>
  )
}

function ModalityTile({ icon: Icon, title, sub, onClick, soon }) {
  return (
    <button
      className={`modality-tile ${soon ? 'disabled-tile' : ''}`}
      onClick={onClick}
      disabled={soon}
    >
      <div className="tile-icon"><Icon size={22} /></div>
      <div>
        <b>{title}</b>
        <small>{sub}</small>
      </div>
      <span className={soon ? 'coming-tag' : 'ready-tag'}>
        {soon ? 'COMING SOON' : 'READY'}
      </span>
    </button>
  )
}

function QuickLink({ icon: Icon, title, desc, onClick }) {
  return (
    <button className="quick-link" onClick={onClick}>
      <span><Icon size={17} /></span>
      <div>
        <b>{title}</b>
        <small>{desc}</small>
      </div>
      <ChevronRight size={16} />
    </button>
  )
}

function AnalysisPage(p) {
  const strokeResult = p.result?.result
  const hasStrokeResult = p.isStrokeWorkflow && p.result?.status === 'ANALYSIS_COMPLETED'

  return (
    <div className="page-content">
      <PageIntro
        eyebrow="IMAGE REVIEW WORKFLOW"
        title="New scan analysis"
        desc="Select the modality, upload your scan and review the available research output."
        action={<span className="workflow-step">STEP 01 <i /> 03</span>}
      />

      <div className="analysis-layout">
        <section className="content-card upload-card">
          <div className="section-title">
            <span className="step-number">01</span>
            <div>
              <h3>Imaging modality</h3>
              <p>Select the type of medical scan.</p>
            </div>
          </div>

          <div className="modality-select-grid">
            <button
              className={`select-modality ${p.modality === 'Chest X-ray' ? 'chosen' : ''}`}
              onClick={() => p.chooseModality('Chest X-ray')}
            >
              <FileImage size={21} />
              <span><b>Chest X-ray</b><small>Thoracic imaging</small></span>
            </button>

            <button
              className={`select-modality ${p.modality === 'Brain MRI' ? 'chosen' : ''}`}
              onClick={() => p.chooseModality('Brain MRI')}
            >
              <Brain size={21} />
              <span><b>Brain MRI</b><small>Neurological imaging</small></span>
            </button>
          </div>

          <label className="form-label" htmlFor="analysis-task">
            Analysis task
          </label>

          <select
            className="form-select"
            id="analysis-task"
            value={p.task}
            onChange={e => p.setTask(e.target.value)}
          >
            {tasks[p.modality].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {p.isStrokeWorkflow ? (
            <>
              <div className="section-title upload-section-title">
                <span className="step-number">02</span>
                <div>
                  <h3>Upload brain MRI sequences</h3>
                  <p>Required formats: NIfTI (.nii or .nii.gz) · Maximum 200 MB per file</p>
                </div>
              </div>

              <div className="mri-upload-grid">
                <div className="mri-upload-card">
                  <div className="mri-upload-heading">
                    <Brain size={20} />
                    <div>
                      <b>DWI sequence</b>
                      <small>Diffusion-weighted imaging</small>
                    </div>
                  </div>

                  <label className="mri-file-input">
                    <UploadCloud size={22} />
                    <b>{p.dwiFile ? 'Replace DWI file' : 'Choose DWI file'}</b>
                    <span>.nii or .nii.gz</span>
                    <input
                      type="file"
                      accept=".nii,.nii.gz,application/gzip"
                      onChange={e => p.onMriFile(e, 'dwi')}
                    />
                  </label>

                  {p.dwiFile && (
                    <div className="mri-file-row">
                      <FileImage size={16} />
                      <span>{p.dwiFile.name}</span>
                      <button
                        type="button"
                        onClick={() => {
                          p.setDwiFile(null)
                          p.setResult(null)
                        }}
                        aria-label="Remove DWI file"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  )}
                </div>

                <div className="mri-upload-card">
                  <div className="mri-upload-heading">
                    <Activity size={20} />
                    <div>
                      <b>ADC sequence</b>
                      <small>Apparent diffusion coefficient</small>
                    </div>
                  </div>

                  <label className="mri-file-input">
                    <UploadCloud size={22} />
                    <b>{p.adcFile ? 'Replace ADC file' : 'Choose ADC file'}</b>
                    <span>.nii or .nii.gz</span>
                    <input
                      type="file"
                      accept=".nii,.nii.gz,application/gzip"
                      onChange={e => p.onMriFile(e, 'adc')}
                    />
                  </label>

                  {p.adcFile && (
                    <div className="mri-file-row">
                      <FileImage size={16} />
                      <span>{p.adcFile.name}</span>
                      <button
                        type="button"
                        onClick={() => {
                          p.setAdcFile(null)
                          p.setResult(null)
                        }}
                        aria-label="Remove ADC file"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="inline-note">
                <Info size={15} />
                Upload the matching DWI and ADC sequences from the same MRI study. Both are required by the stroke segmentation model.
              </div>

              <button
                className="primary-button full-button"
                disabled={!p.dwiFile || !p.adcFile || p.busy}
                onClick={p.runAnalysis}
              >
                {p.busy
                  ? <><LoaderCircle className="spin" size={17} /> Processing MRI...</>
                  : <><Activity size={17} /> Run stroke analysis</>
                }
              </button>
            </>
          ) : (
            <>
              <div className="section-title upload-section-title">
                <span className="step-number">02</span>
                <div>
                  <h3>Upload medical image</h3>
                  <p>Supported formats: JPG, PNG, WEBP · Maximum 15 MB</p>
                </div>
              </div>

              <label className="upload-drop">
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                  onChange={p.onFile}
                />

                {p.preview
                  ? <img src={p.preview} alt="Selected scan preview" />
                  : <>
                      <div className="drop-icon"><UploadCloud size={25} /></div>
                      <b>Click to browse your files</b>
                      <span>or drag and drop an image here</span>
                    </>
                }

                <small>Images are sent to the local academic backend for validation.</small>
              </label>

              {p.file && (
                <div className="selected-file">
                  <FileImage size={17} />
                  <span>{p.file.name}</span>
                  <small>{(p.file.size / 1024 / 1024).toFixed(2)} MB</small>
                  <button
                    onClick={() => {
                      p.setFile(null)
                      p.setPreview('')
                      p.setResult(null)
                    }}
                  >
                    <X size={15} />
                  </button>
                </div>
              )}

              <button
                className="primary-button full-button"
                disabled={!p.file || p.busy}
                onClick={p.runAnalysis}
              >
                {p.busy
                  ? <><LoaderCircle className="spin" size={17} /> Processing image...</>
                  : <><Activity size={17} /> Run analysis</>
                }
              </button>

              <div className="inline-note">
                <Info size={15} />
                Predictions appear only when a compatible trained model is installed and loaded by the backend.
              </div>
            </>
          )}
        </section>

        <div className="analysis-right">
          <section className="content-card preview-card">
            <div className="card-heading">
              <div>
                <span className="eyebrow">SCAN VIEWER</span>
                <h3>{p.isStrokeWorkflow ? 'MRI sequence files' : 'Original image'}</h3>
              </div>
              <span className="viewer-tag">
                {p.isStrokeWorkflow
                  ? (p.dwiFile && p.adcFile ? 'MRI FILES LOADED' : 'AWAITING FILES')
                  : (p.preview ? 'IMAGE LOADED' : 'NO IMAGE')
                }
              </span>
            </div>

            <div className="image-viewer">
              {p.isStrokeWorkflow ? (
                <div className="viewer-empty">
                  <Brain size={34} />
                  <b>Stroke MRI input</b>
                  <span>
                    {p.dwiFile && p.adcFile
                      ? 'Both DWI and ADC files are selected and ready for analysis.'
                      : 'Upload both DWI and ADC NIfTI files to continue.'
                    }
                  </span>
                </div>
              ) : p.preview ? (
                <img src={p.preview} alt="Uploaded scan" />
              ) : (
                <div className="viewer-empty">
                  <ImageIcon size={34} />
                  <b>Scan preview</b>
                  <span>Your uploaded image will appear here.</span>
                </div>
              )}
            </div>

            <div className="viewer-caption">
              <span><CheckCircle2 size={14} /> Input review</span>
              <span>{p.isStrokeWorkflow ? 'DWI + ADC' : 'Original · Unmodified'}</span>
            </div>
          </section>

          <section className="content-card output-card">
            <div className="card-heading">
              <div>
                <span className="eyebrow">ANALYSIS OUTPUT</span>
                <h3>Result summary</h3>
              </div>
              <span className="demo-label">RESEARCH MODE</span>
            </div>

            {p.result ? (
              p.isStrokeWorkflow ? (
                <div className="result-message">
                  {hasStrokeResult ? (
                    <>
                      <div className="success-panel">
                        <CheckCircle2 size={20} />
                        <div>
                          <b>Stroke segmentation completed</b>
                          <span>Research model output — not a medical diagnosis.</span>
                        </div>
                      </div>

                      <div className="result-detail">
                        <small>ANALYSIS ID</small>
                        <b>{p.result.analysis_code || 'Not available'}</b>
                      </div>

                      <div className="stroke-metrics-grid">
                        <div className="stroke-metric">
                          <small>PROCESSED SLICES</small>
                          <b>{strokeResult?.processed_slices ?? '—'}</b>
                        </div>
                        <div className="stroke-metric">
                          <small>SLICES WITH LESIONS</small>
                          <b>{strokeResult?.slices_with_predicted_lesions ?? '—'}</b>
                        </div>
                        <div className="stroke-metric">
                          <small>TOTAL LESION PIXELS</small>
                          <b>{strokeResult?.total_lesion_pixels?.toLocaleString?.() ?? strokeResult?.total_lesion_pixels ?? '—'}</b>
                        </div>
                        <div className="stroke-metric">
                          <small>LESION PIXEL PERCENTAGE</small>
                          <b>
                            {strokeResult?.lesion_pixel_percentage != null
                              ? `${Number(strokeResult.lesion_pixel_percentage).toFixed(3)}%`
                              : '—'
                            }
                          </b>
                        </div>
                      </div>

                      <div className="result-detail">
                        <small>SELECTED WORKFLOW</small>
                        <b>Brain MRI · Stroke screening</b>
                      </div>

                      <div className="result-detail">
                        <small>SEGMENTATION FILE</small>
                        <b>
                          {p.result.segmentation_download_url
                            ? 'Generated and saved by backend'
                            : 'Not available'
                          }
                        </b>
                      </div>

                      {p.result.segmentation_download_url && (
                        <button
                          className="outline-button full-button"
                          onClick={() => p.onStrokeDownload(p.result.segmentation_download_url)}
                        >
                          <Download size={16} /> Download stroke segmentation (.nii.gz)
                        </button>
                      )}

                      <button
                        className="outline-button full-button"
                        onClick={() => p.makeReport()}
                      >
                        <FileText size={16} /> Download PDF report
                      </button>
                    </>
                  ) : (
                    <div className="warning-panel">
                      <AlertCircle size={19} />
                      <div>
                        <b>Stroke analysis response received</b>
                        <span>
                          {p.result.message || 'The backend returned a response, but the expected completion status was not received.'}
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="result-detail">
                    <small>BACKEND STATUS</small>
                    <b>{p.result.status}</b>
                  </div>
                </div>
              ) : (
                <div className="result-message">
                  {p.result.result?.status === 'PREDICTION_GENERATED' ? (
                    <div className="success-panel">
                      <CheckCircle2 size={20} />
                      <div>
                        <b>Model output generated</b>
                        <span>Research classifier result — not a medical diagnosis.</span>
                      </div>
                    </div>
                  ) : (
                    <div className="warning-panel">
                      <AlertCircle size={19} />
                      <div>
                        <b>Trained model not available</b>
                        <span>
                          {p.result.result?.note ||
                            p.result.message ||
                            'The image was validated, but no prediction was generated.'}
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="result-detail">
                    <small>ANALYSIS ID</small>
                    <b>{p.result.analysis_code || 'Not available'}</b>
                  </div>

                  <div className="result-detail">
                    <small>SELECTED WORKFLOW</small>
                    <b>{p.result.task}</b>
                  </div>

                  <div className="result-detail">
                    <small>IMAGE VALIDATION</small>
                    <b>
                      {p.result.image?.valid
                        ? 'Image passed basic validation'
                        : 'Validation response received'}
                    </b>
                  </div>

                  {p.result.result?.status === 'PREDICTION_GENERATED' && (
                    <>
                      <div className="result-detail">
                        <small>MODEL PREDICTION</small>
                        <b>{p.result.result.prediction}</b>
                      </div>

                      <div className="result-detail">
                        <small>MODEL CONFIDENCE (NOT CLINICAL CERTAINTY)</small>
                        <b>
                          {p.result.result.confidence != null
                            ? `${(p.result.result.confidence * 100).toFixed(1)}%`
                            : '—'}
                        </b>
                      </div>
                    </>
                  )}

                  <div className="result-detail">
                    <small>BACKEND STATUS</small>
                    <b>{p.result.status}</b>
                  </div>

                  <button
                    className="outline-button full-button"
                    onClick={() => p.makeReport()}
                  >
                    <Download size={16} /> Download PDF report
                  </button>
                </div>
              )
            ) : (
              <EmptyState
                icon={Activity}
                title="Waiting for analysis"
                text="After upload, the backend analysis response will be displayed here."
              />
            )}
          </section>
        </div>
      </div>

      <div className="explainability-grid">
        <section className="content-card">
          <div className="card-heading">
            <div>
              <span className="eyebrow">EXPLAINABLE AI</span>
              <h3>Grad-CAM visualization</h3>
              <p>Model attention map and overlay preview.</p>
            </div>
            <span className="not-ready-tag">NOT CONNECTED</span>
          </div>

          <div className="gradcam-placeholder">
            {p.result?.gradcam_overlay ? (
              <img
                className="gradcam-result-image"
                src={p.result.gradcam_overlay}
                alt="Grad-CAM overlay generated from the trained model"
              />
            ) : (
              <div className="gradcam-frame">
                <Brain size={40} />
                <span>Grad-CAM</span>
              </div>
            )}

            <div>
              <b>
                {p.result?.gradcam_overlay
                  ? 'Model-generated Grad-CAM overlay'
                  : 'Grad-CAM unavailable'}
              </b>
              <p>
                {p.isStrokeWorkflow
                  ? 'The current stroke workflow returns a segmentation file. Grad-CAM is not part of this segmentation output.'
                  : p.result?.gradcam_overlay
                    ? 'This visualization is derived from model gradients. It is an explanation aid, not proof of a lesion or diagnosis.'
                    : 'A genuine Grad-CAM heatmap will appear here after a compatible CNN model is connected. No artificial heatmap is shown.'
                }
              </p>
            </div>
          </div>
        </section>

        <ClinicalGuidance
          task={p.task}
          result={p.result}
          isStrokeWorkflow={p.isStrokeWorkflow}
        />
      </div>

      <SafetyStrip />
    </div>
  )
}

/* DISEASE-SPECIFIC PRECAUTIONARY GUIDANCE */

function ClinicalGuidance({ task, result, isStrokeWorkflow }) {
  const guidance = {
    'Pneumonia screening': {
      title: 'Pneumonia precautionary guidance',
      points: [
        'Consult a qualified doctor for clinical assessment and confirmation.',
        'Seek prompt medical attention for fever, persistent cough or breathing difficulty.',
        'Seek emergency care for severe breathlessness, bluish lips or confusion.',
        'Do not start antibiotics or other medication without medical advice.'
      ]
    },

    'Tuberculosis screening': {
      title: 'Tuberculosis precautionary guidance',
      points: [
        'Arrange a prompt evaluation with a qualified healthcare professional.',
        'A doctor may recommend sputum testing, chest imaging or additional investigations.',
        'Practise respiratory hygiene and wear a mask if experiencing a persistent cough.',
        'Do not start or stop tuberculosis medication without medical supervision.'
      ]
    },

    'Brain tumour screening': {
      title: 'Brain tumour precautionary guidance',
      points: [
        'Consult a neurologist or neurosurgeon for further clinical evaluation.',
        'A specialist may recommend additional MRI sequences or other investigations.',
        'Seek emergency care for seizures, sudden weakness, confusion or a severe worsening headache.',
        'A screening prediction does not confirm the presence of a brain tumour.'
      ]
    },

    'Stroke screening': {
      title: 'Stroke precautionary guidance',
      points: [
        'If stroke symptoms are present, seek emergency medical attention immediately, even if symptoms disappear.',
        'In India, call 112 for emergency assistance.',
        'Note the time when the person was last known to be well.',
        'Do not give food, drinks or medication unless directed by medical professionals.'
      ]
    }
  }

  const selectedGuidance = guidance[task]

  const hasClassifierPrediction =
    !isStrokeWorkflow &&
    result?.result?.status === 'PREDICTION_GENERATED'

  const hasStrokeResponse =
    isStrokeWorkflow &&
    Boolean(result)

  const hasAnalysisResponse =
    hasClassifierPrediction || hasStrokeResponse ||
    Boolean(result?.result?.status)

  return (
    <section className="content-card">
      <div className="card-heading">
        <div>
          <span className="eyebrow">CLINICAL CONTEXT</span>
          <h3>Precautionary guidance</h3>
          <p>
            General precautionary information for the selected screening workflow.
          </p>
        </div>
        <Stethoscope size={20} className="muted-icon" />
      </div>

      {!hasAnalysisResponse ? (
        <div className="guidance-box">
          <ShieldCheck size={19} />
          <div>
            <b>Awaiting analysis</b>
            <p>
              Upload a medical image and run the selected analysis
              to view its corresponding precautionary guidance.
            </p>
          </div>
        </div>
      ) : selectedGuidance ? (
        <>
          <div className="guidance-box">
            <ShieldCheck size={19} />
            <div>
              <b>{selectedGuidance.title}</b>
              <p>
                {isStrokeWorkflow
                  ? 'Stroke-related precautions. Segmentation output alone cannot establish a stroke diagnosis.'
                  : hasClassifierPrediction
                    ? `The model returned a screening prediction: ${result.result.prediction}. The following information is precautionary, not a treatment recommendation.`
                    : 'The analysis response was received. No confirmed clinical diagnosis can be made from this prototype output.'
                }
              </p>
            </div>
          </div>

          <div className="guidance-list">
            {selectedGuidance.points.map((point, index) => (
              <div className="guidance-item" key={index}>
                <span className="guidance-number">{index + 1}</span>
                <p>{point}</p>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="guidance-box">
          <Info size={19} />
          <div>
            <b>General precautionary guidance</b>
            <p>
              Consult a qualified healthcare professional for
              interpretation of medical imaging results.
            </p>
          </div>
        </div>
      )}

      <div className="guidance-disclaimer">
        <ShieldCheck size={17} />
        <div>
          <b>Research output only</b>
          <p>
            MedVision AI is an academic prototype and is not validated
            for clinical diagnosis. Its predictions and segmentation
            outputs must not be used to make treatment decisions.
            A qualified clinician must interpret medical images.
          </p>
        </div>
      </div>
    </section>
  )
}

function HistoryPage({ history, search, setSearch, onReport }) {
  return (
    <div className="page-content">
      <PageIntro
        eyebrow="WORKSPACE RECORDS"
        title="Analysis history"
        desc="Browse demo analysis sessions saved in this browser."
      />

      <section className="content-card table-card">
        <div className="table-toolbar">
          <div>
            <h3>All sessions</h3>
            <p>{history.length} record{history.length === 1 ? '' : 's'} found</p>
          </div>

          <div className="search-box">
            <Search size={16} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search Analysis ID, filename or modality"
            />
          </div>
        </div>

        {history.length
          ? <HistoryTable items={history} onReport={onReport} />
          : <EmptyState icon={History} title="No matching records" text="Run an analysis to add a session to this history." />
        }
      </section>

      <div className="inline-note">
        <Info size={15} />
        History is stored in this browser's local storage. Clearing browser data may remove these records.
      </div>
    </div>
  )
}

function HistoryTable({ items, onReport }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>SCAN / FILE</th>
            <th>ANALYSIS ID</th>
            <th>MODALITY</th>
            <th>ANALYSIS TASK</th>
            <th>DATE</th>
            <th>STATUS</th>
            {onReport && <th />}
          </tr>
        </thead>

        <tbody>
          {items.map(item => (
            <tr key={item.id}>
              <td>
                <div className="file-cell">
                  <span><FileImage size={16} /></span>
                  <b>{item.filename}</b>
                </div>
              </td>
              <td>
                <span className="analysis-id">
                  {item.analysis_code || '—'}
                </span>
              </td>
              <td>{item.modality}</td>
              <td>{item.task}</td>
              <td>{new Date(item.date).toLocaleString()}</td>
              <td><span className="status-chip">{item.status || 'DEMO_ONLY'}</span></td>
              {onReport && (
                <td>
                  <button
                    className="icon-action"
                    title="Download demo report"
                    onClick={() => onReport(item)}
                  >
                    <Download size={16} />
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ANALYTICS PAGE WITH REAL CHARTS */

function AnalyticsPage({ history }) {
  const total = history.length

  const completed = history.filter(item =>
    item.status === 'ANALYSIS_COMPLETED' ||
    item.result?.status === 'PREDICTION_GENERATED'
  ).length

  const otherSessions = total - completed

  const chestXray = history.filter(
    item => item.modality === 'Chest X-ray'
  ).length

  const brainMRI = history.filter(
    item => item.modality === 'Brain MRI'
  ).length

  const taskCounts = {}
  const predictionCounts = {}

  history.forEach(item => {
    const task = item.task || 'Other'
    taskCounts[task] = (taskCounts[task] || 0) + 1

    const prediction = item.result?.prediction

    if (
      prediction &&
      item.result?.status === 'PREDICTION_GENERATED'
    ) {
      predictionCounts[prediction] =
        (predictionCounts[prediction] || 0) + 1
    }
  })

  const modalityData = [
    { name: 'Chest X-ray', value: chestXray },
    { name: 'Brain MRI', value: brainMRI }
  ].filter(item => item.value > 0)

  const outcomeData = [
    { name: 'Completed outputs', value: completed },
    { name: 'Other saved sessions', value: otherSessions }
  ].filter(item => item.value > 0)

  const taskData = Object.entries(taskCounts).map(([name, count]) => ({
    name,
    sessions: count
  }))

  const predictionData = Object.entries(predictionCounts).map(([name, count]) => ({
    name,
    predictions: count
  }))

  const successPercentage = total
    ? Math.round((completed / total) * 100)
    : 0

  const hasHistory = total > 0
  const hasPredictions = predictionData.length > 0

  const panelStyle = {
    background: '#ffffff',
    border: '1px solid #e8edf4',
    borderRadius: '14px',
    padding: '22px',
    minWidth: 0,
    boxShadow: '0 2px 8px rgba(30,50,80,0.025)'
  }

  const headingStyle = {
    color: '#17243b',
    fontSize: '17px',
    fontWeight: 750,
    margin: '0 0 6px'
  }

  const descriptionStyle = {
    color: '#8290a4',
    fontSize: '12px',
    lineHeight: 1.6,
    margin: 0
  }

  const eyebrowStyle = {
    color: '#71819a',
    fontSize: '10px',
    fontWeight: 800,
    letterSpacing: '1.2px',
    display: 'block',
    marginBottom: '7px'
  }

  const chartHeight = {
    width: '100%',
    height: 270,
    marginTop: 18
  }

  return (
    <div className="page-content">
      <PageIntro
        eyebrow="WORKSPACE INSIGHTS"
        title="Analytics overview"
        desc="Visual insights into imaging activity, analysis outcomes and prediction history."
      />

      <div className="stats-grid analytics-stats">
        <Stat
          icon={Activity}
          label="Total sessions"
          value={total}
          note="Recorded analyses"
        />

        <Stat
          icon={CheckCircle2}
          label="Completed outputs"
          value={completed}
          note="Recognized completed outputs"
        />

        <Stat
          icon={FileImage}
          label="Chest X-ray"
          value={chestXray}
          note="Imaging sessions"
        />

        <Stat
          icon={Brain}
          label="Brain MRI"
          value={brainMRI}
          note="Imaging sessions"
        />
      </div>

      {!hasHistory ? (
        <section className="content-card">
          <EmptyState
            icon={ChartNoAxesCombined}
            title="No analytics available yet"
            text="Complete your first image analysis or stroke segmentation workflow. Your charts will automatically appear here."
          />
        </section>
      ) : (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 390px), 1fr))',
              gap: '20px',
              marginBottom: '20px'
            }}
          >
            <section style={panelStyle}>
              <div>
                <span style={eyebrowStyle}>IMAGING ACTIVITY</span>
                <h3 style={headingStyle}>Modality distribution</h3>
                <p style={descriptionStyle}>
                  Distribution of recorded sessions across imaging modalities.
                </p>
              </div>

              {modalityData.length ? (
                <div style={chartHeight}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={modalityData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="45%"
                        innerRadius={65}
                        outerRadius={95}
                        paddingAngle={4}
                        labelLine={false}
                        label={({ name, percent }) =>
                          `${name}: ${(percent * 100).toFixed(0)}%`
                        }
                      >
                        {modalityData.map((entry, index) => (
                          <Cell
                            key={entry.name}
                            fill={CHART_COLORS[index % CHART_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={chartTooltipStyle} />
                      <Legend verticalAlign="bottom" height={30} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <ChartEmpty text="No modality records available." />
              )}
            </section>

            <section style={panelStyle}>
              <div>
                <span style={eyebrowStyle}>ANALYSIS STATUS</span>
                <h3 style={headingStyle}>Session outcomes</h3>
                <p style={descriptionStyle}>
                  Completed outputs compared with other saved sessions.
                </p>
              </div>

              {outcomeData.length ? (
                <>
                  <div style={chartHeight}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={outcomeData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="45%"
                          innerRadius={65}
                          outerRadius={95}
                          paddingAngle={4}
                          labelLine={false}
                          label={({ percent }) =>
                            `${(percent * 100).toFixed(0)}%`
                          }
                        >
                          {outcomeData.map((entry, index) => (
                            <Cell
                              key={entry.name}
                              fill={index === 0 ? '#20a779' : '#8b9bb1'}
                            />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={chartTooltipStyle} />
                        <Legend verticalAlign="bottom" height={30} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  <p style={{
                    textAlign: 'center',
                    color: '#71819a',
                    fontSize: '12px',
                    margin: '0'
                  }}>
                    {successPercentage}% of sessions have a recognized completed output.
                  </p>
                </>
              ) : (
                <ChartEmpty text="No outcome records available." />
              )}
            </section>

            <section style={panelStyle}>
              <div>
                <span style={eyebrowStyle}>WORKFLOW INSIGHTS</span>
                <h3 style={headingStyle}>Task distribution</h3>
                <p style={descriptionStyle}>
                  Number of sessions recorded for each analysis task.
                </p>
              </div>

              {taskData.length ? (
                <div style={chartHeight}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={taskData}
                      margin={{ top: 15, right: 10, left: -15, bottom: 45 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="#edf1f6"
                      />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: '#71819a', fontSize: 10 }}
                        angle={-15}
                        textAnchor="end"
                        interval={0}
                        height={65}
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fill: '#71819a', fontSize: 11 }}
                      />
                      <Tooltip contentStyle={chartTooltipStyle} />
                      <Bar
                        dataKey="sessions"
                        name="Sessions"
                        fill="#3978d5"
                        radius={[6, 6, 0, 0]}
                        maxBarSize={55}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <ChartEmpty text="No task records available." />
              )}
            </section>

            <section style={panelStyle}>
              <div>
                <span style={eyebrowStyle}>PREDICTION INSIGHTS</span>
                <h3 style={headingStyle}>Prediction distribution</h3>
                <p style={descriptionStyle}>
                  Classification predictions actually returned by the backend.
                </p>
              </div>

              {hasPredictions ? (
                <div style={chartHeight}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={predictionData}
                      margin={{ top: 15, right: 10, left: -15, bottom: 45 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="#edf1f6"
                      />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: '#71819a', fontSize: 10 }}
                        angle={-15}
                        textAnchor="end"
                        interval={0}
                        height={65}
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fill: '#71819a', fontSize: 11 }}
                      />
                      <Tooltip contentStyle={chartTooltipStyle} />
                      <Bar
                        dataKey="predictions"
                        name="Predictions"
                        fill="#20a779"
                        radius={[6, 6, 0, 0]}
                        maxBarSize={55}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <ChartEmpty text="No classification predictions recorded yet. Stroke segmentation outputs are not counted as classification predictions." />
              )}
            </section>
          </div>

          <section style={{ ...panelStyle, marginBottom: '22px' }}>
            <div>
              <span style={eyebrowStyle}>ACTIVITY SUMMARY</span>
              <h3 style={headingStyle}>Workspace statistics</h3>
              <p style={descriptionStyle}>
                Summary calculated from the analysis history stored in this browser.
              </p>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '15px',
                marginTop: '22px'
              }}
            >
              <SummaryNumber label="Total sessions" value={total} />
              <SummaryNumber label="Completed outputs" value={completed} />
              <SummaryNumber label="Other saved sessions" value={otherSessions} />
              <SummaryNumber label="Classification predictions" value={predictionData.reduce((sum, item) => sum + item.predictions, 0)} />
            </div>
          </section>
        </>
      )}

      <section className="content-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">MODEL PERFORMANCE</span>
            <h3>Clinical evaluation metrics</h3>
            <p>
              Independent model evaluation results are separate from workspace activity statistics.
            </p>
          </div>

          <span className="not-ready-tag">AWAITING VALIDATION</span>
        </div>

        <div className="metric-empty">
          <ChartNoAxesCombined size={35} />
          <b>Clinical evaluation data not available</b>
          <p>
            Accuracy, sensitivity, specificity, F1-score and AUROC
            require evaluation on a held-out, patient-level test dataset.
            Workspace activity is not a substitute for clinical model validation.
          </p>
        </div>
      </section>

      <SafetyStrip />
    </div>
  )
}

function ChartEmpty({ text }) {
  return (
    <div
      style={{
        height: 250,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        color: '#8290a4',
        textAlign: 'center',
        fontSize: 12,
        padding: 20
      }}
    >
      <ChartNoAxesCombined size={30} />
      <span>{text}</span>
    </div>
  )
}

function SummaryNumber({ label, value }) {
  return (
    <div
      style={{
        background: '#f6f8fc',
        border: '1px solid #edf0f5',
        borderRadius: 10,
        padding: '16px'
      }}
    >
      <div style={{
        color: '#71819a',
        fontSize: 11,
        marginBottom: 7
      }}>
        {label}
      </div>
      <b style={{
        color: '#17243b',
        fontSize: 23,
        fontWeight: 750
      }}>
        {value}
      </b>
    </div>
  )
}

function ReportsPage({ history, onReport }) {
  return (
    <div className="page-content">
      <PageIntro
        eyebrow="DOCUMENT CENTRE"
        title="Reports"
        desc="Generate an academic demonstration PDF for a processed session."
      />

      <section className="content-card table-card">
        <div className="card-heading">
          <div>
            <h3>Available report records</h3>
            <p>Reports are generated on demand; they are not clinical documents.</p>
          </div>
          <FileText size={22} className="muted-icon" />
        </div>

        {history.length ? (
          <div className="report-list">
            {history.map(item => (
              <div className="report-row" key={item.id}>
                <div className="report-file-icon"><FileText size={20} /></div>
                <div className="report-meta">
                  <b>{item.filename}</b>
                  <span>
                    {item.modality} · {item.task} · {new Date(item.date).toLocaleDateString()}
                  </span>
                  <small>Analysis ID: {item.analysis_code || 'Not available'}</small>
                  <small>Demo report · Research output only</small>
                </div>
                <button className="outline-button" onClick={() => onReport(item)}>
                  <Download size={15} /> PDF
                </button>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={FileText} title="No reports to show" text="Complete an analysis first. You can then generate its PDF report here." />
        )}
      </section>

      <div className="inline-note">
        <Info size={15} />
        PDF report generation uses the existing backend report endpoint.
      </div>
    </div>
  )
}

function ModelsPage() {
  const models = [
    ['Chest X-ray · Pneumonia', 'Image classifier', 'Connected to the existing image prediction workflow'],
    ['Chest X-ray · Tuberculosis', 'Image classifier', 'Connected to the existing image prediction workflow'],
    ['Brain MRI · Tumour', 'Image classifier', 'Connected to the existing image prediction workflow'],
    ['Brain MRI · Stroke', 'MRI segmentation model', 'DWI + ADC input with NIfTI segmentation output']
  ]

  return (
    <div className="page-content">
      <PageIntro
        eyebrow="AI SYSTEM STATUS"
        title="Model information"
        desc="Overview of the model workflows currently integrated into MedVision AI."
      />

      <section className="content-card">
        <div className="card-heading">
          <div>
            <h3>Model registry</h3>
            <p>Model workflows configured in the backend.</p>
          </div>
          <span className="live-tag">4 WORKFLOWS</span>
        </div>

        <div className="model-list">
          {models.map(([name, type, desc]) => (
            <div className="model-row" key={name}>
              <div className="model-icon"><Brain size={19} /></div>
              <div className="model-copy">
                <b>{name}</b>
                <span>{type}</span>
                <small>{desc}</small>
              </div>
              <span className="ready-tag">INTEGRATED</span>
            </div>
          ))}
        </div>
      </section>

      <div className="content-card model-note">
        <ShieldCheck size={20} />
        <div>
          <b>Research and validation requirements</b>
          <p>
            Model integration does not establish clinical validity.
            Each model requires documented dataset provenance, patient-level
            train/validation/test splits, preprocessing consistency and
            independent evaluation. Outputs are for academic research only.
          </p>
        </div>
      </div>

      <SafetyStrip />
    </div>
  )
}

function SettingsPage() {
  return (
    <div className="page-content">
      <PageIntro
        eyebrow="PREFERENCES"
        title="Settings"
        desc="Basic information about this local academic prototype."
      />

      <section className="content-card settings-list">
        <div className="setting-row">
          <div>
            <b>Workspace name</b>
            <span>MedVision AI</span>
          </div>
          <span className="setting-value">Academic prototype</span>
        </div>

        <div className="setting-row">
          <div>
            <b>Data storage</b>
            <span>Analysis history is stored in browser local storage.</span>
          </div>
          <span className="setting-value">Local browser</span>
        </div>

        <div className="setting-row">
          <div>
            <b>Backend API</b>
            <span>FastAPI service at http://127.0.0.1:8001</span>
          </div>
          <span className="setting-value">Local development</span>
        </div>

        <div className="setting-row">
          <div>
            <b>Clinical use</b>
            <span>This application is not validated for diagnosis or treatment.</span>
          </div>
          <span className="not-ready-tag">NOT FOR CLINICAL USE</span>
        </div>
      </section>
    </div>
  )
}

function EmptyState({ icon: Icon, title, text }) {
  return (
    <div className="empty-state">
      <div><Icon size={26} /></div>
      <b>{title}</b>
      <p>{text}</p>
    </div>
  )
}

function SafetyStrip() {
  return (
    <div className="safety-strip">
      <ShieldCheck size={18} />
      <div>
        <b>Clinical safety notice</b>
        <span>
          MedVision AI is an academic prototype, not a diagnostic device.
          Outputs must not guide treatment decisions. Always consult a
          qualified healthcare professional.
        </span>
      </div>
    </div>
  )
}
