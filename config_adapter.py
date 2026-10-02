from __future__ import annotations

import ast
import configparser
import json
import os
import tempfile
import threading


class JsonConfigAdapter:
    """
    configparser.RawConfigParser 兼容适配器，底层使用 JSON 文件存储。

    JSON 文件格式（与 config.ini 一一对应）：
    {
      "SectionName": {
        "key": "value",
        ...
      },
      ...
    }

    实现了 configparser 中常用的接口：
      get / getint / getfloat / getboolean / has_section / has_option /
      set / remove_option / add_section / sections / options / items / write
    """

    default_write_lock = None

    def __init__(self, json_path: str, write_lock=None):
        self._path = json_path
        self._write_lock = write_lock or self.default_write_lock or threading.RLock()
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        # 规范化：所有 section/key 保持原始大小写，值统一为字符串
        self._data: dict = {}
        for sec, opts in raw.items():
            if isinstance(opts, dict):
                self._data[sec] = {}
                for k, v in opts.items():
                    if sec == "Map" and k == "providers":
                        self._data[sec][k] = self._coerce_map_providers(v)
                    else:
                        self._data[sec][k] = str(v)
            else:
                self._data[sec] = {}

    @staticmethod
    def _coerce_map_providers(value):
        if isinstance(value, dict):
            source = value
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            source = {}
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(text)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    source = parsed
                    break
        else:
            return {}

        normalized = {}
        for provider_name, provider_values in source.items():
            if isinstance(provider_values, dict):
                normalized[str(provider_name)] = {
                    key: str(value) for key, value in provider_values.items()
                }
        return normalized

    # ── 读取接口 ──────────────────────────────────────────────────────────

    def sections(self):
        return list(self._data.keys())

    def has_section(self, section: str) -> bool:
        return section in self._data

    def options(self, section: str):
        if section not in self._data:
            raise configparser.NoSectionError(section)
        return list(self._data[section].keys())

    def has_option(self, section: str, option: str) -> bool:
        return section in self._data and option in self._data[section]

    def get(self, section: str, option: str, fallback=configparser._UNSET):
        try:
            return self._data[section][option]
        except KeyError:
            if fallback is not configparser._UNSET:
                return fallback
            raise configparser.NoOptionError(option, section)

    def getint(self, section: str, option: str, fallback=configparser._UNSET):
        v = self.get(section, option, fallback=fallback)
        try:
            return int(v)
        except (ValueError, TypeError):
            return fallback if fallback is not configparser._UNSET else 0

    def getfloat(self, section: str, option: str, fallback=configparser._UNSET):
        v = self.get(section, option, fallback=fallback)
        try:
            return float(v)
        except (ValueError, TypeError):
            return fallback if fallback is not configparser._UNSET else 0.0

    def getboolean(self, section: str, option: str, fallback=configparser._UNSET):
        v = self.get(section, option, fallback=fallback)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            if v.lower() in ("true", "yes", "1", "on"):
                return True
            if v.lower() in ("false", "no", "0", "off"):
                return False
        return bool(fallback) if fallback is not configparser._UNSET else False

    def items(self, section: str = None, raw: bool = False):
        if section is None:
            return list(self._data.items())
        if section not in self._data:
            raise configparser.NoSectionError(section)
        return list(self._data[section].items())

    # ── 写入接口 ──────────────────────────────────────────────────────────

    def add_section(self, section: str):
        if section not in self._data:
            self._data[section] = {}

    def set(self, section: str, option: str, value: str = None):
        if section not in self._data:
            self._data[section] = {}
        if section == "Map" and option == "providers":
            self._data[section][option] = self._coerce_map_providers(value)
        else:
            self._data[section][option] = str(value) if value is not None else ""

    def remove_option(self, section: str, option: str) -> bool:
        if section in self._data and option in self._data[section]:
            del self._data[section][option]
            return True
        return False

    def remove_section(self, section: str) -> bool:
        if section in self._data:
            del self._data[section]
            return True
        return False

    def write(self, fileobj=None):
        """将当前配置写回 JSON 文件（fileobj 参数保留以兼容 configparser 接口）。"""
        abs_path = os.path.abspath(self._path)
        parent_dir = os.path.dirname(abs_path)
        os.makedirs(parent_dir, exist_ok=True)
        with self._write_lock:
            data = {}
            for section, options in self._data.items():
                if not isinstance(options, dict):
                    data[section] = {}
                    continue
                section_data = {}
                has_provider_map = section == "Map" and isinstance(options.get("providers"), dict)
                for key, value in options.items():
                    if has_provider_map and key in {
                        "amap_js_key",
                        "tencent_map_key",
                        "tianditu_token",
                        "baidu_map_ak",
                    }:
                        continue
                    section_data[key] = value if isinstance(value, dict) else str(value)
                data[section] = section_data
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False, dir=parent_dir, suffix=".tmp"
            ) as tmpf:
                json.dump(data, tmpf, indent=2, ensure_ascii=False)
                tmp_path = tmpf.name
            os.replace(tmp_path, abs_path)

    def save(self):
        """显式保存到 JSON 文件的便捷方法。"""
        self.write()

    # ── 兼容性辅助 ────────────────────────────────────────────────────────

    def read(self, filename, encoding=None):
        """兼容 configparser.read() 接口，重新加载文件。"""
        try:
            with open(filename, "r", encoding=encoding or "utf-8") as f:
                raw = json.load(f)
            self._data = {}
            for sec, opts in raw.items():
                if not isinstance(opts, dict):
                    self._data[sec] = {}
                    continue
                self._data[sec] = {}
                for k, v in opts.items():
                    if sec == "Map" and k == "providers":
                        self._data[sec][k] = self._coerce_map_providers(v)
                    else:
                        self._data[sec][k] = str(v)
            self._path = filename
        except Exception:
            pass

    # 让 optionxform 可以被赋值（兼容 config.optionxform = str 调用）
    @property
    def optionxform(self):
        return str

    @optionxform.setter
    def optionxform(self, value):
        pass  # JSON 适配器始终保留原始大小写，无需处理
