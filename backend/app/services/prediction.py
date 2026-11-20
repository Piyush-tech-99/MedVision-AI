"""Prediction services for MedVision AI."""

from __future__ import annotations

import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODELS_ROOT = BACKEND_ROOT / "models"

MODEL_CONFIGS = {
    ("Chest X-ray", "Pneumonia screening"): {
        "name": "pneumonia",
        "model": MODELS_ROOT / "pneumonia_model.keras",
        "metadata": MODELS_ROOT / "pneumonia_metadata.json",
        "binary": True,
    },
    ("Chest X-ray", "Tuberculosis screening"): {
        "name": "tuberculosis",
        "model": MODELS_ROOT / "tuberculosis" / "tb_efficientnetb0_best.keras",
        "metadata": MODELS_ROOT / "tuberculosis" / "tuberculosis_metadata.json",
        "binary": True,
    },
    ("Brain MRI", "Brain tumour screening"): {
        "name": "brain_tumour",
        "model": MODELS_ROOT / "brain_tumour" / "brain_tumour_efficientnetb0_best.keras",
        "metadata": MODELS_ROOT / "brain_tumour" / "brain_tumour_metadata.json",
        "binary": False,
    },
}


@lru_cache(maxsize=3)
def _load_model(model_path: str):
    import tensorflow as tf
    return tf.keras.models.load_model(model_path, compile=False)


def _load_metadata(metadata_path: Path) -> dict:
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _get_classes(metadata: dict) -> list[str]:
    classes = metadata.get("classes", {})

    if isinstance(classes, dict):
        return [
            str(classes[key])
            for key in sorted(classes, key=lambda x: int(x))
        ]

    if isinstance(classes, list):
        return [str(item) for item in classes]

    raise ValueError("Invalid class mapping in model metadata.")


def model_status(modality: str, task: str) -> dict:
    config = MODEL_CONFIGS.get((modality, task))

    if config is None:
        return {
            "connected": False,
            "reason": "No trained model is configured for this modality and task."
        }

    model_path = config["model"]
    metadata_path = config["metadata"]

    if not model_path.is_file():
        return {
            "connected": False,
            "reason": f"Model file not found: {model_path}"
        }

    if not metadata_path.is_file():
        return {
            "connected": False,
            "reason": f"Model metadata not found: {metadata_path}"
        }

    try:
        metadata = _load_metadata(metadata_path)
        _get_classes(metadata)
        _load_model(str(model_path))

    except Exception as exc:
        return {
            "connected": False,
            "reason": f"Model configuration error: {exc}"
        }

    return {
        "connected": True,
        "model_path": str(model_path),
        "metadata_path": str(metadata_path),
        "model_name": metadata.get("model_name", config["name"])
    }


def _predict_classifier(
    image_bytes: bytes,
    modality: str,
    task: str
) -> dict:

    config = MODEL_CONFIGS.get((modality, task))

    if config is None:
        return {
            "status": "MODEL_NOT_CONNECTED",
            "prediction": None,
            "confidence": None,
            "note": "No trained model is configured for this modality and task."
        }

    status = model_status(modality, task)

    if not status["connected"]:
        return {
            "status": "MODEL_NOT_CONNECTED",
            "prediction": None,
            "confidence": None,
            "note": status["reason"]
        }

    try:
        metadata = _load_metadata(config["metadata"])
        classes = _get_classes(metadata)

        image_size = metadata.get("image_size", [224, 224])

        image = (
            Image.open(BytesIO(image_bytes))
            .convert("RGB")
            .resize((int(image_size[1]), int(image_size[0])))
        )

        array = np.asarray(image, dtype=np.float32)[None, ...]

        model = _load_model(str(config["model"]))
        output = np.asarray(model.predict(array, verbose=0))

        if config["binary"]:
            positive_index = 1

            if output.size != 1 or len(classes) != 2:
                raise ValueError("Binary model output or class mapping is invalid.")

            positive_probability = float(output.reshape(-1)[0])

            if not 0.0 <= positive_probability <= 1.0:
                raise ValueError("Invalid binary probability returned by model.")

            probabilities = np.array([
                1.0 - positive_probability,
                positive_probability
            ])

            threshold = float(metadata.get("prediction_threshold", 0.5))

            predicted_index = (
                positive_index
                if positive_probability >= threshold
                else 0
            )

        else:
            probabilities = output.reshape(-1)

            if len(probabilities) != len(classes):
                raise ValueError("Model output does not match metadata classes.")

            if not np.all(np.isfinite(probabilities)):
                raise ValueError("Model returned invalid probabilities.")

            if not np.isclose(np.sum(probabilities), 1.0, atol=0.02):
                raise ValueError("Multiclass model output is not a probability distribution.")

            predicted_index = int(np.argmax(probabilities))
            threshold = None

        prediction = classes[predicted_index]
        confidence = float(probabilities[predicted_index])

        result = {
            "status": "PREDICTION_GENERATED",
            "prediction": prediction,
            "confidence": confidence,
            "class_probabilities": {
                name: float(probabilities[i])
                for i, name in enumerate(classes)
            },
            "model_name": metadata.get("model_name", config["name"]),
            "model_path": str(config["model"]),
            "note": "Academic research classifier output; not a medical diagnosis."
        }

        if threshold is not None:
            result["prediction_threshold"] = threshold

        return result

    except Exception as exc:
        return {
            "status": "PREDICTION_ERROR",
            "prediction": None,
            "confidence": None,
            "note": f"{config['name']} prediction failed: {exc}"
        }


def _predict_pneumonia(image_bytes: bytes) -> dict:
    return _predict_classifier(
        image_bytes,
        "Chest X-ray",
        "Pneumonia screening"
    )


def predict_brain_mri(
    image_bytes: bytes,
    modality: str,
    task: str
) -> dict:
    return _predict_classifier(image_bytes, modality, task)


def predict_image(
    image_bytes: bytes,
    modality: str,
    task: str
) -> dict:
    return _predict_classifier(image_bytes, modality, task)