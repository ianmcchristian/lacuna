# Lacuna

[![ci](https://github.com/ianmcchristian/lacuna/actions/workflows/ci.yml/badge.svg)](https://github.com/ianmcchristian/lacuna/actions/workflows/ci.yml)

Finds empty shelf space in retail shelf photos.

Upload a shelf photo, and Lacuna detects every product, groups them into shelf
rows, and flags the holes where product is missing. Every scan is saved to
Postgres, so you can track a shelf over time and rank which shelves need a
restock first.

*lacuna (Latin): a gap, the missing piece.*

**Try it:** [upload UI](https://ianmcchristian.github.io/lacuna/) ·
[API docs](https://lacuna-mp1n.onrender.com/docs). The API runs on a free
instance with a tenth of a CPU, so a scan takes several seconds there (about
75 ms on a laptop).

![Upload UI showing a scan with 40 products, 2 gaps, and 89% occupancy](docs/screenshot.jpg)

## Demo

Green boxes are products, red boxes are gaps. These shelf photos are
**AI-generated** (made up for this demo, no real brands), and each was made with
known empty spots so the output can be checked against them.

| Canned goods | Cereal | Bottles |
|---|---|---|
| ![canned goods shelf with two gaps found](docs/demo/canned-goods.overlay.jpg) | ![cereal shelf with two gaps found](docs/demo/cereal.overlay.jpg) | ![bottle shelf with two gaps found](docs/demo/bottles.overlay.jpg) |
| 40 products, 2 gaps | 23 products, 2 gaps | 43 products, 2 gaps |

All 6 holes are found, with no false gaps. Two of them are a single product
wide (0.93x and 1.24x the median product width), which is why the threshold is
0.8x and not something looser like 1.5x: at 1.5x only 4 of 6 are found. These
images are a regression test in CI (`tests/test_model.py`).

## How it works

```
photo -> letterbox 640x640 -> YOLO11s (ONNX Runtime) -> NMS -> product boxes
      -> group boxes into shelf rows -> walk each row for holes -> gaps + occupancy
      -> Postgres (images, scans, detections, gaps) -> SQL reports
```

1. **Detect products.** A YOLO11s model fine-tuned on
   [SKU-110K](https://github.com/eg4000/SKU110K_CVPR19) (dense retail shelves)
   runs on ONNX Runtime. Letterboxing and non-max suppression are written here
   in NumPy, so there's no PyTorch in the service.
2. **Group into rows.** Boxes are sorted top to bottom and joined into a row
   when they overlap it vertically by at least half their height. That keeps
   tall and short products on the same shelf together.
3. **Find gaps.** Each row is walked left to right. Any hole wider than
   `0.8x` the row's median product width is a gap. Normal spacing between
   products is about `0.1x`. Row ends are checked against the full shelf width,
   so an empty spot at the edge still counts.
4. **Score it.** Occupancy = `1 - gap width / shelf width` across every row
   checked.

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/images` | Upload a jpeg, png, or webp (10 MB max). Optional `shelf` code like `aisle4-bay2` |
| `POST` | `/detect` | Run detection on an uploaded image, save the scan |
| `GET` | `/results/{scan_id}` | Products, gaps, occupancy, latency |
| `GET` | `/results/{scan_id}/overlay` | The photo with products in green, gaps in red |
| `GET` | `/shelves/{code}/history` | A shelf's scans over time, with the change vs the scan before |
| `GET` | `/reports/worst-shelves` | Shelves ranked by occupancy on their latest scan |
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Readiness: database reachable and model loaded |
| `GET` | `/metrics` | Prometheus metrics |

Interactive docs are at `/docs` once it's running.

```bash
curl -F file=@shelf.jpg -F shelf=aisle4-bay2 localhost:8000/images
curl -X POST localhost:8000/detect -H 'content-type: application/json' -d '{"image_id": "<id>"}'
```

The two reports are plain SQL in [`lacuna/db/reports.py`](lacuna/db/reports.py):
shelf history uses `LAG()` to get the occupancy change between scans, and worst
shelves uses `ROW_NUMBER()` to pick each shelf's latest scan before ranking.

## Run it

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python scripts/download_weights.py s      # ~38 MB, pinned revision + sha256
uv run alembic upgrade head                      # SQLite by default
uv run uvicorn lacuna.main:create_app --factory --reload
```

Try the model on a photo without the API:

```bash
uv run python scripts/annotate.py docs/demo/cereal.jpg   # writes cereal.overlay.jpg
```

The upload UI (React + TypeScript, Vite) lives in `web/`:

```bash
cd web && npm install
npm run dev          # localhost:5173, talks to the API on :8000
```

With Docker (API + Postgres + migrations):

```bash
docker compose up --build    # API on localhost:8080
```

Settings come from `LACUNA_*` environment variables. See `.env.example`.

### Kubernetes (local kind cluster)

`k8s/base` has the Deployment (2 replicas, startup/liveness/readiness probes,
non-root, read-only root filesystem), Service, HorizontalPodAutoscaler (2-6
replicas at 70% CPU), and a migration Job. `k8s/local` adds a throwaway
Postgres for kind.

```bash
kind create cluster --config k8s/local/kind.yaml
docker build -t lacuna:local . && kind load docker-image lacuna:local --name lacuna
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl apply -k k8s/local
kubectl port-forward svc/lacuna 8080:80
```

Under load (8 clients looping on `/detect`), the HPA went from 2 to 6 replicas
in about 90 seconds at 190% of the CPU target.

## Tests

```bash
uv run pytest                                   # SQLite
LACUNA_TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest   # Postgres, like CI
uv run ruff check . && uv run mypy lacuna tests scripts
cd web && npm test && npm run e2e               # UI: jsdom + real browser
```

43 Python tests (97% coverage) cover the API contract, upload edge cases (wrong
type, too big, empty, corrupt), the gap logic, pre/post-processing, the SQL
reports, Alembic migrations matching the models, and an upload being scanned by
a second app instance (a fresh replica). With the weights downloaded, they also
run the real model on the demo shelves and inpaint one bottle out of a full row
to check the gap lands there.

CI runs all of it against Postgres 16, builds the Docker image, starts it, and
runs a real detection against the container.

## Deployment

- **API:** Docker image on [Render](https://render.com)'s free plan
  ([`render.yaml`](render.yaml)). Render deploys `main` only after CI passes.
  The free plan sleeps after 15 minutes idle, so a scheduled workflow pings it.
- **Database:** Postgres on [Neon](https://neon.tech). CI runs the Alembic
  migration before each deploy.
- **UI:** static build on GitHub Pages ([`pages.yml`](.github/workflows/pages.yml)).

## Accessibility

The UI targets WCAG 2.2 AA: every input has a visible label and hint wired up
with `aria-describedby`, errors are announced and move focus to the field,
scan progress uses a live region, focus moves to the results when they load,
there's a skip link and a visible focus ring, buttons are at least 44x44 px,
and gaps are listed in a table so the result doesn't rely on color. Text
contrast is at least 6.67:1.

Playwright runs axe-core with every WCAG 2.2 AA rule (color contrast
included) in Chromium before and after a scan, and drives the whole flow by
keyboard. Vitest runs axe again in jsdom on each component state.

## Design notes

- **ONNX Runtime, not PyTorch.** Inference only, so the runtime is a fraction
  of the size and the container starts faster. The image is about 540 MB and
  uses about 260 MB of RAM.
- **YOLO11s over YOLO11n.** On a glass-door cooler photo, n missed a can
  washed out by glare (score 0.15) and reported a fake gap. s caught it (0.33)
  and found 20 products to n's 15. It costs ~75 ms vs ~31 ms per image on CPU
  (p50 74.6 ms, p95 79.7 ms on an M-series Mac).
- **Image bytes live in Postgres**, not on disk. With two replicas behind a
  Service, an upload can land on one pod and `/detect` on another, and free
  hosts wipe their disk on restart. Stored copies are capped at 2048 px; the
  model only sees 640.
- **Gap logic is only as good as detection recall.** A missed product looks
  exactly like a hole. That's the main failure mode.

## Limits

- A shelf row with no products at all has nothing to anchor it, so it isn't
  reported. Rows with only one product are skipped as noise.
- It finds *where* product is missing, not *which* product. Naming the missing
  item would need a product catalog or planogram.
- The demo set is small and synthetic. Real store photos (angles, glare,
  pegboard displays) will be harder.
- Small products in very large photos lose detail at 640x640.

## Credits and license

- Model: [chistopat/sku110k-yolo11-object-detector](https://huggingface.co/chistopat/sku110k-yolo11-object-detector),
  YOLO11 by [Ultralytics](https://github.com/ultralytics/ultralytics) (AGPL-3.0),
  trained on SKU-110K (Goldman et al., CVPR 2019). The weights carry the
  dataset's research terms.
- Demo shelf photos are AI-generated for this repo.
- This repo is licensed AGPL-3.0. See [LICENSE](LICENSE).
