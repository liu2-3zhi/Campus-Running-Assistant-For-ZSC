from __future__ import annotations

import datetime
import logging
import os
import ssl

import cryptography


def _main():
    import main
    return main


def load_ssl_config():
    """
    从 config.json 文件加载SSL配置。
    """
    config_file = os.path.join(os.path.dirname(__file__), _main().CONFIG_JSON_FILE)
    default_config = {
        "ssl_enabled": False,
        "ssl_cert_path": "ssl/fullchain.pem",
        "ssl_key_path": "ssl/privkey.key",
        "https_only": False,
    }

    try:
        if not os.path.exists(config_file):
            logging.warning(f"配置文件 {config_file} 不存在，使用默认SSL配置（禁用）")
            return default_config
        config = _main()._read_config_ini(config_file)
        if not config or not config.has_section("SSL"):
            logging.warning("配置文件中未找到[SSL]节，使用默认SSL配置（禁用）")
            return default_config
        ssl_config = {
            "ssl_enabled": config.getboolean("SSL", "ssl_enabled", fallback=False),
            "ssl_cert_path": config.get(
                "SSL", "ssl_cert_path", fallback="ssl/fullchain.pem"
            ),
            "ssl_key_path": config.get(
                "SSL", "ssl_key_path", fallback="ssl/privkey.key"
            ),
            "https_only": config.getboolean("SSL", "https_only", fallback=False),
        }
        logging.info(
            f"SSL配置加载成功: enabled={ssl_config['ssl_enabled']}, https_only={ssl_config['https_only']}"
        )

        return ssl_config

    except Exception as e:
        logging.error(f"加载SSL配置时发生错误: {e}，使用默认配置（禁用SSL）")
        return default_config


def save_ssl_config(ssl_config):
    """
    将SSL配置保存到config.json文件。

    参数：
        ssl_config (dict): 包含SSL配置的字典，键应包括：
            - ssl_enabled (bool): 是否启用SSL
            - ssl_cert_path (str): 证书文件路径
            - ssl_key_path (str): 私钥文件路径
            - https_only (bool): 是否仅允许HTTPS访问

    返回值：
        bool: 保存成功返回True，失败返回False
    """
    config_file = os.path.join(os.path.dirname(__file__), _main().CONFIG_JSON_FILE)
    config = _main()._read_config_ini(config_file)

    try:
        if not config:
            logging.warning("config.json 文件不存在或读取失败，将创建新的配置文件")
            config = _main()._get_default_config()
        if not config.has_section("SSL"):
            config.add_section("SSL")
        config.set(
            "SSL", "ssl_enabled", str(
                ssl_config.get("ssl_enabled", False)).lower()
        )
        config.set(
            "SSL", "ssl_cert_path", ssl_config.get(
                "ssl_cert_path", "ssl/fullchain.pem")
        )
        config.set(
            "SSL", "ssl_key_path", ssl_config.get(
                "ssl_key_path", "ssl/privkey.key")
        )
        config.set(
            "SSL", "https_only", str(
                ssl_config.get("https_only", False)).lower()
        )
        _main()._write_config_with_comments(config, config_file)

        logging.info("SSL配置已成功保存到配置文件")
        return True

    except Exception as e:
        logging.error(f"保存SSL配置时发生错误: {e}")
        return False


# ============================================================================

def validate_ssl_certificate(cert_path, key_path):
    """
    验证SSL证书文件和密钥文件是否有效。
    """
    if not os.path.isabs(cert_path):
        cert_path = os.path.join(os.path.dirname(__file__), cert_path)
    if not os.path.isabs(key_path):
        key_path = os.path.join(os.path.dirname(__file__), key_path)
    if not os.path.exists(cert_path):
        error_msg = f"证书文件不存在: {cert_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    if not os.path.exists(key_path):
        error_msg = f"密钥文件不存在: {key_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    if not os.access(cert_path, os.R_OK):
        error_msg = f"证书文件不可读（权限不足）: {cert_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    if not os.access(key_path, os.R_OK):
        error_msg = f"密钥文件不可读（权限不足）: {key_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    try:
        with open(cert_path, "r", encoding="utf-8") as f:
            cert_content = f.read()
            if "-----BEGIN CERTIFICATE-----" not in cert_content:
                error_msg = f"证书文件格式无效（不是PEM格式）: {cert_path}"
                logging.error(error_msg)
                return False, error_msg, {}
    except Exception as e:
        error_msg = f"读取证书文件时发生错误: {e}"
        logging.error(error_msg)
        return False, error_msg, {}
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            key_content = f.read()
            valid_key_headers = [
                "-----BEGIN PRIVATE KEY-----",
                "-----BEGIN RSA PRIVATE KEY-----",
                "-----BEGIN EC PRIVATE KEY-----",
                "-----BEGIN DSA PRIVATE KEY-----",
            ]
            if not any(header in key_content for header in valid_key_headers):
                error_msg = f"密钥文件格式无效（不是PEM格式）: {key_path}"
                logging.error(error_msg)
                return False, error_msg, {}
    except Exception as e:
        error_msg = f"读取密钥文件时发生错误: {e}"
        logging.error(error_msg)
        return False, error_msg, {}
    cert_info = {
        "cert_path": cert_path,
        "key_path": key_path,
        "valid": True,
        "message": "证书文件格式验证通过",
    }
    try:
        # import ssl

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        cert_info["message"] = "证书和密钥验证通过，可以安全使用"
        logging.info(f"SSL证书验证成功: {cert_path}")

    except Exception as e:
        error_msg = f"SSL证书深度验证失败: {e}，但基础格式验证已通过"
        logging.warning(error_msg)
        cert_info["message"] = error_msg
    return True, "", cert_info


def get_ssl_certificate_info(cert_path):
    """
    获取SSL证书的详细信息（如有效期、颁发者、主题等）。
    """
    if not os.path.isabs(cert_path):
        cert_path = os.path.join(os.path.dirname(__file__), cert_path)

    # 在打开文件前检查文件是否存在
    # 如果证书文件不存在，返回友好的错误信息而不记录ERROR日志
    # 这是预期的情况（证书未上传或已被删除），不是系统错误
    if not os.path.exists(cert_path):
        return {
            "error": "证书文件不存在",
            "path": cert_path,
            "message": "请先上传SSL证书"
        }

    cert_info = {}

    try:
        # import ssl
        # from datetime import datetime

        with open(cert_path, "rb") as f:
            cert_data = f.read()

        # from cryptography.hazmat.backends import default_backend

        cert = cryptography.x509.load_pem_x509_certificate(cert_data, cryptography.hazmat.backends.default_backend())
        cert_info = {
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "version": cert.version.name,
            "serial_number": str(cert.serial_number),
            "not_before": cert.not_valid_before_utc.isoformat(),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "is_expired": datetime.datetime.now()
            > cert.not_valid_after_utc.replace(tzinfo=None),
        }
        try:
            san_ext = cert.extensions.get_extension_for_class(
                cryptography.x509.SubjectAlternativeName
            )
            cert_info["san"] = [name.value for name in san_ext.value]
        except cryptography.x509.ExtensionNotFound:
            cert_info["san"] = []

        logging.info(f"成功获取证书信息: {cert_path}")

    # except ImportError:
    #     logging.warning("cryptography库不可用，无法获取详细的证书信息")
    #     cert_info = {
    #         "error": "需要安装cryptography库才能查看详细证书信息",
    #         "install_hint": "pip install cryptography",
    #     }
    except Exception as e:
        # 只在真正的异常情况下（如证书格式错误、读取权限问题等）记录ERROR日志
        logging.error(f"获取证书信息时发生错误: {e}")
        cert_info = {"error": f"读取证书信息失败: {str(e)}"}

    return cert_info
