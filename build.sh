#!/usr/bin/env bash
set -euo pipefail

# 可配置变量
IMAGE_NAME="python_runing-python-running-helper"
REGISTRY_PREFIX="hongkong.zelly.cn/python_runing-python-running-helper"
TAG="${REGISTRY_PREFIX}/${IMAGE_NAME}:latest"
TEMP_TAG="${IMAGE_NAME}:build-temp"

echo "开始构建镜像 ${TEMP_TAG}..."
docker build -t "${TEMP_TAG}" .
echo "构建成功。准备打tag -> ${TAG}"
docker tag "${TEMP_TAG}" "${TAG}"

echo "开始推送 ${TAG}..."
docker push "${TAG}"

echo "推送完成，开始清理本地旧镜像，保留 ${TAG} 对应的镜像镜像ID..."
# 获取已推送镜像的 ID
PUSHED_ID=$(docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | awk -v t="$TAG" '$1==t{print $2}')
if [ -z "${PUSHED_ID}" ]; then
	echo "无法找到推送后的镜像 ID (${TAG})，中止清理。" >&2
	exit 1
fi

# 收集与本项目镜像名称相关的所有 image id（去重），移除除 PUSHED_ID 之外的镜像
mapfile -t IDS < <(docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | awk '/python_runing-python-running-helper/ {print $2}' | sort -u)
for id in "${IDS[@]}"; do
	if [ "${id}" != "${PUSHED_ID}" ]; then
		echo "移除镜像 ${id}..."
		docker rmi -f "${id}" || true
	fi
done

echo "清理悬空镜像..."
docker image prune -f || true

echo "删除临时镜像标签 ${TEMP_TAG}..."
docker rmi -f "${TEMP_TAG}" || true

echo "任务完成。已删除临时标签 ${TEMP_TAG}，仅保留 ${TAG} 的镜像标签。"