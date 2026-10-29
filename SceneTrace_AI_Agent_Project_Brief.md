# SceneTrace --- AI-Powered Video Intelligence and Search System

## Implementation Brief for Claude / Coding Agent

**Document purpose:** This is the source-of-truth specification for
building the first demonstrable version of SceneTrace. Read it fully
before writing code. Build a working MVP, not an overengineered
production platform.

---

## 1. Project Summary

### Project title

**SceneTrace: AI-Powered Video Intelligence and Search System**

### One-line description

SceneTrace lets a user upload a recorded video, detects and tracks
common objects using a pretrained computer-vision model, and creates a
searchable timeline so the user can jump directly to moments where those
objects appear.

### The first demo should prove

1.  A user can upload a local video file through a web interface.
2.  The backend processes the video using a pretrained model.
3.  The app shows detection results and a processed preview.
4.  The app builds a timestamped list of detected objects/events.
5.  A user can filter events by object class and click an event to jump
    to its timestamp.

### Non-goals for the first version

Do **not** attempt to build all of the following in the MVP: - Train or
fine-tune any ML model. - Build a custom object-detection model or
dataset. - Guarantee real-time processing. - Analyze multiple live
camera streams. - Add facial recognition or identify people. - Claim the
model understands every human action or event. - Build natural-language
video question answering. - Add a large local LLM. - Add cloud
deployment, payments, teams, or complex permissions. - Add Redis, Kafka,
Kubernetes, microservices, or a distributed processing architecture. -
Implement complex tracking re-identification across long occlusions.

Keep the MVP small, reliable, locally runnable, and easy to demonstrate.

---

## 2. Hardware and Operating Assumptions

Target machine: - Windows laptop (assume Windows 10/11 unless the
developer says otherwise). - NVIDIA RTX 3050 Laptop GPU with 4 GB
VRAM. - 16 GB system RAM. - Development and inference should work
locally.

### Resource strategy

- Use a small pretrained YOLO nano model.
- Start with inference image size 640; allow configuration to reduce
  it to 480 if memory or speed is a problem.
- Process one frame at a time (batch size 1).
- Sample video frames at a configurable rate, initially around 2
  frames per second. Do not process every frame by default.
- Do not load multiple large models concurrently.
- Detect whether CUDA is available and fall back to CPU with a clear
  UI message if not.
- Keep video files and derived artifacts on local disk.
- Never require an external AI API for the MVP.

Performance will vary with GPU, drivers, video codec, resolution, and
model configuration. Do not promise real-time performance or a fixed
processing time.

---

## 3. Recommended Technology Stack

Keep the architecture simple and modular.

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS (if installed and practical)
- Lucide React icons (optional)
- HTML5 video player

### Backend

- Python 3.11 recommended (verify package compatibility before
  choosing a version)
- FastAPI
- Uvicorn
- Pydantic
- OpenCV (`opencv-python`)
- Ultralytics package for pretrained YOLO inference and tracking
- SQLAlchemy 2.x for database access
- SQLite for the first MVP database

### Model

- A small pretrained YOLO nano checkpoint supported by the installed
  Ultralytics version, such as `yolo11n.pt` or a current compatible
  nano model.
- Download model weights automatically on first inference only if
  internet is available, or document how to place the weights locally.
- Do not train or fine-tune.
- Check the applicable model/library license before public or
  commercial distribution.

### Storage

- Local folders for original videos, annotated output videos, and
  thumbnails.
- SQLite for jobs and event metadata.
- Store paths relative to a configured data directory where possible.
- Add `.gitignore` rules for uploaded videos, generated videos,
  databases, virtual environments, model weights, and secrets.

### Do not add yet

- PostgreSQL unless there is a specific need.
- Redis/Celery unless background jobs prove necessary beyond the
  initial simple worker.
- Docker unless the user asks for it.
- Cloud storage or third-party APIs.

---

## 4. User Experience and Main Flow

### Primary user journey

1.  User opens the dashboard.
2.  User chooses a video file.
3.  Frontend validates basic file type and size.
4.  User clicks **Analyze Video**.
5.  Frontend uploads the file to the backend.
6.  Backend creates a job with status `queued` or `processing`.
7.  A local worker reads the video and samples frames.
8.  The pretrained detector finds supported object classes.
9.  A tracker assigns IDs when tracking is enabled and supported.
10. Backend records timestamped detections and generates an annotated
    video preview.
11. Job status becomes `completed` or `failed`.
12. Frontend displays a result page with:
    - Original video player
    - Processed/annotated preview
    - Processing summary
    - Object class counts
    - Search/filterable event timeline
    - Event cards with timestamps and thumbnails
13. Clicking an event seeks the relevant video player to that timestamp.

### Suggested demo video

Use a short, openly licensed or self-recorded clip with clearly visible
common objects such as people, cars, bicycles, or buses. Keep an example
clip available for repeatable demos, but do not commit large copyrighted
or personal videos to the repository.

---

## 5. MVP Feature Requirements

### P0 --- Must work for the first demo

#### A. Upload video

- Accept common video formats such as MP4, MOV, and AVI, subject to
  OpenCV/codec support.
- Configure a maximum upload size (for example, 200 MB) and return a
  friendly error when exceeded.
- Generate a unique ID for each analysis job.
- Use safe server-side filenames; never trust the original filename as
  a filesystem path.
- Validate the uploaded file as far as practical; extension alone is
  not a security guarantee.
- Store upload metadata: original display name, file size, duration,
  width, height, and creation time.

#### B. Video analysis

- Read video metadata using OpenCV.
- Sample frames at a configurable rate (default: 2 FPS).
- Run the pretrained detector on sampled frames.
- Save detections with:
  - Job ID
  - Timestamp in seconds
  - Frame index
  - Object class ID and class name
  - Confidence score
  - Bounding box coordinates
  - Track ID if tracking is enabled and available
- Use confidence threshold as a configuration value, initially around
  0.35--0.45.
- Draw bounding boxes and labels on sampled frames and generate an
  annotated preview video.
- Ensure output video writer uses a valid codec and dimensions. Handle
  failure gracefully.
- If the annotated video writer fails, still save event data and
  report the preview as unavailable rather than failing the whole job.

#### C. Object tracking

- Use a tracking method supported by the installed Ultralytics
  version, such as ByteTrack, only after confirming the chosen API
  works.
- Tracking is best-effort for the MVP. If tracker integration is
  unreliable, ship detection-only mode and keep track IDs optional.
- Never describe a track ID as a guaranteed identity of a
  person/object across all frames.

#### D. Event index

- Create an event entry for each sampled-frame detection, or group
  consecutive detections of the same track/class into an appearance
  interval if feasible.
- For the simplest MVP, use one event per detection and aggregate
  counts by class.
- Each event must include timestamp, class, confidence, bounding box,
  frame index, optional track ID, and thumbnail path.
- Generate a thumbnail for each event or use one thumbnail per event
  group to control storage.

#### E. Search and filtering

- Filter events by object class.
- Sort events by timestamp.
- Optional text search can match object class names; do not promise
  open-ended natural-language search.
- Selecting an event seeks the original video to the event timestamp.
- If annotated preview is available, let users toggle between original
  and annotated video.

#### F. Job status and errors

- Show upload, queued/processing, completed, and failed states.
- Provide basic progress (frames processed / estimated total sampled
  frames).
- Return useful errors for invalid files, unreadable videos, no
  frames, unsupported codecs, and inference failures.
- Avoid showing raw stack traces to the end user. Log details to the
  backend console.

### P1 --- Add only after P0 is reliable

- Tracking trails drawn over frames.
- Object entry/exit zones defined by user-drawn polygons.
- Export CSV/JSON event reports.
- A small analytics panel (class counts, detections over time).
- Search across multiple analyzed videos.
- Delete video/job functionality.
- Better event grouping into appearance intervals.

### P2 --- Future scope only

- Natural-language event search.
- Semantic scene summaries with a vision-language model.
- Automatic highlight reels.
- Multi-camera live streams.
- Advanced cross-camera tracking.
- Cloud deployment and multi-user accounts.

---

## 6. Architecture

Use a **modular monolith**, not microservices.

```text
SceneTrace/
  frontend/                  # React + TypeScript + Vite
  backend/
    app/
      main.py                # FastAPI app and route registration
      config.py              # Environment/configuration
      database.py            # SQLite engine and session setup
      models.py              # SQLAlchemy models
      schemas.py             # Pydantic request/response schemas
      api/
        health.py
        videos.py            # Upload, list, details, delete
        jobs.py              # Create/get analysis jobs and status
        events.py            # Query events and filters
      services/
        storage.py           # Safe local file handling
        video_reader.py      # Video metadata and frame sampling
        detector.py          # Pretrained model wrapper
        tracker.py           # Optional tracking wrapper
        analyzer.py          # Orchestrates inference and output generation
        job_manager.py       # Simple in-process job management for MVP
      workers/
        analysis_worker.py   # Executes a single analysis job
      utils/
        thumbnails.py
        video_writer.py
      data/                  # Runtime-generated files; gitignored
    tests/
    requirements.txt
    .env.example
  README.md
  .gitignore
```

The exact file layout may be simplified if that helps ship a working
MVP. Keep inference logic out of HTTP route functions.

### Request flow

```text
React UI
  -> POST /api/videos (upload)
  <- video_id + metadata

React UI
  -> POST /api/jobs { video_id, settings }
  <- job_id + status

React polls
  -> GET /api/jobs/{job_id}
  <- status + progress + result summary

React loads
  -> GET /api/jobs/{job_id}/events?class_name=person
  <- timestamped event list

React video player
  -> seeks to event.timestamp
```

Polling every 1--2 seconds is sufficient for the first version.
WebSockets are optional and should not block the MVP.

### Important job-execution guidance

- Never run a long video analysis synchronously inside the upload HTTP
  request.
- For the first local demo, a simple in-process background task/worker
  is acceptable.
- Limit concurrent inference jobs to **one** to avoid VRAM exhaustion.
- Persist job status and results in SQLite so the frontend can refresh
  without losing the job list.
- Document that an in-process worker is appropriate for a local
  prototype and is not a durable distributed queue.

---

## 7. Database Design

Use SQLite and SQLAlchemy.

### `videos`

- `id`: UUID/string primary key
- `original_filename`: string
- `stored_path`: string
- `file_size_bytes`: integer
- `duration_seconds`: float, nullable
- `width`: integer, nullable
- `height`: integer, nullable
- `fps`: float, nullable
- `created_at`: datetime

### `analysis_jobs`

- `id`: UUID/string primary key
- `video_id`: foreign key to videos
- `status`: `queued | processing | completed | failed`
- `progress`: float from 0 to 100
- `frames_total`: integer, nullable
- `frames_processed`: integer, default 0
- `error_message`: text, nullable
- `model_name`: string
- `settings_json`: text
- `started_at`: datetime, nullable
- `completed_at`: datetime, nullable
- `created_at`: datetime

### `events`

- `id`: integer or UUID primary key
- `job_id`: foreign key to analysis_jobs
- `timestamp_seconds`: float
- `frame_index`: integer
- `class_id`: integer
- `class_name`: string
- `confidence`: float
- `x1`, `y1`, `x2`, `y2`: float or integer
- `track_id`: integer, nullable
- `thumbnail_path`: string, nullable

### `artifacts`

- `id`: integer or UUID primary key
- `job_id`: foreign key to analysis_jobs
- `artifact_type`: `annotated_video | thumbnail | report`
- `stored_path`: string
- `created_at`: datetime

Use database indexes for `job_id`, `timestamp_seconds`, and `class_name`
where appropriate. Do not store video bytes or thumbnail bytes directly
in SQLite.

---

## 8. API Contract

Use `/api` as the common prefix. Return consistent JSON and appropriate
HTTP status codes.

### `GET /api/health`

Returns service health and whether the model has loaded. Do not load the
model just to answer health checks if that causes slow startup.

### `GET /api/system`

Returns: - CUDA available: boolean - Device name if available - Selected
model name - Inference device (`cuda:0` or `cpu`) - A short warning if
CPU fallback is active

### `POST /api/videos`

- Multipart upload field: `file`
- Validates and stores video
- Returns video ID and metadata

### `GET /api/videos`

- Lists uploaded videos and their latest analysis status

### `GET /api/videos/{video_id}`

- Returns video metadata and available artifacts

### `POST /api/jobs`

Request:

```json
{
  "video_id": "string",
  "sample_fps": 2,
  "confidence_threshold": 0.4,
  "image_size": 640,
  "enable_tracking": true
}
```

Returns:

```json
{
  "job_id": "string",
  "status": "queued"
}
```

### `GET /api/jobs/{job_id}`

Returns job status, progress, counts, error if failed, and artifact
availability.

### `GET /api/jobs/{job_id}/events`

Optional query parameters: - `class_name` - `min_confidence` - `limit` -
`offset` - `sort=asc|desc`

Returns events with timestamp, class, confidence, bounding box, optional
track ID, and thumbnail URL/path served safely by the backend.

### `GET /api/jobs/{job_id}/artifacts`

Returns URLs or metadata for annotated video, thumbnails, and reports.

### `DELETE /api/videos/{video_id}`

Optional P1. Delete files and related database records safely. If
implemented, confirm that a job is not processing before deleting.

### API conventions

- Use Pydantic schemas for responses.
- Validate IDs and settings.
- Never return arbitrary filesystem paths as public URLs.
- Serve only generated files under the configured data directory.
- Enable CORS only for the local frontend origin during development.
- Provide a consistent error structure, for example
  `{ "detail": "Human-readable explanation" }`.

---

## 9. Frontend Pages and Components

Build a polished but practical dashboard. Prefer clarity over visual
complexity.

### Page 1: Dashboard

- Project name and short explanation.
- System status: GPU/CPU, selected model, local processing.
- Upload card.
- Recent videos and analysis jobs.
- Empty state explaining how to begin.

### Page 2: Upload and configure

- Drag-and-drop or file picker.
- Display filename, size, and video preview.
- Settings:
  - Sampling rate
  - Confidence threshold
  - Tracking toggle
- **Analyze Video** button.
- Friendly validation errors.

### Page 3: Processing

- Job status.
- Progress bar and frames processed/estimated.
- Current settings and model name.
- Cancel button only if cancellation can be implemented safely;
  otherwise omit it.

### Page 4: Analysis results

- Video player with original/annotated toggle.
- Summary cards: duration, sampled frames, detections, unique classes,
  processing time.
- Class-count chart or simple list.
- Filterable event timeline.
- Event cards with thumbnail, class, confidence, timestamp, and
  optional track ID.
- Clicking an event seeks the player to that time.
- CSV export can be added after the main flow works.

### Design direction

- Modern dark video-workbench style, but preserve readable contrast.
- Clear typography and spacing.
- Avoid excessive gradients, unnecessary animations, and fake metrics.
- Use real backend results; do not hardcode demo analytics in the
  production UI.
- Include useful loading, empty, success, and error states.
- Ensure the application is usable at a typical laptop screen size.

---

## 10. Local Development and Setup

The agent should create clear Windows-friendly setup instructions.

### Suggested repository setup

Use separate frontend and backend folders.

### Backend environment

1.  Install a compatible Python version.
2.  Create a virtual environment.
3.  Install a CUDA-enabled PyTorch build compatible with the installed
    NVIDIA driver, following the official PyTorch installation selector.
4.  Install the remaining backend dependencies.
5.  Run the backend.
6.  Test the health and system endpoints.
7.  Run a short sample video through the detector.

Example commands (adapt if required by the chosen compatible package
versions):

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install the appropriate PyTorch build separately using the official
PyTorch instructions. Then install project requirements:

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If PowerShell blocks virtual-environment activation, provide an
alternative command or explain the local execution-policy option without
asking the user to weaken system security unnecessarily.

### Frontend environment

```powershell
cd frontend
npm install
npm run dev
```

### Expected local addresses

- Frontend: typically `http://localhost:5173`
- Backend API: typically `http://localhost:8000`
- FastAPI docs: typically `http://localhost:8000/docs`

Configure these through environment variables where practical.

### GPU verification

Provide a diagnostic command:

```powershell
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')"
```

If CUDA is false: - Do not crash. - Explain that PyTorch may have been
installed without CUDA support, or the driver/environment may need
attention. - Allow CPU inference for short test clips. - Do not claim
the GPU is being used unless verified.

---

## 11. Reliability, Security, and Quality

- Validate uploads and enforce size limits.
- Use safe generated filenames and prevent path traversal.
- Restrict static file serving to the configured data directory.
- Do not expose private local paths in API responses.
- Clean up temporary frame files.
- Avoid loading the model for every frame or every request; load it
  once per worker/process.
- Keep inference concurrency at one by default.
- Handle unreadable/corrupt videos and output-writer errors.
- Use configurable frame sampling, image size, and confidence
  threshold.
- Use structured logging.
- Keep the database and generated artifacts out of Git.
- Add basic tests for upload validation, job state transitions, event
  filtering, and video metadata extraction.
- Include a short sample video only if licensing permits; otherwise
  document how to obtain a suitable sample.
- Clearly label confidence as a model score, not a probability of
  truth.
- Do not identify people or make identity claims.

### Privacy

The MVP should process video locally. Make it clear that uploaded files
remain in the configured local storage folder unless the user explicitly
adds a remote service later.

---

## 12. Evaluation and Demo Plan

Prepare a repeatable 2--3 minute demonstration.

1.  Open the dashboard and show local GPU/system status.
2.  Upload a short video containing several common objects.
3.  Start analysis and show progress.
4.  Show the annotated output and object counts.
5.  Filter for one class, such as `person` or `car`.
6.  Click an event and demonstrate that the video jumps to its
    timestamp.
7.  Show a few tracking IDs if tracking is enabled.
8.  Explain limitations honestly: the detector only recognizes supported
    classes, sampling can miss brief events, and tracking IDs may switch
    or disappear.

### MVP acceptance checklist

- [ ] Frontend and backend start using documented commands.
- [ ] Model inference works on the local machine.
- [ ] GPU use is verified when CUDA is available; CPU fallback works.
- [ ] Video upload returns a valid ID.
- [ ] Job status and progress update.
- [ ] Events include correct timestamps within reasonable tolerance.
- [ ] Annotated video can be played if output generation succeeds.
- [ ] Filtering by object class works.
- [ ] Clicking an event seeks to its timestamp.
- [ ] Invalid or corrupt files produce friendly errors.
- [ ] No model training or fine-tuning is used.
- [ ] README documents limitations and local storage behavior.

---

## 13. Implementation Order for the Coding Agent

Build in small, testable milestones. Do not generate the entire codebase
blindly and claim it works.

### Milestone 1 --- Repository skeleton

- Create frontend/backend folders.
- Add README, `.gitignore`, environment example, and basic app health
  route.
- Confirm frontend and backend start.

### Milestone 2 --- Local inference proof

- Add a standalone Python script that loads the selected pretrained
  nano model.
- Run inference on one image and one short video.
- Verify CUDA/CPU selection.
- Save a sample annotated output.
- Fix package/device issues before adding the frontend workflow.

### Milestone 3 --- Video upload and job processing

- Implement safe upload.
- Add SQLite models and job status.
- Add a single-worker analysis service.
- Test one short video end to end.

### Milestone 4 --- Events and annotated output

- Persist detections and timestamps.
- Generate thumbnails and annotated preview.
- Add event filtering endpoints.

### Milestone 5 --- Frontend workflow

- Build dashboard, upload form, progress page, and results page.
- Connect all pages to real API endpoints.
- Implement event-click-to-seek behavior.

### Milestone 6 --- Polish and verification

- Test malformed uploads, unsupported codecs, model errors, and
  refresh behavior.
- Verify the README commands on Windows.
- Complete the demo checklist.
- Fix bugs before adding optional features.

At the end of every milestone: 1. List files created/changed. 2. Run
available tests or smoke checks. 3. Report actual results and any
unresolved errors. 4. Do not claim a command passed unless it was run
successfully.

---

## 14. Instructions to the AI Coding Agent

You are implementing **SceneTrace: AI-Powered Video Intelligence and
Search System**.

Follow these rules: 1. Read this entire brief before making changes. 2.
Build the MVP in the milestone order above. 3. Use pretrained model
weights only. **Do not train or fine-tune any model.** 4. Prioritize a
working end-to-end local demo over architectural complexity. 5. Target
Windows, RTX 3050 with 4 GB VRAM, and 16 GB RAM. 6. Keep GPU memory use
conservative; process frames sequentially and limit concurrent jobs to
one. 7. Do not add features from P1/P2 until every P0 acceptance
criterion passes. 8. If a package/API has changed, check the installed
version and adapt to its documented interface rather than inventing
methods. 9. Keep detector, tracker, video reader, job processing,
database, and API concerns separated. 10. Never hardcode fake analysis
results into the real dashboard. 11. Do not silently swallow errors. Log
technical details and show friendly user-facing messages. 12. Do not
overengineer with microservices, Redis, Docker, or cloud infrastructure. 13. Keep a `README.md` with exact setup, run, troubleshooting, and demo
instructions. 14. If a choice is uncertain, prefer the simplest reliable
implementation and document the trade-off. 15. Start by inspecting the
current repository. If it is empty, scaffold the project. If code
already exists, preserve useful working code and explain the plan before
major refactoring.

### First response expected from the agent

Before implementation, briefly state: - Your understanding of the MVP. -
The proposed folder structure. - The exact pretrained model and
dependency strategy. - Any hardware/compatibility risks. Then begin
Milestone 1 and continue incrementally.

---

## 15. Definition of Done

The project is ready to present when a user can run it locally, upload a
short video, process it with a pretrained detector, see object
detections and timestamps, filter events by class, and click an event to
jump to the correct part of the video.

**Do not confuse a large feature list with a successful project. A
reliable, polished end-to-end demo is the priority.**
