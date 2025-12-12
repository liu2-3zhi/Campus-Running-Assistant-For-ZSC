import base64
import json
import urllib.parse
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

def format_public_key(pub_key_str):
    """
    格式化公钥，如果缺失头尾则补全
    """
    # 去除可能存在的空格、换行符
    key_pure = pub_key_str.replace("-----BEGIN PUBLIC KEY-----", "") \
                          .replace("-----END PUBLIC KEY-----", "") \
                          .replace("\n", "").replace("\r", "").strip()
    
    # 按照每64个字符换行
    formatted_key = "-----BEGIN PUBLIC KEY-----\n"
    for i in range(0, len(key_pure), 64):
        formatted_key += key_pure[i:i+64] + "\n"
    formatted_key += "-----END PUBLIC KEY-----"
    return formatted_key

def build_sign_string(params):
    """
    按照规则构建待签名字符串
    """
    if not isinstance(params, dict):
        return str(params)

    sorted_keys = sorted(params.keys())
    kv_list = []

    for key in sorted_keys:
        val = params[key]

        # 1. 剔除 sign 和 sign_type
        if key in ["sign", "sign_type"]:
            continue
        
        # 2. 剔除空值 (None 或 空字符串)
        if val is None or val == "":
            continue

        # 3. 剔除数组、字节类型
        if isinstance(val, (list, tuple, dict, bytes, bytearray)):
            continue

        # 组合 k=v
        kv_list.append(f"{key}={str(val)}")

    # 4. & 符号连接
    sign_str = "&".join(kv_list)
    return sign_str

def verify_signature(params, signature, public_key_str, hash_algo='SHA256'):
    """
    验证签名
    """
    try:
        # 1. 构建待签名字符串 (原文)
        content = build_sign_string(params)
        print(f"\n[INFO] 自动生成的待签名原文(Pre-sign string):\n{content}")

        # 2. 处理公钥格式
        formatted_pub_key = format_public_key(public_key_str)
        
        # 加载公钥
        public_key = serialization.load_pem_public_key(
            formatted_pub_key.encode('utf-8')
        )

        # 3. 解码签名 (Base64 -> Bytes)
        # 注意：如果签名中包含空格（被URL解码后的+号），尝试替换回+号
        if " " in signature:
            print("[WARN] 签名中检测到空格，尝试替换为 '+' (常见于URL解码错误)")
            signature = signature.replace(" ", "+")
            
        try:
            signature_bytes = base64.b64decode(signature)
        except Exception as e:
            print(f"[ERROR] Base64解码失败，请检查sign字符串是否完整: {e}")
            return False

        # 4. 选择哈希算法
        if hash_algo.upper() == 'SHA1':
            chosen_hash = hashes.SHA1()
        else:
            chosen_hash = hashes.SHA256()

        # 5. 执行验证
        public_key.verify(
            signature_bytes,
            content.encode('utf-8'),
            padding.PKCS1v15(),
            chosen_hash
        )
        print("\n[SUCCESS] ✅ 验签通过！签名有效。")
        return True

    except InvalidSignature:
        print("\n[FAILED] ❌ 验签失败！签名无效。")
        return False
    except Exception as e:
        print(f"\n[ERROR] ⚠️ 发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    # ================= 配置区域 =================
    
    # 1. 请在这里粘贴完整的请求字符串（格式如：pid=123&sign=XXX&name=test）
    # 程序会自动解析并提取 sign
    raw_input_string = """
    pid=1408&trade_no=2025121221232074298&out_trade_no=ORDER20251212212320788420&type=wxpay&name=product&money=0.5&trade_status=TRADE_SUCCESS&api_trade_no=4200002911202512129872346578&buyer=ooIeqs1etKekdatliYbfcvbohV8g&timestamp=1765545839&sign_type=RSA&sign=k7AwlSdM4wm6GVyAwJPV%2BgtNI7D1AD8y0zPvk5I9zCPl%2Fkvr0ZA13KfFWk7GwR%2BTQMfDPW72oIfWodLZj8OyHRFNdIQHQENPyTBA%2BmcK0tvDgaAKLRuKjwLWB35993BuG%2BzP7bgT3xlIfje9rRGRWAiJjs4hwlm2STeqHXJ0H1bw138pFAvdd2fHx6lLq%2FzfHyVgc3h6VHjAK2zJcjDBVmINk1RCKvX8uaDfSfT19qVLuHMV12vSCKFBwyfa9%2Fra166nzwCadQkkG%2BiMSdJEDPcGqIw6QKzlMPUY2720MKJeUawwcg3DgEVaPtvkUYfTU1LMSY8ndqObxRQ57SYH%2BQ%3D%3D
    """

    # 2. 这里填入公钥 (无需头尾)
    pub_key = """
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApHOAw8DMPO4V3yVJcEcSBXafA1yZKk5BjOHEyzZUjpeIosb1jb5NOVnissJzA3MsJbbYyqQv+aHw7kCb3izPcMkeuQUVltsHTrhOh/Y/NGza1Twuk8YhKD6t/4G80mFcHL+VdUinA1rxeVvwybK1N1s0e5VWvuoPlArjLHNySEC+8kA8K+wpDgNcOe5PclZwrltoBoEWEs7mtOXp+qzX0zEI3sqOg52ID2buReUHL6Z/hTNP4Fz7xu78IYvVkAkKQb/W/NQIMFC7YVYSpVsM8/qAaAE+KHS7PUpzVORDmall4L8iwIbbLiT3Sfj2+XMAi2OQYuZSDwucYWVyOQYQzwIDAQAB
    """

    # ================= 自动处理逻辑 =================
    
    print("--- 开始处理 ---")
    
    # 清理输入字符串的多余换行
    clean_input = raw_input_string.strip().replace('\n', '').replace('\r', '')
    
    # 解析 URL 字符串为字典
    # parse_qsl 会处理 URL 编码 (如 %20 -> 空格, %2B -> +)
    try:
        parsed_params = dict(urllib.parse.parse_qsl(clean_input, keep_blank_values=True))
    except Exception as e:
        print(f"[CRITICAL] 无法解析输入字符串: {e}")
        exit()
        
    if not parsed_params:
        print("[CRITICAL] 解析结果为空，请检查 raw_input_string 是否正确填写")
        exit()

    # 提取 sign
    target_sign = parsed_params.pop('sign', None)

    if not target_sign:
        print("[CRITICAL] 输入字符串中未找到 'sign' 参数！请确保字符串包含 &sign=...")
    else:
        print(f"[INFO] 已提取参数个数: {len(parsed_params)}")
        print(f"[INFO] 已提取签名(前20位): {target_sign[:20]}...")
        
        # 开始验证 (默认 SHA256，如需 SHA1 请修改参数)
        verify_signature(parsed_params, target_sign, pub_key, hash_algo='SHA256')