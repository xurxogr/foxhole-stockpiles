FROM python:3.11-slim

# Install dependencies
WORKDIR /code
COPY ./docker/requirements.txt /code/requirements.txt
RUN python -m pip install --upgrade pip && pip3 install --no-cache-dir --upgrade -r ./requirements.txt


# Install python files
COPY ./foxhole_stockpiles /code/foxhole_stockpiles

CMD ["uvicorn", "foxhole_stockpiles.server:root_app", "--host", "0.0.0.0", "--port", "8010", "--log-level", "info"]
