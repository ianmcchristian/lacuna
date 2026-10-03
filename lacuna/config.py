"""App settings, read from LACUNA_* environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from lacuna.vision.gaps import DEFAULT_MIN_GAP_RATIO


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LACUNA_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./lacuna.db"
    # s over n: n missed a glare-washed can and reported a fake gap. ~74 vs ~31 ms on CPU.
    model_path: Path = Path("models/sku110k-yolo11-s640.onnx")
    max_upload_bytes: int = 10 * 1024 * 1024

    # ONNX Runtime threads, 0 = one per core. Use 1 on small CPU quotas (0.1 CPU: 33 s -> 7 s)
    inference_threads: int = 0

    conf_threshold: float = 0.25
    iou_threshold: float = 0.45
    # a hole has to be this many median product widths wide to count as a gap
    min_gap_ratio: float = DEFAULT_MIN_GAP_RATIO

    cors_origins: list[str] = ["http://localhost:5173"]
    log_json: bool = True
