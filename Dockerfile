FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
ARG INSTALL_AKSHARE=0
RUN if [ "$INSTALL_AKSHARE" = "1" ]; then pip install --no-cache-dir ".[akshare]"; else pip install --no-cache-dir .; fi
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["stock-auto"]
CMD ["--help"]
