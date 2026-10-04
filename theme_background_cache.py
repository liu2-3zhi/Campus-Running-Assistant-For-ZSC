from __future__ import annotations

import datetime
import logging
import mimetypes
import os
import threading


def _main():
    import main
    return main


def _ensure_random_background_cache_count(
    cache_dir,
    api_key,
    image_type,
    target_count=5,
):
    logging.info(f"[主题背景] 确保 {image_type} 背景缓存数量至少为 {target_count} 张...")
    target_count = max(int(target_count or 0), 0)
    if target_count == 0:
        logging.info(f"[主题背景] 目标缓存数量为 0，跳过 {image_type} 背景缓存检查")
        return

    available_count = len(
        [
            file_name
            for file_name in os.listdir(cache_dir)
            if os.path.isfile(os.path.join(cache_dir, file_name))
            and file_name != "index.json"
            and file_name.startswith(f"{image_type}_")
        ]
    )
    missing_count = max(target_count - available_count, 0)
    logging.info(f"[主题背景] {image_type} 背景缓存缺失 {missing_count} 张")
    if missing_count == 0:
        return

    _main().Api(_main().args)
    for _ in range(missing_count):
        try:
            logging.info(f"[主题背景] 正在拉取新的 {image_type} 随机背景图以补足缓存...")
            _main()._fetch_random_background_image(cache_dir, api_key, image_type)
        except Exception as e:
            logging.warning(f"[主题背景] 补足 {image_type} 背景缓存失败: {e}")
            break
        logging.info(f"[主题背景] 已完成一次 {image_type} 背景图拉取尝试以补足缓存")


def _start_default_theme_background_cache_warmup():
    main_module = _main()
    with main_module._THEME_BACKGROUND_WARMUP_LOCK:
        if main_module._THEME_BACKGROUND_WARMUP_IN_PROGRESS:
            logging.info("[主题背景] 启动预热线程已在执行，跳过重复启动")
            return
        main_module._THEME_BACKGROUND_WARMUP_IN_PROGRESS = True

    logging.info("[主题背景] 启动时预下载背景缓存线程正在启动...")

    def _worker():
        try:
            logging.info("[主题背景] 启动时预下载背景缓存线程已启动")
            config = (
                _main()._read_config_ini(_main().CONFIG_JSON_FILE)
                or _main()._get_default_config()
            )
            api_key = config.get(
                "IP_Location",
                "uapipro_api_key",
                fallback="",
            ).strip()
            if not api_key:
                logging.info("[主题背景] 未配置 UapiPro API Key，跳过启动预下载缓存")
                return

            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
            os.makedirs(cache_dir, exist_ok=True)

            index_data = _main()._load_random_background_index(cache_dir)
            _main()._save_random_background_index(cache_dir, index_data)

            for image_type in ("pc", "mb"):
                _main()._ensure_random_background_cache_count(
                    cache_dir,
                    api_key,
                    image_type,
                    target_count=_main().BACKGROUND_CACHE_TARGET_COUNT,
                )

            try:
                _main()._cleanup_random_background_cache(cache_dir)
            except Exception as cleanup_error:
                logging.warning(f"[主题背景] 启动预热后清理缓存失败: {cleanup_error}")
        except Exception as e:
            logging.warning(f"[主题背景] 启动时预下载背景缓存失败: {e}", exc_info=True)
        finally:
            with _main()._THEME_BACKGROUND_WARMUP_LOCK:
                _main()._THEME_BACKGROUND_WARMUP_IN_PROGRESS = False

    threading.Thread(
        target=_worker,
        name="ThemeBackgroundWarmup",
        daemon=True,
    ).start()


def _fetch_random_background_image(cache_dir, api_key, image_type):
    url = f"https://uapis.cn/api/v1/random/image?category=acg&type={image_type}"
    headers = {"Authorization": f"Bearer {api_key}"}
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = _main().requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                content_type = (
                    response.headers.get("Content-Type") or ""
                ).split(";")[0].strip().lower()
                extension = mimetypes.guess_extension(content_type) or ".jpg"
                if extension == ".jpe":
                    extension = ".jpg"
                timestamp = datetime.datetime.now().strftime(
                    "%Y-%m-%d-%H-%M-%S-%f"
                )[:-3]
                file_name = f"{image_type}_{timestamp}{extension}"
                file_path = os.path.join(cache_dir, file_name)
                with open(file_path, "wb") as file:
                    file.write(response.content)

                _main()._mark_random_background_file_state(
                    cache_dir,
                    file_name,
                    image_type=image_type,
                    expired=False,
                    created_at=datetime.datetime.now().isoformat(timespec="seconds"),
                    last_used_at=None,
                    expired_at=None,
                )
                _main()._cleanup_random_background_cache(cache_dir)
                return _main()._build_theme_background_image_url(
                    f"{_main().RANDOM_BACKGROUND_IMAGE_DIR}/{file_name}"
                )

            if response.status_code == 404:
                logging.warning(f"[主题背景] 未找到类型为 {image_type} 的随机背景图")
                return ""

            logging.warning(
                f"[主题背景] 拉取 {image_type} 随机背景图失败，"
                f"状态码: {response.status_code}，第 {attempt} 次尝试"
            )
        except _main().requests.exceptions.RequestException as e:
            logging.warning(
                f"[主题背景] 拉取 {image_type} 随机背景图异常，"
                f"第 {attempt} 次尝试: {e}"
            )

    return ""


def _build_theme_background_image_url(relative_path):
    normalized_path = str(relative_path or "").replace("\\", "/").strip("/")
    if not normalized_path:
        return ""
    return f"/theme-assets/{normalized_path}"
