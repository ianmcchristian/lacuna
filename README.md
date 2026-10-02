# Lacuna

Finds empty shelf space in retail shelf photos.

Upload a shelf photo, and Lacuna detects every product, groups them into shelf
rows, and flags the holes where product is missing. Every scan is saved to
Postgres, so you can track a shelf over time and rank which shelves need a
restock first.

*lacuna (Latin): a gap, the missing piece.*

## How it works

```
photo -> letterbox 640x640 -> YOLO11s (ONNX Runtime) -> NMS -> product boxes
      -> group boxes into shelf rows -> walk each row for holes -> gaps + occupancy
      -> Postgres (scans, detections, gaps) -> SQL reports
```

1. **Detect products.** A YOLO11s model fine-tuned on
   [SKU-110K](https://github.com/eg4000/SKU110K_CVPR19) (dense retail shelves)
   runs on ONNX Runtime. Letterboxing and non-max suppression are written here
   in NumPy, so there's no PyTorch in the service.
2. **Group into rows.** Boxes are sorted top to bottom and joined into a row
   when they overlap it vertically by at least half their height. That keeps
   tall and short products on the same shelf together.
3. **Find gaps.** Each row is walked left to right. Any hole wider than
   `0.8x` the row's median product width is a gap. One missing product leaves a
   hole about `1.1-1.2x` wide, and normal spacing between products is about
   `0.1x`, so `0.8` catches a single out without flagging spacing. Row ends are
   checked against the full shelf width, so an empty spot at the edge still
   counts.
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
uv run python scripts/download_weights.py s      # ~38 MB, checksum verified
uv run alembic upgrade head                      # SQLite by default
uv run uvicorn lacuna.main:create_app --factory --reload
```

Try the model on a photo without the API:

```bash
uv run python scripts/annotate.py path/to/shelf.jpg   # writes shelf.overlay.jpg
```

With Docker (API + Postgres + migrations):

```bash
docker compose up --build    # API on localhost:8080
```

Settings come from `LACUNA_*` environment variables. See `.env.example`.

## Tests

```bash
uv run pytest                                   # SQLite
LACUNA_TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest   # Postgres, like CI
uv run ruff check . && uv run mypy lacuna tests scripts
```

The suite covers the API contract, upload edge cases (wrong type, too big,
empty, corrupt), the gap logic, pre/post-processing, the SQL reports, and a
check that the Alembic migrations match the models. With the weights
downloaded, it also runs the real model, inpaints one product out of a shelf
photo, and checks a gap shows up in that spot.

## Design notes

- **ONNX Runtime, not PyTorch.** Inference only, so the runtime is a fraction
  of the size and the container starts faster.
- **YOLO11s over YOLO11n.** On a glass-door cooler photo, n missed a can
  washed out by glare (score 0.15) and reported a fake gap. s caught it (0.33)
  and found 20 products to n's 15. It costs ~74 ms vs ~31 ms per image on CPU.
- **Gap logic is only as good as detection recall.** A missed product looks
  exactly like a hole. That's the main failure mode.

## Limits

- A shelf row with no products at all has nothing to anchor it, so it isn't
  reported. Rows with only one product are skipped as noise.
- It finds *where* product is missing, not *which* product. Naming the missing
  item would need a product catalog or planogram.
- Images are stored on local disk, which is fine for one container but not for
  several replicas.
- Small products in very large photos lose detail at 640x640.

## Credits and license

- Model: [chistopat/sku110k-yolo11-object-detector](https://huggingface.co/chistopat/sku110k-yolo11-object-detector),
  YOLO11 by [Ultralytics](https://github.com/ultralytics/ultralytics) (AGPL-3.0),
  trained on SKU-110K (Goldman et al., CVPR 2019). The weights carry the
  dataset's research terms.
- This repo is licensed AGPL-3.0. See [LICENSE](LICENSE).
