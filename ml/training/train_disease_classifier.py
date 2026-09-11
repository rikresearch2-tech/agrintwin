"""
Trains the production crop-disease classifier used by
backend/app/services/disease_service.py.

Approach: transfer learning on MobileNetV2 (small enough to run inference
on modest cloud instances and, longer-term, even on-device at the edge —
relevant for low-connectivity smallholder regions). Fine-tuned on a
plant-disease image dataset organized as:

    data/
      train/
        healthy/
        rice_blast/
        rice_bacterial_blight/
        tomato_early_blight/
        tomato_leaf_curl_virus/
        potato_late_blight/
        maize_leaf_spot/
      val/
        <same class folders>

Recommended base dataset: PlantVillage (public, ~54k labeled leaf images
across 38 classes — subset/remap to the 7 classes above) augmented with
regionally-collected images for rice blast/bacterial blight, which are
under-represented in PlantVillage but dominant in eastern-India paddy
fields (directly relevant to Team VIDYUT's home region).

Usage:
    python train_disease_classifier.py --data-dir ./data --epochs 15

Output:
    ../backend/app/ml/weights/disease_model.keras

Note: this script is provided as the production training path. It is not
executed as part of the hackathon submission's live demo (no GPU/dataset
available in the judging environment) — the backend runs in
DISEASE_MODEL_DEMO_MODE by default and falls back to a heuristic
classifier so the full pipeline is still demonstrable end-to-end without
requiring a pretrained weights file in the repo.
"""
import argparse
from pathlib import Path

LABELS = [
    "healthy",
    "rice_blast",
    "rice_bacterial_blight",
    "tomato_early_blight",
    "tomato_leaf_curl_virus",
    "potato_late_blight",
    "maize_leaf_spot",
]

IMG_SIZE = (224, 224)
BATCH_SIZE = 32


def build_model(num_classes: int):
    import tensorflow as tf
    from tensorflow.keras import layers, models

    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(*IMG_SIZE, 3), include_top=False, weights="imagenet"
    )
    base_model.trainable = False  # stage 1: train head only

    inputs = layers.Input(shape=(*IMG_SIZE, 3))
    x = tf.keras.applications.mobilenet_v2.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)

    model = models.Model(inputs, outputs)
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model, base_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default="./data")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--fine-tune-epochs", type=int, default=5)
    parser.add_argument(
        "--output",
        type=str,
        default="../backend/app/ml/weights/disease_model.keras",
    )
    args = parser.parse_args()

    import tensorflow as tf

    data_dir = Path(args.data_dir)
    train_ds = tf.keras.utils.image_dataset_from_directory(
        data_dir / "train", image_size=IMG_SIZE, batch_size=BATCH_SIZE, label_mode="int"
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        data_dir / "val", image_size=IMG_SIZE, batch_size=BATCH_SIZE, label_mode="int"
    )

    class_names = train_ds.class_names
    print(f"Detected classes: {class_names}")
    assert set(class_names) <= set(LABELS), (
        "Dataset folder names must be a subset of the LABELS list in "
        "app/services/disease_service.py — keep them in sync."
    )

    augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal"),
            tf.keras.layers.RandomRotation(0.1),
            tf.keras.layers.RandomZoom(0.1),
            tf.keras.layers.RandomContrast(0.1),
        ]
    )
    train_ds = train_ds.map(lambda x, y: (augmentation(x, training=True), y))

    model, base_model = build_model(num_classes=len(class_names))

    print("Stage 1: training classification head with frozen base...")
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs)

    print("Stage 2: fine-tuning top layers of MobileNetV2...")
    base_model.trainable = True
    for layer in base_model.layers[:-30]:
        layer.trainable = False
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-5),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(train_ds, validation_data=val_ds, epochs=args.fine_tune_epochs)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(output_path)
    print(f"Saved trained model to {output_path}")
    print("Set DISEASE_MODEL_DEMO_MODE=False in the backend .env to activate it.")


if __name__ == "__main__":
    main()
