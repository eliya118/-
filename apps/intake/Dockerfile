FROM python:3.13.18-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS build
RUN pip install --no-cache-dir uv==0.13.8
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs ./libs
COPY apps/calendar ./apps/calendar
COPY apps/intake ./apps/intake
COPY apps/ideas ./apps/ideas
COPY apps/notifier ./apps/notifier
RUN uv sync --frozen --package intake --no-dev --no-editable

FROM python:3.13.18-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS test
RUN pip install --no-cache-dir uv==0.13.8
WORKDIR /app
COPY . .
RUN uv sync --frozen --all-packages --group dev --no-editable
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
CMD ["pytest", "-q", "apps/intake/tests"]

FROM python:3.13.18-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS runtime
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY apps/intake/entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
