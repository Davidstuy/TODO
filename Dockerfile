# 基础镜像：Python 3.12 精简版（体积小，够用）
FROM python:3.12-slim

# 容器内的固定工作目录
WORKDIR /app

# 先复制依赖清单再安装 —— 依赖没变化时 Docker 会用缓存，不用重复下载
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制你的源代码
COPY app ./app

# 不写 CMD：容器要跑什么命令，由 docker-compose.yml 里每个服务分别指定
