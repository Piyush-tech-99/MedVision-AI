"""Train an EfficientNetB0 brain-MRI tumour research classifier.

Expected dataset layout:
  dataset/Training/<class_name>/*.(jpg|jpeg|png)
  dataset/Testing/<class_name>/*.(jpg|jpeg|png)

Use only a dataset whose terms permit this use. Keep patient-level separation
when patient identifiers are available. The common Kaggle folder dataset may
not provide patient IDs, so its image-level split is not clinical validation.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True, help='Folder containing Training/ and Testing/')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent / 'model')
    parser.add_argument('--epochs', type=int, default=12)
    args = parser.parse_args()
    train_dir, test_dir = args.data_dir / 'Training', args.data_dir / 'Testing'
    if not train_dir.is_dir() or not test_dir.is_dir():
        raise SystemExit('Expected --data-dir/Training and --data-dir/Testing folders.')

    train_ds = keras.utils.image_dataset_from_directory(
        train_dir, validation_split=0.2, subset='training', seed=SEED,
        image_size=IMG_SIZE, batch_size=BATCH_SIZE, label_mode='categorical')
    val_ds = keras.utils.image_dataset_from_directory(
        train_dir, validation_split=0.2, subset='validation', seed=SEED,
        image_size=IMG_SIZE, batch_size=BATCH_SIZE, label_mode='categorical')
    test_ds = keras.utils.image_dataset_from_directory(
        test_dir, shuffle=False, image_size=IMG_SIZE,
        batch_size=BATCH_SIZE, label_mode='categorical')
    class_names = train_ds.class_names
    if class_names != test_ds.class_names:
        raise SystemExit(f'Training/testing class folders differ: {class_names} vs {test_ds.class_names}')

    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.prefetch(autotune)
    val_ds = val_ds.prefetch(autotune)
    test_ds = test_ds.prefetch(autotune)

    augmentation = keras.Sequential([
        layers.RandomRotation(0.04),
        layers.RandomZoom(0.08),
        layers.RandomContrast(0.08),
    ], name='augmentation')
    base = keras.applications.EfficientNetB0(
        include_top=False, weights='imagenet', input_shape=(*IMG_SIZE, 3))
    base.trainable = False
    inputs = keras.Input(shape=(*IMG_SIZE, 3), name='mri_image')
    x = augmentation(inputs)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D(name='global_average_pooling')(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(len(class_names), activation='softmax', name='predictions')(x)
    model = keras.Model(inputs, outputs, name='medvision_brain_mri_efficientnetb0')
    model.compile(optimizer=keras.optimizers.Adam(1e-3),
                  loss='categorical_crossentropy', metrics=['accuracy'])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    callbacks = [
        keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True, monitor='val_loss'),
        keras.callbacks.ModelCheckpoint(args.output_dir / 'brain_mri_model.keras',
                                        save_best_only=True, monitor='val_loss'),
        keras.callbacks.ReduceLROnPlateau(patience=2, factor=0.3),
    ]
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs, callbacks=callbacks)

    # Evaluate the held-out dataset. These metrics describe this dataset only.
    best = keras.models.load_model(args.output_dir / 'brain_mri_model.keras')
    loss, accuracy = best.evaluate(test_ds, verbose=0)
    predictions = best.predict(test_ds, verbose=0).argmax(axis=1)
    actual = tf.concat([y for _, y in test_ds], axis=0).numpy().argmax(axis=1)
    from sklearn.metrics import classification_report, confusion_matrix
    report = classification_report(actual, predictions, target_names=class_names,
                                   output_dict=True, zero_division=0)
    metadata = {
        'model_name': 'EfficientNetB0 brain MRI research classifier',
        'classes': class_names, 'image_size': list(IMG_SIZE),
        'test_loss': float(loss), 'test_accuracy': float(accuracy),
        'classification_report': report,
        'confusion_matrix': confusion_matrix(actual, predictions).tolist(),
        'dataset_note': 'Image-level split; not clinical validation. Use patient-level separation when IDs are available.'
    }
    (args.output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps({'classes': class_names, 'test_accuracy': accuracy,
                      'model': str(args.output_dir / 'brain_mri_model.keras')}, indent=2))

if __name__ == '__main__':
    main()
