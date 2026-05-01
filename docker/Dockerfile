FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建基础工具
RUN apt update && apt install -y git

COPY . .

# 解决 git 安全目录问题，确保 dynamic-versioning 能读取到标签
# 全面切换为 pip 安装，避开 poetry.lock 哈希冲突
RUN git config --global --add safe.directory /app && \
    python -m pip install --upgrade pip && \
    python -m pip install . poetry-dynamic-versioning


FROM python:3.12-slim AS runner

WORKDIR /app

# 从 builder 阶段拷贝已安装依赖的 python 环境（位于 site-packages）
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/javsp /usr/local/bin/javsp

# 拷贝核心资源文件到 site-packages (程序 resource_path 逻辑要求)
COPY --from=builder /app/data /usr/local/lib/python3.12/site-packages/data
COPY --from=builder /app/image /usr/local/lib/python3.12/site-packages/image

# 拷贝默认配置文件
COPY --from=builder /app/config.yml /app/config.yml

ENTRYPOINT ["javsp"]
CMD ["-i", "/video"]
