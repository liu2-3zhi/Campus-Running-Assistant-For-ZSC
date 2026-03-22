@echo off
REM 尝试设置为 UTF-8 输出（需在支持 UTF-8 的控制台中运行）
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 注意：请确保此文件以 "UTF-8 带 BOM" 编码保存，以便 Windows cmd 正确显示中文。
REM 在编辑器中选择保存为 UTF-8 with BOM（有些编辑器默认为无 BOM）。

REM 可配置变量
set "IMAGE_NAME=python_runing-python-running-helper"
set "REGISTRY_PREFIX=hongkong.zelly.cn/python_runing-python-running-helper"
set "TAG=%REGISTRY_PREFIX%/%IMAGE_NAME%:latest"
set "TEMP_TAG=%IMAGE_NAME%:build-temp"

echo 开始构建 %TEMP_TAG% ...
docker build -t %TEMP_TAG% .
if errorlevel 1 (
	echo 构建失败，已中止。
	exit /b 1
)

echo 为镜像打tag：%TAG% ...
docker tag %TEMP_TAG% %TAG%
if errorlevel 1 (
	echo 打tag失败，已中止。
	exit /b 1
)

echo 开始推送 %TAG% ...
docker push %TAG%
if errorlevel 1 (
	echo 推送失败，已中止。
	exit /b 1
)

REM 获取推送后的镜像 ID
set "PUSHED_ID="
for /f "tokens=1,2" %%A in ('docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" ^| findstr /b /c:"%TAG% "') do (
	set "PUSHED_ID=%%B"
)

if "%PUSHED_ID%"=="" (
	echo 无法确定已推送的镜像 ID，已中止。
	exit /b 1
)

echo 清理本地镜像，仅保留 %TAG% (ID=%PUSHED_ID%) ...
for /f "tokens=1,2" %%A in ('docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" ^| findstr /i "%IMAGE_NAME%"') do (
	set "REPO_TAG=%%A"
	set "IMGID=%%B"
	if not "!IMGID!"=="%PUSHED_ID%" (
		echo 正在移除镜像 !IMGID! ...
		docker rmi -f !IMGID! || echo 移除镜像 !IMGID! 失败
	)
)

echo 清理悬空镜像...
docker image prune -f
echo 正在删除临时标签 %TEMP_TAG% ...
docker rmi -f %TEMP_TAG% || echo 删除临时标签 %TEMP_TAG% 失败

echo 完成。
endlocal