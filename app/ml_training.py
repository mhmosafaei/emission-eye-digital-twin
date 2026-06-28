from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Any

import joblib
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.ml_features import build_ml_training_dataset


def train_expected_co2_model(*, vessel_id: str | None = None) -> dict[str, Any]:
    dataset = build_ml_training_dataset(vessel_id=vessel_id)
    rows = dataset["rows"]
    features = dataset["features"]
    targets = dataset["targets"]
    if len(rows) < 5:
        raise ValueError("At least 5 valid performance windows are required to train the expected CO2 model.")

    split = _split_dataset(rows, features, targets)
    vectorizer = DictVectorizer(sparse=False)
    x_train = vectorizer.fit_transform(split["train_features"])
    x_test = vectorizer.transform(split["test_features"])

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=2,
    )
    model.fit(x_train, split["train_targets"])
    predictions = model.predict(x_test)

    dummy_model = DummyRegressor(strategy="mean")
    dummy_model.fit(x_train, split["train_targets"])
    dummy_predictions = dummy_model.predict(x_test)

    metrics = _build_metrics(split["test_targets"], predictions)
    dummy_metrics = _build_metrics(split["test_targets"], dummy_predictions)
    model_version = _model_version()
    model_dir = _model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "expected_co2_model.joblib"
    metadata_path = model_dir / "expected_co2_model_metadata.json"

    metadata = {
        "model_type": "RandomForestRegressor",
        "target_column": dataset["target_column"],
        "train_rows": len(split["train_targets"]),
        "test_rows": len(split["test_targets"]),
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "r2": metrics["r2"],
        "mape_pct": metrics["mape_pct"],
        "dummy_mae": dummy_metrics["mae"],
        "dummy_rmse": dummy_metrics["rmse"],
        "dummy_r2": dummy_metrics["r2"],
        "dummy_mape_pct": dummy_metrics["mape_pct"],
        "feature_columns": list(vectorizer.get_feature_names_out()),
        "raw_feature_columns": dataset["feature_columns"],
        "model_version": model_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(model_path),
        "metadata_path": str(metadata_path),
        "vessel_id": vessel_id,
    }

    artifact = {
        "model": model,
        "vectorizer": vectorizer,
        "metadata": metadata,
    }
    joblib.dump(artifact, model_path)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def load_model_artifact() -> dict[str, Any]:
    model_path = _model_dir() / "expected_co2_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {model_path}")
    artifact = joblib.load(model_path)
    if not isinstance(artifact, dict):
        raise ValueError("Invalid model artifact format.")
    return artifact


def load_model_metadata() -> dict[str, Any] | None:
    metadata_path = _model_dir() / "expected_co2_model_metadata.json"
    if not metadata_path.exists():
        return None
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _split_dataset(rows: list[Any], features: list[dict[str, Any]], targets: list[float]) -> dict[str, Any]:
    ordered = sorted(
        zip(rows, features, targets, strict=False),
        key=lambda item: (getattr(item[0], "window_start_utc", "") or "", getattr(item[0], "id", 0)),
    )
    split_index = max(int(len(ordered) * 0.8), 1)
    split_index = min(split_index, len(ordered) - 1)
    train_rows = ordered[:split_index]
    test_rows = ordered[split_index:]
    if not test_rows:
        test_rows = ordered[-1:]
        train_rows = ordered[:-1]
    return {
        "train_features": [item[1] for item in train_rows],
        "train_targets": [item[2] for item in train_rows],
        "test_features": [item[1] for item in test_rows],
        "test_targets": [item[2] for item in test_rows],
    }


def _build_metrics(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    mae = mean_absolute_error(actual, predicted)
    mse = mean_squared_error(actual, predicted)
    r2 = r2_score(actual, predicted) if len(actual) >= 2 else None
    non_zero_pairs = [(a, p) for a, p in zip(actual, predicted, strict=False) if a != 0]
    mape_pct = (
        sum(abs((a - p) / a) for a, p in non_zero_pairs) / len(non_zero_pairs) * 100.0
        if non_zero_pairs
        else None
    )
    return {
        "mae": round(float(mae), 6),
        "rmse": round(float(sqrt(mse)), 6),
        "r2": round(float(r2), 6) if r2 is not None else None,
        "mape_pct": round(float(mape_pct), 6) if mape_pct is not None else None,
    }


def _model_dir() -> Path:
    configured = os.getenv("EMISSION_EYE_MODEL_DIR")
    return Path(configured) if configured else Path("data") / "models"


def _model_version() -> str:
    return datetime.now(timezone.utc).strftime("expected-co2-%Y%m%dT%H%M%SZ")
