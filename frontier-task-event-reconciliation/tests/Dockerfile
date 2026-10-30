FROM python:3.11-slim-bookworm
RUN pip install --no-cache-dir pytest==9.1.1 pytest-json-ctrf==0.5.2
RUN useradd -m -u 1000 candidate
WORKDIR /tests
COPY . /tests/
RUN chmod +x /tests/test.sh
