import time
import json
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def base64url_encode(data):
    """
    实现 JWT 规范要求的 Base64URL 编码：
    1. 使用 URL 安全的字符表 (-_)
    2. 去除末尾的填充等号 (=)
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    encoded = base64.urlsafe_b64encode(data)
    return encoded.decode('utf-8').rstrip('=')


def format_private_key(raw_key):
    """格式化私钥 (同前，确保 PEM 格式正确)"""
    if not raw_key:
        raise ValueError("私钥不能为空")
    key_content = raw_key.strip()
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"
    if not key_content.startswith(header):
        key_content = header + "\n" + key_content
    else:
        if not key_content.startswith(header + "\n"):
            key_content = key_content.replace(header, header + "\n", 1)
    if not key_content.endswith(footer):
        key_content = key_content + "\n" + footer
    else:
        if not key_content.endswith("\n" + footer):
            key_content = key_content.replace(footer, "\n" + footer, 1)
    return key_content


def generate_strict_token():
    # ---------------- 配置区域 ----------------
    # 凭据ID
    KEY_ID = "TAGXVCYU3Q"
    # 项目ID
    PROJECT_ID = "3B89A55XRT"
    # 私钥内容 (PEM 格式)
    PRIVATE_KEY_RAW = """
    -----BEGIN PRIVATE KEY-----
    MC4CAQAwBQYDK2VwBCIEII/A+il+JwWXZPWcd4tCZVV/geF6N5DOMQr2FPO6sOSL
    -----END PRIVATE KEY-----
    """
    # Token 有效期 (秒)
    EXPIRATION_SECONDS = 60
    # ----------------------------------------

    try:
        # 1. 准备私钥对象
        pem_key = format_private_key(PRIVATE_KEY_RAW).encode('utf-8')
        private_key = serialization.load_pem_private_key(
            pem_key, password=None)

        # 检查是否为 Ed25519 私钥
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("提供的私钥不是 Ed25519 格式")

        # 2. 手动构建 Header (严格控制字段)
        # 仅包含 alg 和 kid，绝对不含 typ
        header_dict = {
            "alg": "EdDSA",
            "kid": KEY_ID
        }

        # 3. 手动构建 Payload (严格控制字段)
        # 仅包含 sub, iat, exp，绝对不含 iss, aud, nbf
        current_time = int(time.time())
        payload_dict = {
            "sub": PROJECT_ID,
            "iat": current_time - 30,
            "exp": current_time + EXPIRATION_SECONDS
        }

        # 4. JSON 序列化并 Base64URL 编码
        # separators=(',', ':') 用于去除 JSON 中的空格，减小体积
        header_json = json.dumps(
            header_dict, separators=(',', ':')).encode('utf-8')
        payload_json = json.dumps(
            payload_dict, separators=(',', ':')).encode('utf-8')

        header_b64 = base64url_encode(header_json)
        payload_b64 = base64url_encode(payload_json)

        # 5. 拼接签名原始内容
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')

        # 6. 进行 Ed25519 签名
        signature = private_key.sign(signing_input)
        signature_b64 = base64url_encode(signature)

        # 7. 组合最终 Token
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        auth_header = f"Bearer {token}"

        print("=== 生成成功 (已移除保留字段 typ/iss/aud/nbf) ===")
        print(f"Header JSON:  {header_dict}")
        print(f"Payload JSON: {payload_dict}")
        print(auth_header)

        return auth_header

    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    generate_strict_token()
