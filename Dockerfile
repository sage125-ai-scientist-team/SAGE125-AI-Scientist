# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/sage125

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        fonts-noto-cjk \
        libcairo2 \
        libffi8 \
        libgdk-pixbuf-2.0-0 \
        libgomp1 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 sage125 \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --shell /usr/sbin/nologin \
        sage125

WORKDIR /opt/sage125

COPY requirements.txt ./requirements.txt
# 首页 CCv2 组件（tsParticles + Magic UI）以可编辑方式安装，需要在
# `pip install -r requirements.txt` 之前就位；只包含 Python 包清单和已经
# 本地构建好的 frontend/build 产物，不在镜像内运行 npm。
COPY --chown=10001:10001 frontend_components ./frontend_components
RUN python -m pip install --no-cache-dir -r requirements.txt

# Runtime files are copied from an allowlisted build context.  No repository
# root, .env, tests, local data, exports, or VCS metadata enters the image.
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 scripts ./scripts

RUN mkdir -p \
        /opt/sage125/data \
        /var/lib/sage125/exports \
        /var/lib/sage125/multimodal \
    && chown -R 10001:10001 /var/lib/sage125 /opt/sage125

USER 10001:10001

EXPOSE 8000 8501

CMD ["python", "-m", "scripts.start_api"]
