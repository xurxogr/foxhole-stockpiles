FROM python:3.11

# Install dependencies
WORKDIR /code
RUN apt update && apt install -y musl-dev g++ libgl1 \
    tesseract-ocr libtesseract-dev \
    tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-deu tesseract-ocr-rus tesseract-ocr-chi-sim tesseract-ocr-por

COPY ./docker/requirements.txt /code/requirements.txt
RUN python -m pip install --upgrade pip
RUN --mount=type=cache,target=/root.cache pip3 install -r ./requirements.txt

# Install python files
COPY ./foxhole_stockpiles /code/foxhole_stockpiles

CMD ["uvicorn", "foxhole_stockpiles.server:root_app", "--host", "0.0.0.0", "--port", "8010", "--log-level", "info"]
