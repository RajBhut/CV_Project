# SceneTrace

SceneTrace is a local video intelligence demo. Upload a recorded video, run sampled frames through a pretrained object detector, and browse timestamped detections. The MVP uses a single local worker and SQLite. No model training or fine-tuning is used.

## Current status

The local GPU inference proof and the API path for upload, analysis, event filtering, thumbnails, and annotated preview have been exercised on an RTX 3050 Laptop GPU (4 GB VRAM). The dashboard is wired to those API endpoints. See **Verification** for the actual checks run and their limits.

## Layout

```text
frontend/                       React + TypeScript + Vite interface
backend/
  app/
    api/                        FastAPI route modules
    services/                   Storage, video reading, inference, analysis, worker
    data/                        Local runtime files (ignored by Git)
    main.py                     FastAPI setup and route registration
    models.py                   SQLAlchemy SQLite schema
    schemas.py                  Pydantic API schemas
  scripts/inference_smoke.py    Standalone image and video inference check
```

## Windows setup

Use PowerShell in two terminals. Python 3.11 is recommended by the brief; the implementation was exercised with Python 3.10, which is available on this machine and supported by the current PyTorch Windows packages. Replace `3.10` below with `3.11` if installed.

### 1. Create the backend environment

```powershell
cd backend
py -3.10 -m venv .venv
```

Activation is optional. To avoid PowerShell execution-policy changes, call the virtual environment's interpreter directly as shown below.

### 2. Install PyTorch with CUDA support

Install PyTorch separately from the rest of the backend packages. This project was verified with the CUDA 12.8 wheel:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Select the appropriate CUDA wheel for your driver on the [official PyTorch install selector](https://pytorch.org/get-started/locally/). The PyTorch wheel is large. Verify the actual device; `nvidia-smi` reporting a GPU does not by itself prove that PyTorch can use it:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print('CUDA available:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')"
```

### 3. Install application packages and start the API

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend: http://localhost:8000. Health: http://localhost:8000/api/health. System: http://localhost:8000/api/system. API docs: http://localhost:8000/docs.

### 4. Start the frontend

In a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173. The Vite development server proxies `/api` to `http://localhost:8000`.

## Model, GPU memory, and speed

Inference uses the pretrained Ultralytics `yolo11n.pt` nano checkpoint. The weights download automatically on first inference when internet access is available and are kept locally; the weights are ignored by Git. Ultralytics currently states that its code and trained models are AGPL-3.0 by default and that a project using them must comply with AGPL-3.0 or obtain its Enterprise license. Review the [official license terms](https://www.ultralytics.com/license) before making this repository public or using it commercially. This repository does not bundle Ultralytics model weights. A project-level `LICENSE` has not been selected yet.

Frames run sequentially at a default sampling rate of 2 FPS. Inference image size defaults to 640 and can be lowered to 480 in the UI. Only one analysis worker runs at a time to limit VRAM use. On this machine, CUDA was available on the RTX 3050 Laptop GPU with 4,096 MiB. A different driver, CUDA-enabled PyTorch wheel, video codec, resolution, or GPU workload can affect performance. CPU fallback is supported but can be slow. SceneTrace does not promise real-time processing or a fixed completion time.

ByteTrack is optional and best-effort. IDs are useful only as short-range tracker labels: they may switch, disappear, or differ between runs. They do not identify a person or guarantee object identity across long occlusions.

## Data and privacy

Uploads, SQLite metadata, thumbnails, and annotated previews are stored under `backend/app/data` by default. Set `SCENETRACE_DATA_DIR` before starting the backend to change this location. Data stays on the local machine; the MVP makes no external AI API calls. Runtime files and `.env` are excluded from Git. The API serves generated files through ID-based routes and checks that resolved paths remain inside the configured data directory.

The first worker is an in-process local prototype, not a durable distributed queue. SQLite retains videos, job states, settings, and event metadata across page refreshes and backend restarts. A queued job is not guaranteed to resume if the backend process exits while it is waiting or processing.

## Repeatable inference smoke check

The repository does not include a sample video. Use an openly licensed or self-recorded clip with common objects; keep it short for the first run. With the backend environment active (or using its interpreter directly), run:

```powershell
cd backend
New-Item -ItemType Directory -Force app\data\smoke-input | Out-Null
```

Place one image and one short video in that folder, then run:

```powershell
.\.venv\Scripts\python.exe scripts\inference_smoke.py app\data\smoke-input\image.jpg app\data\smoke-input\clip.mp4 --image-size 640 --output-dir app\data\smoke-output
```

The script checks CUDA/CPU selection, loads the nano model once, runs image inference and up to 30 sequential video frames, and writes annotated outputs. Model weights download on the first inference if they are not already present.

## Automated checks

Install the optional test dependencies and run the backend tests from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

The tests cover friendly upload rejection, video metadata extraction, persisted job state transitions, and class/confidence event filtering.

## Limitations

- The detector recognizes only its pretrained supported classes. It does not understand arbitrary actions or natural-language questions.
- Sparse frame sampling can miss brief objects or events.
- The event list records individual detections and may contain repeated appearances of the same object.
- Confidence is a model score, not a calibrated probability that a detection is true.
- Preview generation prefers WebM/VP8 for browser playback and falls back to MP4 when the local OpenCV codecs do not provide that writer. If the writer cannot create a preview, event data remains available.
- Uploaded videos must be decodable by the local OpenCV/FFmpeg build.

## Verification performed during implementation

- Frontend production build (`npm run build`): passed.
- FastAPI health endpoint startup smoke check: passed.
- Standalone inference: `yolo11n.pt` detected objects in the sample image and processed 30 sample video frames on CUDA; annotated image/video files were written.
- CPU fallback: the same standalone script ran one image and 30 video frames with CUDA hidden, selected CPU, and wrote outputs.
- API end-to-end: sample MP4 upload returned metadata; a job advanced from queued to completed and processed its estimated sampled frames; class-filtered timestamp events and a thumbnail were returned; the annotated preview endpoint served a decodable WebM.
- Headless Edge UI: uploaded through the dashboard, waited for results, clicked a timestamped event, and confirmed seeking in both the original and annotated players.

These checks use a short public Ultralytics sample clip, not a broad validation set. They verify the local demo path, not detector accuracy on arbitrary footage.
