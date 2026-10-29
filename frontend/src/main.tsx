import { useEffect, useMemo, useRef, useState } from 'react'
import ReactDOM from 'react-dom/client'
import './style.css'

const API = import.meta.env.VITE_API_BASE ?? ''
const MAX_UPLOAD_BYTES = 200 * 1024 * 1024

type SystemInfo = {
  cuda_available: boolean
  device_name: string | null
  model_name: string
  inference_device: string
  warning: string | null
}

type VideoInfo = {
  id: string
  original_filename: string
  file_size_bytes: number
  duration_seconds: number | null
  width: number | null
  height: number | null
  fps: number | null
  latest_status: string | null
  latest_job_id: string | null
  file_url: string
}

type JobInfo = {
  job_id: string
  video_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  frames_total: number | null
  frames_processed: number
  model_name: string
  settings: {
    sample_fps: number
    confidence_threshold: number
    image_size: number
    enable_tracking: boolean
  }
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  detections_count: number
  class_counts: Record<string, number>
  annotated_video_available: boolean
}

type EventInfo = {
  id: number
  timestamp_seconds: number
  frame_index: number
  class_id: number
  class_name: string
  confidence: number
  bbox: { x1: number; y1: number; x2: number; y2: number }
  track_id: number | null
  thumbnail_url: string | null
}

type ArtifactInfo = { artifact_type: string; url: string }
type Page = 'dashboard' | 'upload' | 'processing' | 'results'

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : message
    } catch {
      // Keep the readable status message when the server response is not JSON.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

function formatTime(seconds: number | null | undefined) {
  const value = Math.max(0, seconds ?? 0)
  const mins = Math.floor(value / 60)
  const secs = Math.floor(value % 60)
  const tenths = Math.floor((value % 1) * 10)
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${tenths}`
}

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [videos, setVideos] = useState<VideoInfo[]>([])
  const [video, setVideo] = useState<VideoInfo | null>(null)
  const [job, setJob] = useState<JobInfo | null>(null)
  const [events, setEvents] = useState<EventInfo[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [sampleFps, setSampleFps] = useState(2)
  const [confidence, setConfidence] = useState(0.4)
  const [imageSize, setImageSize] = useState(640)
  const [tracking, setTracking] = useState(true)
  const [classFilter, setClassFilter] = useState('all')
  const [previewMode, setPreviewMode] = useState<'original' | 'annotated'>('original')
  const [previewPlaybackError, setPreviewPlaybackError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loadingRecent, setLoadingRecent] = useState(true)
  const [objectUrl, setObjectUrl] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const originalRef = useRef<HTMLVideoElement>(null)
  const annotatedRef = useRef<HTMLVideoElement>(null)
  const pendingSeek = useRef<number | null>(null)

  const annotatedArtifact = artifacts.find((artifact) => artifact.artifact_type === 'annotated_video')
  const activeVideoUrl = video ? `${API}${video.file_url}` : ''
  const durationLabel = useMemo(() => formatTime(video?.duration_seconds), [video?.duration_seconds])

  async function refreshVideos() {
    const items = await api<VideoInfo[]>('/api/videos')
    setVideos(items)
  }

  useEffect(() => {
    let active = true
    Promise.all([api<SystemInfo>('/api/system'), api<VideoInfo[]>('/api/videos')])
      .then(([device, items]) => {
        if (!active) return
        setSystem(device)
        setVideos(items)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not connect to the local API.')
      })
      .finally(() => active && setLoadingRecent(false))

    const savedJobId = localStorage.getItem('scenetrace:lastJobId')
    if (savedJobId) {
      api<JobInfo>(`/api/jobs/${savedJobId}`)
        .then(async (savedJob) => {
          if (!active) return
          const savedVideo = await api<VideoInfo>(`/api/videos/${savedJob.video_id}`)
          if (!active) return
          setJob(savedJob)
          setVideo(savedVideo)
          if (savedJob.status === 'completed') setPage('results')
          else if (savedJob.status === 'queued' || savedJob.status === 'processing') setPage('processing')
        })
        .catch(() => localStorage.removeItem('scenetrace:lastJobId'))
    }
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!selectedFile) {
      setObjectUrl('')
      return
    }
    const url = URL.createObjectURL(selectedFile)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [selectedFile])

  useEffect(() => {
    if (!job || !['queued', 'processing'].includes(job.status)) return
    let active = true
    const poll = async () => {
      try {
        const updated = await api<JobInfo>(`/api/jobs/${job.job_id}`)
        if (!active) return
        setJob(updated)
        if (updated.status === 'completed') {
          setPage('results')
          void refreshVideos()
        } else if (updated.status === 'failed') {
          setError(updated.error || 'Analysis failed. Check the backend console for details.')
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not refresh job status.')
      }
    }
    void poll()
    const timer = window.setInterval(poll, 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [job?.job_id, job?.status])

  useEffect(() => {
    if (!job || job.status !== 'completed') return
    let active = true
    const query = new URLSearchParams({ limit: '500', sort: 'asc' })
    if (classFilter !== 'all') query.set('class_name', classFilter)
    Promise.all([
      api<EventInfo[]>(`/api/jobs/${job.job_id}/events?${query.toString()}`),
      api<ArtifactInfo[]>(`/api/jobs/${job.job_id}/artifacts`),
    ]).then(([loadedEvents, loadedArtifacts]) => {
      if (!active) return
      setEvents(loadedEvents)
      setArtifacts(loadedArtifacts)
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : 'Could not load analysis results.')
    })
    return () => { active = false }
  }, [job?.job_id, job?.status, classFilter])

  function validateFile(file: File) {
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!['mp4', 'mov', 'avi'].includes(extension ?? '')) {
      setError('Choose an MP4, MOV, or AVI video file.')
      return false
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError('This video is larger than the 200 MB upload limit.')
      return false
    }
    setError('')
    setSelectedFile(file)
    setPage('upload')
    return true
  }

  function onFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) validateFile(file)
    event.target.value = ''
  }

  async function startAnalysis() {
    if (!selectedFile) return
    setBusy(true)
    setError('')
    setNotice('Uploading video to local storage…')
    try {
      const body = new FormData()
      body.append('file', selectedFile)
      const uploaded = await api<VideoInfo>('/api/videos', { method: 'POST', body })
      setVideo(uploaded)
      setNotice('Starting analysis…')
      const accepted = await api<{ job_id: string; status: string }>('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: uploaded.id,
          sample_fps: sampleFps,
          confidence_threshold: confidence,
          image_size: imageSize,
          enable_tracking: tracking,
        }),
      })
      const firstStatus = await api<JobInfo>(`/api/jobs/${accepted.job_id}`)
      setJob(firstStatus)
      localStorage.setItem('scenetrace:lastJobId', accepted.job_id)
      setPage('processing')
      setNotice('')
      setSelectedFile(null)
      await refreshVideos()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start video analysis.')
      setNotice('')
    } finally {
      setBusy(false)
    }
  }

  async function openJob(jobId: string) {
    setError('')
    try {
      const loadedJob = await api<JobInfo>(`/api/jobs/${jobId}`)
      const loadedVideo = await api<VideoInfo>(`/api/videos/${loadedJob.video_id}`)
      setJob(loadedJob)
      setVideo(loadedVideo)
      setPreviewMode('original')
      setPreviewPlaybackError(false)
      setPage(loadedJob.status === 'completed' ? 'results' : 'processing')
      localStorage.setItem('scenetrace:lastJobId', jobId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open analysis.')
    }
  }

  function jumpTo(seconds: number) {
    pendingSeek.current = seconds
    const player = previewMode === 'annotated' ? annotatedRef.current : originalRef.current
    if (player && player.readyState >= 1) {
      player.currentTime = seconds
      player.play().catch(() => undefined)
      pendingSeek.current = null
    }
  }

  function applyPendingSeek(player: HTMLVideoElement | null) {
    if (player && pendingSeek.current !== null) {
      player.currentTime = pendingSeek.current
      pendingSeek.current = null
    }
  }

  function resetWorkspace() {
    setSelectedFile(null)
    setJob(null)
    setVideo(null)
    setEvents([])
    setArtifacts([])
    setError('')
    setNotice('')
    localStorage.removeItem('scenetrace:lastJobId')
    setPage('dashboard')
  }

  function beginNewAnalysis() {
    setJob(null)
    setVideo(null)
    setEvents([])
    setArtifacts([])
    setError('')
    localStorage.removeItem('scenetrace:lastJobId')
    setPage('dashboard')
  }

  const completedVideos = videos.filter((item) => item.latest_job_id)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={resetWorkspace} aria-label="Go to SceneTrace dashboard">
          <span>SceneTrace</span>
        </button>
        <div className="side-label">Workspace</div>
        <button className={`nav-item ${page === 'dashboard' || page === 'upload' ? 'active' : ''}`} onClick={resetWorkspace}>
          Overview
        </button>
        <button className={`nav-item ${page === 'results' || page === 'processing' ? 'active' : ''}`} onClick={() => job && openJob(job.job_id)} disabled={!job}>
          Current analysis
          {job && <span className={`nav-dot ${job.status}`} />}
        </button>
        <div className="sidebar-spacer" />
        <div className="sidebar-foot">Files are stored locally</div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="crumb"><span>Workspace</span><b>/</b><strong>{page === 'results' ? 'Analysis results' : page === 'processing' ? 'Processing' : page === 'upload' ? 'New analysis' : 'Overview'}</strong></div>
        </header>

        {error && <div className="toast error-toast" role="alert"><span>!</span>{error}<button onClick={() => setError('')}>×</button></div>}

        {page === 'dashboard' && (
          <section className="page-content dashboard-page">
            <div className="welcome-row">
              <div className="welcome-copy"><h1>Find objects in your videos.</h1><p className="lede">Upload a clip to view detected objects and jump to their timestamps.</p></div>
            </div>

            <div className="system-status" aria-live="polite">
              <span className={`system-status-dot ${system?.cuda_available ? 'available' : system ? 'fallback' : ''}`} />
              <strong>{system?.cuda_available ? 'GPU available' : system ? 'CPU mode' : 'Checking device'}</strong>
              {system?.device_name && <span>{system.device_name}</span>}
              <span className="status-separator">·</span>
              <span>{system?.model_name ?? 'yolo11n.pt'}</span>
              {system?.warning && <span className="system-warning">{system.warning}</span>}
            </div>

            <div className="section-title-row"><div><h2>Analyze a video</h2><p>MP4, MOV, or AVI · up to 200 MB</p></div></div>
            <button className="upload-launch" onClick={() => inputRef.current?.click()}>
              <span className="upload-copy"><strong>Choose a video</strong><small>Files stay on this device.</small></span>
              <span className="browse-button">Browse files</span>
            </button>
            <input ref={inputRef} type="file" accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.avi" hidden onChange={onFileChange} />

            <div className="section-title-row recent-heading"><div><h2>Recent videos</h2></div><button className="text-button" onClick={() => void refreshVideos()}>Refresh</button></div>
            <div className="recent-list">
              {loadingRecent && <div className="empty-row">Loading local library…</div>}
              {!loadingRecent && completedVideos.length === 0 && <div className="empty-row"><strong>No analyses yet</strong><p>Your recent videos and jobs will appear here.</p></div>}
              {completedVideos.slice(0, 6).map((item) => (
                <button className="video-row" key={item.id} onClick={() => item.latest_job_id && void openJob(item.latest_job_id)}>
                  <span className="file-icon">Video</span>
                  <span className="video-row-main"><strong>{item.original_filename}</strong><small>{formatTime(item.duration_seconds)} · {formatSize(item.file_size_bytes)} · {item.width} × {item.height}</small></span>
                  <span className={`status-chip ${item.latest_status ?? 'idle'}`}><i />{item.latest_status ?? 'uploaded'}</span>
                </button>
              ))}
            </div>
            <div className="footnote">Sampling can miss brief appearances. Track IDs may change between frames.</div>
          </section>
        )}

        {page === 'upload' && (
          <section className="page-content upload-page">
            <button className="back-link" onClick={() => { setPage('dashboard'); setError('') }}>← <span>Back to overview</span></button>
            <h1 className="page-heading">New video analysis</h1><p className="page-subtitle">Choose how frames are sampled and detected.</p>
            <div className="upload-layout">
              <div className="upload-main-card">
                <div className="card-heading"><div><h2>Source video</h2><p>Your source remains in local storage.</p></div><button className="change-file" onClick={() => inputRef.current?.click()}>Change file</button></div>
                <input ref={inputRef} type="file" accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.avi" hidden onChange={onFileChange} />
                {selectedFile && <>
                  <div className="local-preview">{objectUrl && <video src={objectUrl} controls muted playsInline />}</div>
                  <div className="selected-file"><span className="file-icon">Video</span><div><strong>{selectedFile.name}</strong><small>{formatSize(selectedFile.size)} · Ready to analyze</small></div><span className="ready-check">✓</span></div>
                </>}
                <div className="settings-divider" />
                <div className="card-heading settings-title"><div><h2>Detection settings</h2><p>These values apply to this analysis only.</p></div></div>
                <label className="setting-row"><span><strong>Sampling rate</strong><small>Frames analyzed per second</small></span><span className="range-control"><input type="range" min="0.5" max="5" step="0.5" value={sampleFps} onChange={(event) => setSampleFps(Number(event.target.value))} /><b>{sampleFps} <small>FPS</small></b></span></label>
                <label className="setting-row"><span><strong>Confidence threshold</strong><small>Minimum model score to include a detection</small></span><span className="range-control"><input type="range" min="0.1" max="0.9" step="0.05" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} /><b>{confidence.toFixed(2)}</b></span></label>
                <label className="setting-row"><span><strong>Inference image size</strong><small>Lower size may reduce memory use</small></span><select className="select-input" value={imageSize} onChange={(event) => setImageSize(Number(event.target.value))}><option value={640}>640 px · Recommended</option><option value={480}>480 px · Lower memory</option></select></label>
                <label className="setting-row tracking-row"><span><strong>Object tracking</strong><small>Best-effort IDs can switch or disappear</small></span><input className="toggle" type="checkbox" checked={tracking} onChange={(event) => setTracking(event.target.checked)} /></label>
                <div className="analysis-action"><div>Model: <strong>{system?.model_name ?? 'yolo11n.pt'}</strong> · stored locally</div><button className="primary-button" disabled={!selectedFile || busy} onClick={() => void startAnalysis()}>{busy ? 'Starting…' : 'Analyze video'}</button></div>
                {notice && <div className="inline-notice">{notice}</div>}
              </div>
            </div>
          </section>
        )}

        {page === 'processing' && job && (
          <section className="page-content processing-page">
            <h1 className="page-heading">{job.status === 'queued' ? 'Waiting to start' : job.status === 'failed' ? 'Analysis failed' : 'Processing video'}</h1><p className="page-subtitle">{job.status === 'queued' ? 'The local worker will start shortly.' : job.status === 'failed' ? 'The analysis could not be completed.' : 'Sampling frames and detecting objects.'}</p>
            <div className="processing-card">
              <div className="processing-info"><div className="processing-file-title">{video?.original_filename ?? 'Video analysis'}</div><div className="processing-state"><span className={`state-pulse ${job.status}`} />{job.status === 'queued' ? 'Queued' : job.status === 'failed' ? 'Failed' : 'Processing'}<span className="processing-percent">{Math.round(job.progress)}%</span></div><div className="progress-track"><span style={{ width: `${job.progress}%` }} /></div><div className="progress-caption"><span>{job.frames_processed} frames processed</span><span>{job.frames_total ?? '—'} estimated</span></div>
                <div className="processing-detail-grid"><div><span>Model</span><strong>{job.model_name}</strong></div><div><span>Sampling rate</span><strong>{job.settings.sample_fps} frames/sec</strong></div><div><span>Image size</span><strong>{job.settings.image_size}px</strong></div><div><span>Device</span><strong>{system?.inference_device ?? 'Local'}</strong></div></div>
                {job.error && <div className="job-error">{job.error}</div>}
                {job.status === 'completed' && <button className="primary-button full-button" onClick={() => setPage('results')}>View results <span>→</span></button>}
              </div>
            </div>
            <p className="processing-note">This analysis runs on your device.</p>
          </section>
        )}

        {page === 'results' && job && video && (
          <section className="page-content results-page">
            <div className="results-header"><div><button className="back-link" onClick={() => setPage('dashboard')}>← <span>Library</span></button><div className="result-status">Analysis complete · {job.job_id.slice(0, 8)}</div><h1 className="page-heading">{video.original_filename}</h1><p className="page-subtitle">Sampled at {job.settings.sample_fps} frames per second · {job.model_name}</p></div><button className="secondary-button" onClick={beginNewAnalysis}>New analysis</button></div>
            <div className="summary-grid"><div className="summary-card"><span>Video duration</span><strong>{durationLabel}</strong><small>Source length</small></div><div className="summary-card"><span>Sampled frames</span><strong>{job.frames_processed}<i> / {job.frames_total ?? job.frames_processed}</i></strong><small>Frames analyzed</small></div><div className="summary-card accent-summary"><span>Detections</span><strong>{job.detections_count.toLocaleString()}</strong><small>Model detections</small></div><div className="summary-card"><span>Object classes</span><strong>{Object.keys(job.class_counts).length}</strong><small>Unique detected classes</small></div></div>
            <div className="results-layout">
              <div className="results-main-column">
                <div className="player-card"><div className="player-topline"><div><strong>{previewMode === 'annotated' ? 'Annotated preview' : 'Original video'}</strong></div><div className="player-toggle"><button className={previewMode === 'original' ? 'selected' : ''} onClick={() => { setPreviewPlaybackError(false); setPreviewMode('original') }}>Original</button><button className={previewMode === 'annotated' ? 'selected' : ''} disabled={!annotatedArtifact} onClick={() => { setPreviewPlaybackError(false); setPreviewMode('annotated') }}>Annotated</button></div></div>
                  <div className="video-frame">
                    {previewMode === 'original' ? <video ref={originalRef} src={activeVideoUrl} controls playsInline onLoadedMetadata={(event) => applyPendingSeek(event.currentTarget)} /> : annotatedArtifact && !previewPlaybackError ? <video ref={annotatedRef} src={`${API}${annotatedArtifact.url}`} controls playsInline onError={() => setPreviewPlaybackError(true)} onLoadedMetadata={(event) => applyPendingSeek(event.currentTarget)} /> : <div className="no-preview"><span>▧</span><strong>Preview unavailable</strong><p>Detection events are saved; this browser could not play the annotated video.</p></div>}
                  </div><div className="player-foot"><span><i className="green-mini-dot" /> {previewMode === 'original' ? 'Source video' : 'Sampled frame preview'}</span><span>{video.width} × {video.height} <b>·</b> {durationLabel}</span></div>
                </div>
                <div className="class-card"><div className="card-heading"><div><h2>Detections by class</h2></div><span className="count-caption">{job.detections_count} total</span></div>
                  {Object.keys(job.class_counts).length === 0 ? <div className="no-events">No objects were detected above this confidence threshold.</div> : <div className="class-list">{Object.entries(job.class_counts).sort((a, b) => b[1] - a[1]).map(([name, count]) => <button className={`class-row ${classFilter === name ? 'class-selected' : ''}`} key={name} onClick={() => setClassFilter(classFilter === name ? 'all' : name)}><span className="class-name">{name}</span><span className="class-bar"><i style={{ width: `${Math.max(4, count / Math.max(...Object.values(job.class_counts)) * 100)}%` }} /></span><strong>{count}</strong></button>)}</div>}
                </div>
              </div>
              <aside className="event-panel"><div className="event-panel-head"><div><h2>Event timeline <span>{events.length}</span></h2></div><select className="filter-select" value={classFilter} onChange={(event) => setClassFilter(event.target.value)}><option value="all">All classes</option>{Object.keys(job.class_counts).sort().map((name) => <option key={name} value={name}>{name}</option>)}</select></div>
                <div className="timeline-meta"><span>Sorted by time</span><span>Select an event to seek</span></div>
                <div className="event-list">{events.length === 0 ? <div className="event-empty"><span>◷</span><strong>No events in this view</strong><p>Try another class filter or lower the confidence threshold on a new analysis.</p></div> : events.map((event) => <button className="event-card" key={event.id} onClick={() => jumpTo(event.timestamp_seconds)}><span className="event-thumb">{event.thumbnail_url ? <img src={`${API}${event.thumbnail_url}`} alt="" loading="lazy" /> : <span>▧</span>}<i>▶</i></span><span className="event-details"><strong>{event.class_name}</strong><small>{(event.confidence * 100).toFixed(0)}% model score{event.track_id !== null ? ` · ID ${event.track_id}` : ''}</small><span className="event-time">◷ {formatTime(event.timestamp_seconds)}</span></span><span className="event-jump">↗</span></button>)}</div>
                <div className="tracking-note"><span>ⓘ</span> Confidence is a model score, not a probability of truth. Track IDs can change or disappear.</div>
              </aside>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
