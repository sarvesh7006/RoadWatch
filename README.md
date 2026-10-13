# Roadwatch — Pothole Detection Using Deep Learning

Roadwatch is a local pothole-detection application built with **YOLOv8, FastAPI, React, and Leaflet**. Analyze road images or sampled video frames, attach observation coordinates, and manage repair reports from a single dashboard.

Inference runs on your computer. No API key or paid inference service is required. SQLite works out of the box; Docker Compose provides an optional PostgreSQL/PostGIS setup.

## Features

- Detect potholes in images using a pretrained YOLOv8 model.
- Analyze sampled frames from uploaded videos or a live camera.
- View GPS-tagged observations on an interactive map.
- Review annotated evidence and track open, scheduled, and resolved repairs.
- Export reports as CSV or GeoJSON.
- Train on custom data, convert RDD2022 annotations, and process video with GPS telemetry.

## Requirements

| Requirement | Notes |
| --- | --- |
| Python 3.12 | Recommended version for the included Python dependencies |
| Node.js 20.19+ or 22.12+ | Includes npm; needed to build the dashboard |
| Git | To clone the repository; downloading the repository ZIP also works |
| Internet access during setup | Downloads dependencies and the approximately 23 MB model |
| Modern browser | Camera and device location require browser permission |
| Docker with Compose | Optional; only needed for the containerized setup |

A GPU is optional. The application uses CPU inference by default. The Bash setup scripts support macOS, Linux, and WSL; native Windows instructions are below.

## Quick start

Clone the repository:

```bash
git clone https://github.com/sarvesh7006/RoadWatch.git
cd RoadWatch
```

### macOS, Linux, or WSL

With `uv` installed, the setup script can provision Python 3.12. Without `uv`, install Python 3.12 first and select it explicitly:

```bash
# With uv:
bash scripts/setup.sh

# Alternatively, without uv:
PYTHON=python3.12 bash scripts/setup.sh
```

Run only the setup command appropriate for your environment, then start the application:

```bash
bash scripts/start.sh
```

Setup creates `.venv`, installs Python and frontend dependencies, verifies the included pretrained model checkpoint, and builds the dashboard. The first installation can take a couple of minutes because PyTorch is installed.

### Windows (PowerShell)

With Python 3.12 and Node.js installed, run the automated setup and start scripts:

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

Or execute the steps manually:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/download_model.py
npm --prefix frontend ci
npm --prefix frontend run build
$env:YOLO_CONFIG_DIR = "$PWD/data/yolo"
$env:MPLCONFIGDIR = "$PWD/data/matplotlib"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8011
```

For subsequent launches, simply run `.\scripts\start.ps1` (or repeat the environment variable assignments and Uvicorn command).

### Open the app

- **Dashboard:** [http://127.0.0.1:8011](http://127.0.0.1:8011)
- **Interactive API docs:** [http://127.0.0.1:8011/docs](http://127.0.0.1:8011/docs)

Keep the server terminal open while using the app. Stop it with `Ctrl+C`.

The runtime model checkpoint (`models/pothole.pt`, ~22.5 MB) is committed directly to the repository so you can run inference immediately after setup. Development artifacts, experimental checkpoints, local databases, and generated frontend files are excluded by `.gitignore`. `requirements.txt` pins Python dependencies; `requirements.lock.txt` records environment versions; and `frontend/package-lock.json` locks frontend dependencies.

## Try your first inspection

1. Open **Detection studio** and select the included [sample image](examples/pothole.jpg) or your own road image.
2. Optionally enter the observation coordinates or choose **Use device GPS**. Leave coordinates empty if the location is unknown. The sample image's actual location is unknown.
3. Click **Analyze image** to see bounding boxes and confidence scores.
4. Detections create repair reports unless **Save detection reports** is unchecked.
5. Open **Repair reports** to review evidence, add notes, edit the observation location, and update the repair status.
6. If you add coordinates after analyzing, click **Save location to this report** under the result; changing the input fields alone does not update an already saved report.
7. Export reports as CSV, or export geotagged reports as GeoJSON.

A fresh installation starts with an empty report database. The included sample lets you check that real inference works without collecting your own footage first.

## Implementation details

- **Real image inference:** pretrained YOLOv8 pothole detection checkpoint. CPU default, 640×640 letterbox preprocessing. EXIF orientation is corrected; uploads are bounded to 15 MB / 24 megapixels and resized to a maximum 1920-pixel edge before inference.
- **Browser video and camera:** sequential frame sampling, annotated latest-frame preview, adjustable confidence, capture start/stop. Video is decoded locally in the browser. Each request finishes before another frame is sampled, with a one-second pause.
- **GPS:** manually entered observation coordinates or browser device position, including reported accuracy. Pending, failed, and stale device locations block capture until you retry, enter coordinates, or explicitly continue without a location. Images and reports can be saved without GPS.
- **Repair queue:** SQLite persistence, evidence JPEGs, notes, open/scheduled/resolved statuses, search, status filters, and CSV / GeoJSON export (latest 2,000 records).
- **Session grouping:** observations within 15 m and 30 seconds in the same capture session update one unresolved report. Without GPS, frames remain separate reports. Grouping is a triage heuristic and can combine distinct nearby potholes. It is not object tracking or a unique physical pothole count.
- **PostgreSQL + PostGIS option:** Docker Compose uses PostGIS; startup creates a `reports_geo` view with a geography location and a GiST expression index.
- **Training and video tools:** RDD VOC conversion, YOLOv8 training / test evaluation, and video processing with timestamp-aligned GPS CSV.

## Model and data provenance

Public checkpoint: [Harisanth/Pothole-Finetuned-YOLOv8](https://huggingface.co/Harisanth/Pothole-Finetuned-YOLOv8), trained for the `pothole` class. Model revision:

```
30a4d21de50998dbfa7cc79abb0d7a0d4aa71a4d
```

The download script verifies SHA-256 before installing `models/pothole.pt`:

```
8542745fa3e4f7ee0d03d8320443c6161747ba4658d2bbd770ee93abf7a7701a
```

This is a third-party starter model; this repository does not include a newly trained model or a 6,400-image training dataset. The model card does not identify a reproducible training-dataset split; evaluate it on your own roads before drawing accuracy conclusions. See [sample attribution](examples/ATTRIBUTION.md) for the included public sample and its CC BY 4.0 attribution. The upstream model card declares MIT licensing for this checkpoint. Ultralytics has its own AGPL-3.0 / enterprise licensing terms.

The inference code uses [Ultralytics' prediction API](https://docs.ultralytics.com/modes/predict/). To use your own trusted checkpoint:

```bash
MODEL_PATH=/absolute/path/to/best.pt ./scripts/start.sh
```

Only labels containing `pothole` or exactly `D40` are retained. Generic COCO YOLO weights do not detect potholes.

### Upgrading an existing installation

The original starter checkpoint missed obvious potholes outside its sample image. The default checkpoint has been replaced after comparing water-filled and broken-asphalt potholes, the original sample, and negative controls at the unchanged **35%** confidence threshold. This is a targeted regression check, not a benchmark or a guarantee of general accuracy.

```bash
.venv/bin/python scripts/download_model.py
# Stop the running server with Ctrl+C, then restart:
bash scripts/start.sh
```

The downloader preserves an existing different checkpoint in `models/pothole-backup-<hash>.pt`. Restarting matters because the server keeps the loaded model in memory. Fresh installations automatically receive the new pinned checkpoint. Inference uses a 0.5 NMS IoU threshold to suppress overlapping detections.

Run the opt-in real-model regression checks with the downloaded weights:

```bash
RUN_MODEL_TESTS=1 .venv/bin/python -m pytest tests/test_model_regression.py -q
```

On Windows, set `$env:RUN_MODEL_TESTS = "1"` before running the test command with `.\.venv\Scripts\python.exe`. The two local user-image cases are skipped if their files are absent; the attributed public sample and bundled negative controls remain runnable in a fresh clone. See [model validation notes](docs/model-validation.md) for the comparison and limitations.

## Train on your dataset

Prepare YOLO-format `images/{train,val,test}` and matching `labels/{train,val,test}` folders, with `0 x_center y_center width height` normalized labels. Use [training/data.example.yaml](training/data.example.yaml) as a template.

For extracted RDD2022 VOC annotations, convert only class **D40** to pothole:

```bash
.venv/bin/python scripts/prepare_rdd.py --source /path/to/RDD2022 --output /path/to/new-pothole-dataset
.venv/bin/python scripts/train.py --data /path/to/new-pothole-dataset/data.yaml --epochs 100 --batch 16 --device 0
```

Use `--device cpu --batch 4` without CUDA, or `--device mps` on a compatible Apple Silicon installation. Training downloads base YOLOv8s weights on first use. The conversion produces deterministic image-level 70/20/10 splits; for research results, split by route or capture session to prevent neighboring frames leaking across splits. Check label quality, country coverage, and negative examples. Download and prepare your own dataset separately; the conversion script does not acquire training images.

Evaluate your trained model on the held-out test split:

```bash
.venv/bin/python scripts/train.py --data /path/to/data.yaml --model runs/pothole/train/weights/best.pt --evaluate --device cpu
```

Training outputs under `runs/pothole/` contain Ultralytics metrics, plots, and weights. Repeated runs may increment the output folder name.

## Video with synchronized telemetry

Browser GPS for a prerecorded video describes the current device, not where that video was filmed. For a moving dashcam route, use a CSV with these columns:

```csv
seconds,latitude,longitude,accuracy_m
0.0,19.0760,72.8777,8.0
1.0,19.0761,72.8778,8.0
```

The coordinates above are illustrative. Supply actual telemetry aligned to the video's time origin.

With the local server running:

```bash
.venv/bin/python scripts/process_video.py /path/to/drive.mp4 --gps /path/to/gps.csv --every 1 --output /path/to/annotated.mp4
```

The script uses the nearest GPS sample only if it is within two video seconds (`--max-gps-gap`), saves observations through the API, and optionally writes a sampled annotated MP4 without audio. `--preview-only` avoids saving reports. Variable-frame-rate recordings should be converted to constant frame rate first because timestamps are derived from the declared FPS.

## Development and tests

Run the backend from the repository root:

```bash
bash scripts/start.sh
```

In another terminal, also from the repository root, start Vite:

```bash
npm --prefix frontend run dev
```

Open the development URL printed by Vite. It proxies API and media requests to port 8011. Update `frontend/vite.config.js` if you change the backend port.

Run tests or create a production frontend build from the repository root:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

The API tests use an isolated temporary database and a mocked detector for deterministic behavior. They do not require downloaded model weights. Check actual model inference separately with the sample image in the dashboard.

Initial validation covered 15 passing API tests, a successful frontend build, real-image detection, browser report creation and note updates, sampled-video processing, and RDD conversion. These checks are not an accuracy benchmark. Native Windows setup, physical camera/GPS hardware, GPU/Jetson deployment, the PostGIS Docker runtime, and full training still need validation on the target system.

## Docker / PostGIS

```bash
docker compose up --build
```

Run this command from the repository root, then open [http://127.0.0.1:8011](http://127.0.0.1:8011). Use this instead of the local server, since both use port 8011. Persistent volumes hold reports, images, and PostgreSQL data. This CPU image does not configure CUDA or NVIDIA Jetson TensorRT. On Apple Silicon, the selected PostGIS image may need `platform: linux/amd64` emulation or a native compatible PostGIS image. Docker must be installed separately.

Spatial query example (within 100 m):

```sql
SELECT id, severity, status
FROM reports_geo
WHERE ST_DWithin(location, ST_SetSRID(ST_MakePoint(72.8777, 19.0760), 4326)::geography, 100);
```

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | API and model-file availability |
| `POST /api/detect` | Multipart image + confidence, optional GPS, source, session ID, persist |
| `GET /api/reports` | Latest 2,000 reports |
| `PATCH /api/reports/{id}` | Update status, notes, or paired observation coordinates; null coordinates clear the location |
| `GET /api/export/csv` | Download tabular reports |
| `GET /api/export/geojson` | Download geotagged reports |
| `GET /media/{filename}` | Annotated evidence image |

JSON detection responses include `detections`, `inference_ms`, `preview`, `report`, and `merged`. Images with no detections create no repair ticket. Missing model files produce an explicit 503 error rather than fake detections.

## Configuration

Copy `.env.example` to `.env` to customize local runtime settings:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8011` | Local server port |
| `MODEL_PATH` | `models/pothole.pt` | Path to trained YOLOv8 checkpoint |
| `YOLO_DEVICE` | `cpu` | `cpu`, `mps` (Apple Silicon), or CUDA device `0` |
| `DATA_DIR` | `data/` | SQLite database and evidence images directory |
| `DATABASE_URL` | SQLite in data directory | Optional SQLAlchemy PostgreSQL / PostGIS URL |
| `YOLO_CONFIG_DIR` | `data/yolo` via start script | Ultralytics runtime settings |
| `MPLCONFIGDIR` | `data/matplotlib` via start script | Matplotlib cache directory |
| `RUN_MODEL_TESTS` | `0` | Set to `1` to run real model inference regression tests in pytest |

## Scope and limitations

This is a local prototype for detection and repair-report review. No project-specific precision, recall, mAP, real-time frame rate, GPS error bound, or maintenance cost reduction has been established. Measure these on a representative held-out dataset and the target hardware before making performance claims.

Priority is an explicit visual-footprint heuristic: below 2.5% of image area = low; 2.5–8% = medium; 8% and above = high. It depends on perspective, crop, and distance, and cannot measure depth, volume, or actual repair urgency. GPS is the observation/camera location, not a calibrated projection of the pothole onto the road. A zero-detection result does not certify a safe road.

Local reports are the implemented repair alerts. Automatic delivery to a real municipal service, authentication, team assignments, retention controls, background video jobs, and calibrated edge performance are integration work. The app binds to localhost and has no user authentication; add authentication and HTTPS before deploying it beyond a trusted local environment. Browser camera/GPS APIs require localhost or HTTPS. Inference runs locally; OpenStreetMap tiles and optional Google Fonts require internet, and map tile requests reveal the viewed area to the tile provider.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Model unavailable / detection returns 503 | Run `.venv/bin/python scripts/download_model.py` from the repository root to verify or restore `models/pothole.pt`. If weights are present, inspect the server log for an inference error. |
| Port 8011 is already in use | On macOS/Linux, run `PORT=8020 bash scripts/start.sh` and open port 8020. On Windows, set `$env:PORT="8020"` and run `.\scripts\start.ps1`. Update the Vite proxy if developing with `npm run dev`. |
| Dashboard is missing or outdated | Run `npm --prefix frontend ci` and `npm --prefix frontend run build`, then restart the backend and refresh the browser. |
| Camera or location is unavailable | Use localhost or HTTPS, check browser permissions, and confirm that the device provides the requested capability. Some embedded browsers cannot provide a location fix. Open the app in a regular browser, or enter coordinates manually. You can attach a location to an existing report after detection. |
| Map tiles do not appear | Map tiles require an internet connection. Reports and coordinates remain stored locally. |
| Python installation fails | Use Python 3.12 in a fresh virtual environment and check the failing package's platform support. |
| Few or no potholes detected | Try the included sample, inspect image quality and confidence settings, and evaluate or fine-tune the model on representative roads. |

## Contributing

Bug reports and pull requests are welcome. When reporting an issue, include your operating system, Python and Node.js versions, reproduction steps, and relevant error output. Use a public or anonymized sample when possible.

For code changes, run the API tests and frontend production build above. Describe the behavior changed and how it was verified. Keep generated reports, candidate model checkpoints, local datasets, and credentials out of commits; the included `.gitignore` excludes the standard runtime directories.

## Licensing and attribution

This repository does not currently include a project-level `LICENSE` file. Before publishing it for others to reuse, the repository owner should choose and add an appropriate license; this README does not grant one. Third-party libraries, model weights, and sample data retain their own terms. See the model provenance section and [sample attribution](examples/ATTRIBUTION.md).

## Publishing this repository

Before pushing:

1. Confirm that `models/pothole.pt` (~22.5 MB) is staged. It fits within standard GitHub limits (< 100 MB) without requiring Git LFS.
2. Verify that local databases (`data/*.db`), user uploads (`data/media/*`), experimental candidate weights, virtual environments (`.venv`), and `.env` credentials remain excluded by `.gitignore`.
3. Add a project-level `LICENSE` reflecting the permissions you intend to grant.

## Layout

```
backend/app/             FastAPI routes, detector, database
frontend/src/            React dashboard, Leaflet map, capture UI
models/pothole.pt        Verified pretrained checkpoint (included in repository)
data/                    Local SQLite database and report images (generated at runtime)
scripts/                 Setup, launch, training, RDD conversion, video processing
tests/                   API and persistence tests
training/                Dataset configuration template
examples/                Attributed public test images
Dockerfile, compose.yaml Optional CPU + PostGIS deployment
```
