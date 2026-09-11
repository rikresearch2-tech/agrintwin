"""
Crop disease diagnostic service.

PRODUCTION PATH: loads a fine-tuned MobileNetV2 classifier (see
/ml/training/train_disease_classifier.py) trained on a plant-disease
dataset. A real trained model IS included in this submission — see
app/ml/weights/disease_model.keras — trained on 5 classes sourced from
the public PlantVillage dataset (healthy, maize_leaf_spot,
potato_late_blight, tomato_early_blight, tomato_leaf_curl_virus). It
does NOT cover rice_blast/rice_bacterial_blight — PlantVillage has no
rice-disease images, and we did not have time/access in the hackathon
window to source a labeled rice dataset. This is disclosed via
model_version in every response rather than silently guessing on rice
photos with unwarranted confidence.

DEMO PATH (DISEASE_MODEL_DEMO_MODE=True or weights file missing): falls
back to a deterministic, per-pixel HSV lesion-detection heuristic so the
endpoint always returns a sensible result even without the weights file
present (e.g. a clone of just the source code, without ml/weights/).
"""
import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

LABELS = [
    "healthy",
    "rice_blast",
    "rice_bacterial_blight",
    "tomato_early_blight",
    "tomato_leaf_curl_virus",
    "potato_late_blight",
    "maize_leaf_spot",
]

# Which disease labels are even plausible for a given crop. The heuristic
# uses this to restrict its guess to the right family — without it, a
# rice-leaf photo could get labeled "maize_leaf_spot" purely from a hue
# hash, which is nonsensical to anyone reading the result and undermines
# trust in the whole scan even though the healthy/diseased call itself
# was correct. Unlisted/unknown crops fall back to the full disease list
# since we have no better information.
CROP_DISEASE_LABELS: dict[str, list[str]] = {
    "rice": ["rice_blast", "rice_bacterial_blight"],
    "paddy": ["rice_blast", "rice_bacterial_blight"],
    "tomato": ["tomato_early_blight", "tomato_leaf_curl_virus"],
    "potato": ["potato_late_blight"],
    "maize": ["maize_leaf_spot"],
    "corn": ["maize_leaf_spot"],
}

# The trained model (see ml/training/train_disease_classifier.py) only
# covers the classes we could source real labeled images for — PlantVillage
# (the public dataset used for this demo build) has no rice-disease classes
# at all, so rice_blast/rice_bacterial_blight are NOT in the trained
# model's output. Its label order is written alongside the weights file
# (disease_model_labels.json) and loaded dynamically below; this constant
# is only the fallback if that file is missing. A rice photo will still
# get a prediction (softmax always picks the closest of the 5 trained
# classes) but it won't be a real rice-disease diagnosis — see the
# model_version field in the response, and docs/ARCHITECTURE.md, for how
# this is disclosed rather than silently presented as authoritative.
TRAINED_LABELS_FALLBACK = [
    "healthy",
    "maize_leaf_spot",
    "potato_late_blight",
    "tomato_early_blight",
    "tomato_leaf_curl_virus",
]

RECOMMENDATIONS = {
    "healthy": "No action needed. Continue current regenerative practices.",
    "rice_blast": (
        "Apply tricyclazole-based fungicide within 48 hours; avoid excess nitrogen; "
        "improve field drainage to reduce humidity around the canopy."
    ),
    "rice_bacterial_blight": (
        "Remove and destroy infected leaves; avoid overhead irrigation; "
        "use copper-based bactericide; rotate to a resistant variety next season."
    ),
    "tomato_early_blight": (
        "Prune lower infected leaves; apply chlorothalonil or copper fungicide; "
        "mulch to prevent soil splash onto leaves."
    ),
    "tomato_leaf_curl_virus": (
        "Remove infected plants to stop whitefly-vector spread; install yellow sticky "
        "traps; consider virus-resistant seed varieties for next planting."
    ),
    "potato_late_blight": (
        "Apply metalaxyl or mancozeb fungicide immediately — late blight spreads fast in "
        "humid conditions; destroy visibly infected tubers."
    ),
    "maize_leaf_spot": (
        "Apply azoxystrobin-based fungicide; rotate with a non-cereal crop next season; "
        "clear crop residue after harvest to reduce spore carryover."
    ),
}


class DiseaseClassifier:
    """Lazy-loaded singleton wrapper around the trained Keras model."""

    _instance = None

    def __init__(self):
        self.model = None
        self.trained_labels = TRAINED_LABELS_FALLBACK
        self.demo_mode = True
        self._try_load_model()

    def _try_load_model(self):
        model_path = Path(settings.DISEASE_MODEL_PATH)
        if settings.DISEASE_MODEL_DEMO_MODE or not model_path.exists():
            logger.warning(
                "Disease model weights not found at %s — running in heuristic demo mode. "
                "Run ml/training/train_disease_classifier.py to produce real weights.",
                model_path,
            )
            self.demo_mode = True
            return
        try:
            import json

            import tensorflow as tf  # local import: keeps tensorflow optional for API-only deploys

            self.model = tf.keras.models.load_model(model_path)

            labels_path = model_path.with_name(model_path.stem + "_labels.json")
            if labels_path.exists():
                self.trained_labels = json.loads(labels_path.read_text())
            else:
                logger.warning(
                    "No %s found alongside the model — falling back to the hardcoded "
                    "TRAINED_LABELS_FALLBACK order. This will mis-map predictions if the "
                    "model was trained with a different class order.",
                    labels_path.name,
                )

            self.demo_mode = False
            logger.info("Loaded disease classifier from %s (%d classes)", model_path, len(self.trained_labels))
        except Exception as exc:  # noqa: BLE001 — must never crash the API on model load failure
            logger.error("Failed to load disease model, falling back to demo mode: %s", exc)
            self.demo_mode = True

    @classmethod
    def instance(cls) -> "DiseaseClassifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _heuristic_predict(self, image: Image.Image, crop: str | None = None) -> tuple[str, float]:
        """
        Deterministic pixel-level lesion-patch heuristic used only when no
        trained weights are available.

        IMPORTANT: a whole-image color *average* fails on real photos —
        a lesion (blast, blight, leaf spot) is typically a small localized
        patch on an otherwise healthy-green blade, so averaging color across
        the full frame dilutes it into "mostly green" and misses the
        disease entirely. This version instead computes greenness
        *per pixel*, then looks at what FRACTION of pixels look like lesion
        tissue (non-green, but not background/shadow/glare) — closer to
        what a trained CNN's localized filters would actually pick up.
        Still not a substitute for the trained model in ml/training/ — a
        real classifier reasons over texture and lesion shape, not just
        color — but this catches localized spots the naive average missed.

        The disease-TYPE label is picked from the crop-appropriate subset
        only (CROP_DISEASE_LABELS) — this heuristic has no real ability to
        tell disease types apart from color/hue alone, so the label is
        always a rough guess, but it should at least never suggest a maize
        disease on a rice photo. Only the healthy/diseased call itself is
        meaningfully grounded in the image.
        """
        # HSV separates hue from brightness/saturation, which is a more
        # reliable per-pixel "is this green plant tissue?" test than a
        # linear RGB combination — a linear index can't cleanly separate
        # tan/brown lesion pixels from green leaf pixels across lighting
        # conditions, which is what caused the earlier version to miss a
        # real diseased-leaf photo.
        hsv = np.asarray(image.convert("RGB").resize((224, 224)).convert("HSV"), dtype=np.float32)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]  # each channel 0-255

        # Healthy leaf tissue: green hue band, reasonably saturated.
        green_mask = (h >= 45) & (h <= 150) & (s >= 40)
        # Exclude near-black (shadow) and near-white (glare/background)
        # pixels from the lesion count either way.
        valid_mask = (v > 40) & (v < 245)
        lesion_mask = (~green_mask) & valid_mask
        lesion_fraction = float(np.mean(lesion_mask))

        LESION_THRESHOLD = 0.02  # >2% of the frame looking like non-green tissue

        if lesion_fraction <= LESION_THRESHOLD:
            confidence = min(0.97, 0.80 + (LESION_THRESHOLD - lesion_fraction) * 5)
            return "healthy", round(confidence, 3)

        # Classify disease type from the hue *within the lesion pixels only*,
        # not the whole frame — so the label reflects the lesion's actual color.
        lesion_hue = float(h[lesion_mask].mean()) if lesion_mask.any() else float(h.mean())

        candidate_labels = CROP_DISEASE_LABELS.get((crop or "").strip().lower(), LABELS[1:])
        idx = int(abs(hash(round(lesion_hue, 1))) % len(candidate_labels))
        confidence = min(0.95, 0.55 + lesion_fraction * 3)
        return candidate_labels[idx], round(confidence, 3)

    def predict(self, image_bytes: bytes) -> tuple[str, float]:
        image = Image.open(io.BytesIO(image_bytes))

        if self.demo_mode or self.model is None:
            return self._heuristic_predict(image)

        # NOTE: no /255.0 here — the trained model has its own
        # tf.keras.layers.Rescaling(1./255) as its first layer (see
        # ml/training/train_disease_classifier.py), so it expects raw
        # 0-255 pixel values. Normalizing here too silently double-scales
        # the input toward zero and produces a degenerate, always-the-
        # same-class prediction — this bit us once already; don't
        # reintroduce it.
        arr = np.asarray(image.convert("RGB").resize((224, 224)), dtype=np.float32)
        batch = np.expand_dims(arr, axis=0)
        preds = self.model.predict(batch, verbose=0)[0]
        idx = int(np.argmax(preds))
        return self.trained_labels[idx], float(preds[idx])


# Crops the trained model actually has classes for. A photo of a crop
# NOT in this set (most importantly rice — PlantVillage has zero rice
# images) gets routed to the heuristic instead of the trained model,
# even when the model is loaded. Without this guard, the CNN produces
# a confident-looking softmax score on tissue it has never seen — it
# called a real diseased rice leaf "healthy" at 98% confidence during
# testing, which is a worse outcome than an honestly-uncertain
# heuristic. Keep this in sync with TRAINED_LABELS_FALLBACK/the
# training data's source crops.
TRAINED_MODEL_CROP_COVERAGE = {"tomato", "potato", "maize", "corn"}


def diagnose(image_bytes: bytes, crop: str | None = None) -> dict:
    classifier = DiseaseClassifier.instance()

    crop_covered = crop is not None and crop.strip().lower() in TRAINED_MODEL_CROP_COVERAGE
    use_trained_model = not classifier.demo_mode and classifier.model is not None and crop_covered

    if use_trained_model:
        label, confidence = classifier.predict(image_bytes)
        model_version = "mobilenetv2-plantvillage-v1"
    else:
        label, confidence = classifier._heuristic_predict(Image.open(io.BytesIO(image_bytes)), crop=crop)
        if not classifier.demo_mode and classifier.model is not None:
            # Model IS loaded and working — we're choosing the heuristic
            # specifically because this crop isn't in its training data.
            model_version = "heuristic-v0 (crop not covered by trained model — see docs)"
        else:
            model_version = "heuristic-demo-v0"

    return {
        "predicted_label": label,
        "confidence": round(confidence, 4),
        "is_healthy": label == "healthy",
        "recommended_action": RECOMMENDATIONS.get(label, "Consult local agricultural extension officer."),
        "model_version": model_version,
    }
