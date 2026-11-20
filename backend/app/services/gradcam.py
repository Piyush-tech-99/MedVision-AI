"""Grad-CAM visualization for MedVision AI CNN models."""

from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import tensorflow as tf
from PIL import Image


def _prepare_image(
    image_bytes: bytes,
    target_size: tuple[int, int] = (224, 224)
):
    image = (
        Image.open(BytesIO(image_bytes))
        .convert("RGB")
        .resize(target_size)
    )

    array = np.asarray(
        image,
        dtype=np.float32
    )[None, ...]

    return image, array


def _find_last_conv_layer(model: tf.keras.Model):
    """
    Locate the final convolutional layer.

    Supports:
    - A model containing Conv2D layers directly.
    - An outer model containing a nested CNN such as EfficientNetB0.
    """

    # Prefer EfficientNet's final convolutional feature layer.
    for layer in model.layers:
        if layer.name == "top_conv":
            return model, layer

    # Check nested models.
    for layer in model.layers:
        if isinstance(layer, tf.keras.Model):
            for nested_layer in layer.layers:
                if nested_layer.name == "top_conv":
                    return layer, nested_layer

    # Fall back to the last Conv2D layer in the outer model.
    last_conv = None

    for layer in model.layers:
        if isinstance(layer, tf.keras.layers.Conv2D):
            last_conv = layer

    if last_conv is not None:
        return model, last_conv

    # Fall back to the last Conv2D layer in a nested model.
    for layer in model.layers:
        if isinstance(layer, tf.keras.Model):
            nested_conv = None

            for nested_layer in layer.layers:
                if isinstance(
                    nested_layer,
                    tf.keras.layers.Conv2D
                ):
                    nested_conv = nested_layer

            if nested_conv is not None:
                return layer, nested_conv

    raise ValueError(
        "Could not locate a convolutional layer for Grad-CAM."
    )


def _create_overlay(
    image: Image.Image,
    heatmap: np.ndarray
) -> str:

    size = image.size

    heat_image = Image.fromarray(
        np.uint8(heatmap * 255)
    ).resize(
        size,
        Image.Resampling.BILINEAR
    )

    heat_array = np.asarray(
        heat_image,
        dtype=np.uint8
    )

    color = np.zeros(
        (size[1], size[0], 3),
        dtype=np.uint8
    )

    color[..., 0] = heat_array

    color[..., 1] = np.clip(
        (heat_array.astype(float) - 80) * 1.5,
        0,
        255
    ).astype(np.uint8)

    original = np.asarray(
        image,
        dtype=np.uint8
    )

    overlay = Image.fromarray(
        np.uint8(
            original * 0.55 + color * 0.45
        )
    )

    buffer = BytesIO()

    overlay.save(
        buffer,
        format="PNG"
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return "data:image/png;base64," + encoded


def generate_gradcam(
    model: tf.keras.Model,
    image_bytes: bytes,
    class_index: int | None = None
) -> str:

    if not image_bytes:
        raise ValueError("No image data was provided to Grad-CAM.")

    if not model.built:
        input_shape = getattr(
            model,
            "input_shape",
            None
        )

        if isinstance(input_shape, list):
            input_shape = input_shape[0]

        height = (
            int(input_shape[1])
            if input_shape and input_shape[1]
            else 224
        )

        width = (
            int(input_shape[2])
            if input_shape and input_shape[2]
            else 224
        )

        model(
            np.zeros(
                (1, height, width, 3),
                dtype=np.float32
            ),
            training=False
        )

    input_shape = getattr(
        model,
        "input_shape",
        None
    )

    if isinstance(input_shape, list):
        input_shape = input_shape[0]

    height = (
        int(input_shape[1])
        if input_shape and input_shape[1]
        else 224
    )

    width = (
        int(input_shape[2])
        if input_shape and input_shape[2]
        else 224
    )

    image, array = _prepare_image(
        image_bytes,
        (width, height)
    )

    owner, last_conv = _find_last_conv_layer(model)

    # Build one connected model that returns both:
    # 1. The convolutional feature maps.
    # 2. The output of the CNN containing that convolutional layer.
    #
    # Both outputs must come from the same forward pass.
    grad_model = tf.keras.Model(
        inputs=owner.input,
        outputs=[
            last_conv.output,
            owner.output
        ]
    )

    # Identify layers before and after the nested CNN.
    pre_layers = []
    post_layers = []

    if owner is not model:
        found_owner = False

        for layer in model.layers:

            if layer is owner:
                found_owner = True
                continue

            if isinstance(
                layer,
                tf.keras.layers.InputLayer
            ):
                continue

            if not found_owner:
                pre_layers.append(layer)
            else:
                post_layers.append(layer)

    inputs_tensor = tf.convert_to_tensor(
        array,
        dtype=tf.float32
    )

    with tf.GradientTape() as tape:

        x = inputs_tensor

        # Run outer-model layers before the nested CNN.
        for layer in pre_layers:
            x = layer(
                x,
                training=False
            )

        # Get activations and CNN output together.
        conv_outputs, owner_output = grad_model(
            x,
            training=False
        )

        # Continue through any outer-model layers after the CNN.
        predictions = owner_output

        for layer in post_layers:
            predictions = layer(
                predictions,
                training=False
            )

        # Binary classification with sigmoid output.
        if predictions.shape[-1] == 1:

            positive_probability = predictions[:, 0]

            if class_index is None:
                class_index = int(
                    (
                        positive_probability[0] >= 0.5
                    ).numpy()
                )

            if class_index not in (0, 1):
                raise ValueError(
                    "Binary class_index must be 0 or 1."
                )

            if class_index == 1:
                score = positive_probability
            else:
                score = 1.0 - positive_probability

        # Multiclass classification with softmax output.
        else:

            number_of_classes = int(
                predictions.shape[-1]
            )

            if class_index is None:
                class_index = int(
                    tf.argmax(
                        predictions[0]
                    ).numpy()
                )

            if not 0 <= class_index < number_of_classes:
                raise ValueError(
                    "Invalid class_index."
                )

            score = predictions[:, class_index]

    # Calculate gradients from the selected class score
    # back to the convolutional feature maps.
    gradients = tape.gradient(
        score,
        conv_outputs
    )

    if gradients is None:
        raise ValueError(
            "Grad-CAM gradients are unavailable. "
            "Check the model architecture and convolutional layer."
        )

    # Average gradients spatially to obtain channel weights.
    weights = tf.reduce_mean(
        gradients,
        axis=(0, 1, 2)
    )

    # Weighted combination of feature maps.
    heatmap = tf.reduce_sum(
        conv_outputs[0] * weights,
        axis=-1
    )

    heatmap = tf.maximum(
        heatmap,
        0
    )

    heatmap = heatmap / (
        tf.reduce_max(heatmap)
        + tf.keras.backend.epsilon()
    )

    heatmap = heatmap.numpy()

    return _create_overlay(
        image,
        heatmap
    )