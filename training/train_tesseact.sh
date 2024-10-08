#!/bin/bash

cd tesstrain
ITERATIONS=10000

TESSDATA_PREFIX=../tesseract/tessdata make training MODEL_NAME=rennereng START_MODEL=eng TESSDATA=../tesseract/tessdata MAX_ITERATIONS=${ITERATIONS}
TESSDATA_PREFIX=../tesseract/tessdata make training MODEL_NAME=rennernumbers START_MODEL=eng TESSDATA=../tesseract/tessdata MAX_ITERATIONS=${ITERATIONS}

cd ..
