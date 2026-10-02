from __future__ import annotations

import base64
import logging
import traceback

import cryptography


class RsaSigner:
    def __init__(self, private_key_str: str = None, public_key_str: str = None):
        """
        初始化签名器（用于签名和验签）

        参数说明:
            private_key_str (str): 私钥字符串（用于签名，可以是带头尾的PEM格式，也可以是纯Base64字符串）
            public_key_str (str): 公钥字符串（用于验签，可以是带头尾的PEM格式，也可以是纯Base64字符串）

        使用场景:
            - 签名操作：需要传入 private_key_str
            - 验签操作：需要传入 public_key_str
            - 两者都传入时：可同时支持签名和验签
        """
        # 加载私钥（如果提供了私钥字符串）
        # 私钥用于生成签名（sign）操作
        self.private_key = self._load_private_key(
            private_key_str) if private_key_str else None

        # 加载公钥（如果提供了公钥字符串）
        # 公钥用于验证签名（verify）操作
        self.public_key = self._load_public_key(
            public_key_str) if public_key_str else None

    def _load_private_key(self, pk_str: str):
        """
        内部函数：处理私钥格式并加载

        功能说明:
            将私钥字符串转换为cryptography库可用的私钥对象
            支持两种输入格式：
            1. 完整的PEM格式（包含 -----BEGIN PRIVATE KEY----- 头尾）
            2. 纯Base64编码的密钥内容（自动补全头尾）

        参数:
            pk_str (str): 私钥字符串

        返回:
            私钥对象（cryptography.hazmat.primitives.asymmetric.rsa.RSAPrivateKey）

        异常:
            ValueError: 当私钥格式错误或加载失败时抛出
        """
        # 去除首尾空白字符（空格、换行等）
        pk_str = pk_str.strip()

        # 检查是否包含PEM格式的头部标识
        # 如果没有头部，说明是纯Base64字符串，需要补全标准的PEM格式头尾
        # 注意：这里默认补全为 PKCS#8 格式 (BEGIN PRIVATE KEY)
        # 如果是 PKCS#1 格式可能需要改为 BEGIN RSA PRIVATE KEY
        if not pk_str.startswith("-----BEGIN"):
            # 简单的格式化，每64字符换行是PEM的标准，但在Python加载时通常不需要强制换行，
            # 只要头尾正确即可。
            pk_str = f"-----BEGIN PRIVATE KEY-----\n{pk_str}\n-----END PRIVATE KEY-----"

        try:
            # 使用cryptography库加载PEM格式的私钥
            # encode('utf-8') 将字符串转换为字节串
            # password=None 表示私钥未加密（不需要密码）
            return cryptography.hazmat.primitives.serialization.load_pem_private_key(
                pk_str.encode('utf-8'),
                password=None
            )
        except Exception as e:
            # 加载失败时抛出ValueError异常，包含详细的错误信息
            raise ValueError(f"私钥格式错误或加载失败: {str(e)}")

    def _load_public_key(self, pub_key_str: str):
        """
        内部函数：处理公钥格式并加载

        功能说明:
            将公钥字符串转换为cryptography库可用的公钥对象
            支持两种输入格式：
            1. 完整的PEM格式（包含 -----BEGIN PUBLIC KEY----- 头尾）
            2. 纯Base64编码的密钥内容（自动补全头尾）

        参数:
            pub_key_str (str): 公钥字符串

        返回:
            公钥对象（cryptography.hazmat.primitives.asymmetric.rsa.RSAPublicKey）

        异常:
            ValueError: 当公钥格式错误或加载失败时抛出
        """
        # 去除首尾空白字符（空格、换行、制表符等）
        pub_key_str = pub_key_str.strip()

        # 检查是否包含PEM格式的头部标识
        # 如果没有头部，说明是纯Base64字符串，需要补全标准的PEM格式头尾
        if not pub_key_str.startswith("-----BEGIN"):
            # 补全PEM格式的头尾
            # 标准格式：-----BEGIN PUBLIC KEY-----\n{base64内容}\n-----END PUBLIC KEY-----
            pub_key_str = f"-----BEGIN PUBLIC KEY-----\n{pub_key_str}\n-----END PUBLIC KEY-----"

        try:
            # 使用cryptography库加载PEM格式的公钥
            # encode('utf-8') 将字符串转换为字节串
            return cryptography.hazmat.primitives.serialization.load_pem_public_key(
                pub_key_str.encode('utf-8')
            )
        except Exception as e:
            # 加载失败时抛出ValueError异常，包含详细的错误信息
            raise ValueError(f"公钥格式错误或加载失败: {str(e)}")

    def generate_sign_string(self, params: dict) -> str:
        """
        排序、拼接、签名并返回JSON
        """
        # 1. & 2. 获取非空参数，剔除特定字段，排序并拼接
        string_to_sign = self._build_string_to_sign(params)

        # 3. 计算 RSA 签名 (SHA256WithRSA)
        # 使用 PKCS1v15 填充，这是大多数支付接口（如支付宝）的标准
        signature = self.private_key.sign(
            string_to_sign.encode('utf-8'),
            cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15(),
            cryptography.hazmat.primitives.hashes.SHA256()
        )

        # 转为 Base64 字符串
        sign_b64 = base64.b64encode(signature).decode('utf-8')

        return sign_b64

    def verify_sign(self, params: dict, signature: str, hash_algo: str = 'SHA256') -> bool:
        """
        验证RSA签名是否有效

        功能说明:
            使用公钥验证签名字符串的有效性
            这是支付回调通知中的核心安全机制，确保通知来自真实的支付平台

        参数:
            params (dict): 需要验证的参数字典（包含所有参数，但不包含sign）
            signature (str): Base64编码的签名字符串（从支付平台返回的sign参数）
            hash_algo (str): 哈希算法，默认为'SHA256'，也支持'SHA1'

        返回:
            bool: 验证成功返回True，验证失败返回False

        验证流程:
            1. 使用 _build_string_to_sign() 构建待签名字符串（参数排序、拼接）
            2. 使用公钥对签名进行解密
            3. 比对解密后的哈希值与重新计算的哈希值是否一致
        """
        try:
            # 第1步：构建待签名字符串
            # 按照同样的规则（过滤、排序、拼接）生成原文
            # 这个原文必须与签名时使用的原文完全一致
            content = self._build_string_to_sign(params)

            # 原文可能包含订单、回调地址或其他敏感参数，只记录长度用于排障。
            logging.info(f"[RSA验签] 待验证原文长度: {len(content)}")

            # 第2步：检查公钥是否已加载
            # 如果初始化时没有提供公钥，则无法进行验签
            if not self.public_key:
                logging.error("[RSA验签] 错误：未加载公钥，无法验证签名")
                return False

            # 第3步：处理签名字符串中的空格问题
            # 问题场景：URL传输时，Base64中的"+"号可能被解码为空格
            # 解决方案：检测到空格时，尝试替换回"+"号
            if " " in signature:
                logging.warning("[RSA验签] 检测到签名中包含空格，尝试替换为'+'（可能是URL解码导致）")
                signature = signature.replace(" ", "+")

            # 第4步：Base64解码签名字符串
            # 将Base64编码的签名字符串解码为原始字节串
            try:
                signature_bytes = base64.b64decode(signature)
            except Exception as e:
                # Base64解码失败，说明签名字符串格式不正确
                logging.error(f"[RSA验签] Base64解码失败: {str(e)}")
                return False

            # 第5步：选择哈希算法
            # 根据参数选择SHA256或SHA1哈希算法
            # 默认使用SHA256（更安全），部分旧系统可能使用SHA1
            if hash_algo.upper() == 'SHA1':
                chosen_hash = cryptography.hazmat.primitives.hashes.SHA1()
            else:
                chosen_hash = cryptography.hazmat.primitives.hashes.SHA256()

            # 第6步：执行RSA签名验证
            # 使用公钥验证签名是否有效
            # 验证过程：
            #   1. 使用公钥解密签名（得到哈希值A）
            #   2. 对原文进行哈希计算（得到哈希值B）
            #   3. 比较A和B是否相同
            # 如果验证成功，函数正常返回；如果失败，抛出InvalidSignature异常
            self.public_key.verify(
                signature_bytes,                                    # 签名字节串
                content.encode('utf-8'),                            # 原文字节串
                cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15(),  # 填充方式
                chosen_hash                                         # 哈希算法
            )

            # 验证成功，记录日志并返回True
            logging.info("[RSA验签] ✅ 验签通过！签名有效")
            return True

        except cryptography.exceptions.InvalidSignature:
            # 签名无效异常
            # 原因可能是：
            #   1. 签名被篡改
            #   2. 原文被篡改
            #   3. 使用了错误的公钥
            #   4. 签名算法不匹配
            logging.error("[RSA验签] ❌ 验签失败！签名无效")
            return False

        except Exception as e:
            # 其他未预期的异常
            # 例如：公钥格式错误、加密库内部错误等
            logging.error(f"[RSA验签] ⚠️ 验签过程发生错误: {str(e)}")
            logging.error(traceback.format_exc())
            return False

    def generate_sign(self, params: dict) -> str:
        """
        排序、拼接、签名并返回JSON
        """
        # 1. & 2. 获取非空参数，剔除特定字段，排序并拼接
        string_to_sign = self._build_string_to_sign(params)

        # 3. 计算 RSA 签名 (SHA256WithRSA)
        # 使用 PKCS1v15 填充，这是大多数支付接口（如支付宝）的标准
        signature = self.private_key.sign(
            string_to_sign.encode('utf-8'),
            cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15(),
            cryptography.hazmat.primitives.hashes.SHA256()
        )

        # 转为 Base64 字符串
        sign_b64 = base64.b64encode(signature).decode('utf-8')

        # 复制一份原参数，避免直接修改传入的 params 字典对外部造成影响
        response_data = params.copy()

        # 将签名和签名类型加入到字典中
        response_data["sign"] = sign_b64
        response_data["sign_type"] = "RSA"

        return response_data

    def _build_string_to_sign(self, params: dict) -> str:
        """
        参数过滤、排序和拼接
        """
        filtered_params = {}

        for key, value in params.items():
            # 剔除 sign 和 sign_type
            if key in ['sign', 'sign_type']:
                continue

            # 剔除空值 (None 或 空字符串)
            # 注意：数字 0 通常被视为有效值，所以不能简单用 if not value
            if value is None or value == "":
                continue

            # 剔除数组、字节类型 (list, tuple, bytes)
            if isinstance(value, (list, tuple, bytes)):
                continue

            # 确保值为字符串格式
            filtered_params[key] = str(value)

        # 按照键名 ASCII 码升序排序
        sorted_keys = sorted(filtered_params.keys())

        # 组合成 "参数=参数值" 并用 "&" 连接
        kv_pairs = [f"{key}={filtered_params[key]}" for key in sorted_keys]

        # 修复：返回拼接后的字符串
        return "&".join(kv_pairs)
