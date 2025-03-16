# @title Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Based on this tutorial:
# https://www.tensorflow.org/tutorials/images/classification

# This code is based on https://github.com/GICodeWarrior/fir/blob/main/trainer/train.py

import json

import keras
import tensorflow as tf
from keras import layers
from keras.models import Sequential

EPOCHS = 1000
COLOR_MODE = "rgb"
DROPOUT = 0.5
DATA_DIR = "icons-naval57/"
PATIENTE = 50

IMG_SIZE = (32, 32)

PREFETCH_SIZE = tf.data.AUTOTUNE
RANDOM_SEED = 4687951


def scheduler(epoch, lr):
    if epoch < 200:
        return float(lr)
    elif epoch < 600:
        return float(lr * tf.math.exp(-0.1))
    else:
        return float(lr * tf.math.exp(-0.01))


tf.random.set_seed(RANDOM_SEED)

train_ds = keras.utils.image_dataset_from_directory(
    DATA_DIR, seed=RANDOM_SEED, color_mode=COLOR_MODE, image_size=IMG_SIZE
)

class_names = train_ds.class_names
output_dim = len(class_names)

with open("icons_model.json", "w", encoding="utf-8") as f:
    f.write(json.dumps(class_names, indent=2))
    f.write("\n")

train_ds = train_ds.cache().prefetch(buffer_size=PREFETCH_SIZE)

model = Sequential(
    [
        layers.Input(shape=IMG_SIZE + (3,)),
        layers.Rescaling(1.0 / 255),
        layers.Conv2D(16, 3, padding="same", use_bias=False),
        layers.BatchNormalization(),
        layers.Activation("relu"),
        layers.MaxPooling2D(),
        layers.Dropout(DROPOUT),
        layers.Conv2D(32, 3, padding="same"),
        layers.Activation("relu"),
        layers.MaxPooling2D(),
        layers.Dropout(DROPOUT),
        layers.Flatten(),
        layers.Dense(output_dim, name="outputs"),
    ]
)

model.compile(
    optimizer="adam",
    loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=["accuracy"],
)

# Add early stopping callback
early_stopping = keras.callbacks.EarlyStopping(
    monitor="accuracy", patience=PATIENTE, restore_best_weights=True
)

model.fit(
    train_ds,
    epochs=EPOCHS,
    callbacks=[tf.keras.callbacks.LearningRateScheduler(scheduler), early_stopping],
)

model.save("icons_model.keras")
