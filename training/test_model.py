import json
import os

import numpy as np
from tensorflow import keras

# Load configuration
DATA_DIR = "infantry-61/icons/"
IMG_SIZE = (32, 32)
COLOR_MODE = "rgb"

# Load the saved model
model = keras.models.load_model("icons_model.keras")

# Load class names
with open("icons_model.json", "r") as f:
    class_names = json.load(f)

# Create a dataset from the directory
test_ds = keras.utils.image_dataset_from_directory(
    DATA_DIR, shuffle=False, image_size=IMG_SIZE, batch_size=32, color_mode=COLOR_MODE
)

# Get file paths
file_paths = test_ds.file_paths

# Make predictions
predictions = model.predict(test_ds)
predicted_classes = np.argmax(predictions, axis=1)

# Get true labels
true_labels = []
for _, labels in test_ds.as_numpy_iterator():
    true_labels.extend(labels)

# Calculate accuracy
accuracy = np.mean(predicted_classes == true_labels)
print(f"Overall accuracy: {accuracy:.2%}")

# Print class-wise accuracy
class_correct = [0] * len(class_names)
class_total = [0] * len(class_names)

for true_label, pred_label in zip(true_labels, predicted_classes):
    class_total[true_label] += 1
    if true_label == pred_label:
        class_correct[true_label] += 1

print("\nMisclassified images:")
misclassified = {}
for file_path, true_label, pred_label in zip(file_paths, true_labels, predicted_classes):
    if true_label != pred_label:
        misclassified[file_path] = (true_label, pred_label)

for file_path, (true_label, pred_label) in misclassified.items():
    file_name = os.path.basename(file_path)
    print(
        f"File: {file_path:<40} | {class_names[pred_label]:<40} | {np.max(predictions[true_labels.index(true_label)]):.2%}"
    )
