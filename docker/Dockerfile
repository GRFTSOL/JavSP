FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建基础工具
RUN apt update && apt install -y git

COPY . .

# 全面切换为 pip 安装，避开 poetry.lock 哈希冲突
RUN python -m pip install --upgrade pip && \
    python -m pip install . poetry-dynamic-versioning && \
    rm -rf /app/.git


FROM python:3.12-slim AS runner

WORKDIR /app

# 从 builder 阶段拷贝已安装依赖的 python 环境（位于 site-packages）
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/javsp /usr/local/bin/javsp
COPY --from=builder /app /app

ENTRYPOINT ["javsp"]
CMD ["-i", "/video"]
