from __future__ import annotations

import json
import logging
import re
import secrets


def _main():
    import main
    return main


def _get_crypto_primitives():
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import serialization, hashes

    return rsa, padding, serialization, hashes


def _obfuscate_runtime_javascript(source):
    import base64 as _base64

    source = re.sub(r"/\*[\s\S]*?\*/", "", str(source or ""))
    compact_lines = []
    for line in source.splitlines():
        line = re.sub(r"^\s*//.*$", "", line)
        line = line.strip()
        if not line:
            continue
        compact_lines.append(line)
    compact_source = "".join(compact_lines)
    source_bytes = compact_source.encode("utf-8")
    mask = secrets.token_bytes(16)
    encoded_bytes = bytes(
        byte ^ mask[index % len(mask)]
        for index, byte in enumerate(source_bytes)
    )
    payload = _base64.b64encode(encoded_bytes).decode("ascii")
    mask_payload = _base64.b64encode(mask).decode("ascii")
    payload_name = f"_{secrets.token_hex(6)}"
    mask_name = f"_{secrets.token_hex(6)}"
    decode_name = f"_{secrets.token_hex(6)}"
    return (
        f"(function(){{'use strict';"
        f"const {payload_name}='{payload}',{mask_name}='{mask_payload}';"
        f"function {decode_name}(v){{"
        f"const b=atob(v),a=new Uint8Array(b.length);"
        f"for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);"
        f"return a}}"
        f"const d={decode_name}({payload_name}),m={decode_name}({mask_name}),"
        f"o=new Uint8Array(d.length);"
        f"for(let i=0;i<d.length;i++)o[i]=d[i]^m[i%m.length];"
        f"(0,Function)(new TextDecoder().decode(o))();"
        f"}})();"
    )


def _build_obfuscated_map_key_runtime_script(runtime_version):
    runtime_template = _main()._load_map_key_runtime_template()
    rendered = (
        runtime_template
        .replace("__MAP_KEY_RUNTIME_NAMESPACE__", _main().MAP_KEY_RUNTIME_NAMESPACE)
        .replace("__MAP_KEY_RUNTIME_VERSION__", json.dumps(str(runtime_version or "")))
    )
    return _main()._obfuscate_runtime_javascript(rendered)


def _generate_map_key_runtime_context():
    rsa, _, _, _ = _main()._get_crypto_primitives()
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    runtime_version = secrets.token_hex(8)
    return {
        "private_key": private_key,
        "public_key": private_key.public_key(),
        "runtime_version": runtime_version,
        "runtime_script": _main()._build_obfuscated_map_key_runtime_script(
            runtime_version=runtime_version,
        ),
    }


def _get_map_key_runtime_user_key(username):
    normalized = str(username or "").strip()
    if not normalized or normalized.lower() == "guest":
        return ""
    return normalized.casefold()


def _get_map_key_runtime_session_identity(session_id):
    """验证会话是否仍存在，并返回会话绑定的认证用户。"""
    normalized_session_id = _main().normalize_session_uuid(session_id)
    if not normalized_session_id:
        return "", None, False
    main_module = _main()
    if not hasattr(main_module, "web_sessions_lock") or not hasattr(
        main_module,
        "web_sessions",
    ):
        return normalized_session_id, None, False
    with main_module.web_sessions_lock:
        api_instance = main_module.web_sessions.get(normalized_session_id)
        if api_instance is None:
            return normalized_session_id, None, False
        if getattr(api_instance, "is_guest", True):
            return normalized_session_id, None, True
        return (
            normalized_session_id,
            getattr(api_instance, "auth_username", None),
            True,
        )


def _register_map_key_runtime_context(context):
    if not isinstance(context, dict):
        return
    runtime_version = str(context.get("runtime_version") or "").strip()
    if runtime_version:
        _main().map_key_runtime_contexts_by_version[runtime_version] = context


def _unregister_map_key_runtime_context_if_unused(context):
    if not isinstance(context, dict):
        return
    main_module = _main()
    if any(item is context for item in main_module.map_key_runtime_session_contexts.values()):
        return
    if any(item is context for item in main_module.map_key_runtime_user_contexts.values()):
        return
    runtime_version = str(context.get("runtime_version") or "").strip()
    if runtime_version:
        registered = main_module.map_key_runtime_contexts_by_version.get(runtime_version)
        if registered is context:
            main_module.map_key_runtime_contexts_by_version.pop(runtime_version, None)


def _get_map_key_runtime_context_for_session(
    session_id=None,
    username=None,
    create=True,
):
    """获取会话使用的运行时上下文，并按用户复用仍存活的密钥对。"""
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        # 没有真实会话时只使用启动级兜底上下文，避免为匿名探测请求不断生成孤立密钥对。
        return _main()._ensure_map_key_runtime_cache() if create else None
    main_module = _main()
    user_key = main_module._get_map_key_runtime_user_key(username)
    with main_module._get_map_key_runtime_lock():
        context = (
            main_module.map_key_runtime_session_contexts.get(normalized_session_id)
            if normalized_session_id
            else None
        )
        previous_context = context
        previous_user_key = (
            main_module.map_key_runtime_session_users.get(normalized_session_id)
            if normalized_session_id
            else ""
        )

        if user_key:
            context = main_module.map_key_runtime_user_contexts.get(user_key)
            if context is None and create:
                context = main_module._generate_map_key_runtime_context()
            if context is not None:
                main_module.map_key_runtime_user_contexts[user_key] = context
        elif context is None and create:
            context = main_module._generate_map_key_runtime_context()

        if not context:
            return None

        main_module._register_map_key_runtime_context(context)
        if normalized_session_id:
            main_module.map_key_runtime_session_contexts[normalized_session_id] = context
            main_module.map_key_runtime_session_users[normalized_session_id] = user_key

        if previous_user_key != user_key and previous_user_key:
            old_context = main_module.map_key_runtime_user_contexts.get(previous_user_key)
            has_remaining_sessions = any(
                linked_user == previous_user_key
                for linked_session_id, linked_user in main_module.map_key_runtime_session_users.items()
                if linked_session_id != normalized_session_id
            )
            if old_context is previous_context and not has_remaining_sessions:
                main_module.map_key_runtime_user_contexts.pop(previous_user_key, None)
                main_module._unregister_map_key_runtime_context_if_unused(old_context)

        if previous_context is not None and previous_context is not context:
            main_module._unregister_map_key_runtime_context_if_unused(previous_context)
        return context


def _get_map_key_runtime_context_by_version(runtime_version):
    normalized_version = str(runtime_version or "").strip()
    if not normalized_version:
        return None
    main_module = _main()
    with main_module._get_map_key_runtime_lock():
        return main_module.map_key_runtime_contexts_by_version.get(normalized_version)


def _release_map_key_runtime_session(session_id, username=None):
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return
    main_module = _main()
    with main_module._get_map_key_runtime_lock():
        context = main_module.map_key_runtime_session_contexts.pop(
            normalized_session_id,
            None,
        )
        user_key = main_module.map_key_runtime_session_users.pop(
            normalized_session_id,
            None,
        )
        user_key = user_key or main_module._get_map_key_runtime_user_key(username)
        if user_key:
            user_context = main_module.map_key_runtime_user_contexts.get(user_key)
            has_remaining_sessions = any(
                linked_user == user_key
                for linked_user in main_module.map_key_runtime_session_users.values()
            )
            if not has_remaining_sessions:
                main_module.map_key_runtime_user_contexts.pop(user_key, None)
                main_module._unregister_map_key_runtime_context_if_unused(
                    user_context or context
                )
        main_module._unregister_map_key_runtime_context_if_unused(context)


def _get_map_key_runtime_context_for_request(require_session_header=False):
    main_module = _main()
    session_id = main_module.normalize_session_uuid(
        main_module.request.headers.get("X-Session-ID", "")
    )
    if require_session_header and not session_id:
        return None
    if not session_id:
        session_id = main_module.normalize_session_uuid(
            main_module.request.args.get("session_id", "")
        )
    if not session_id and main_module.request.referrer:
        uuid_match = re.search(
            r"/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})",
            main_module.request.referrer,
            re.IGNORECASE,
        )
        if uuid_match:
            session_id = uuid_match.group(1)

    session_id, username, session_exists = (
        main_module._get_map_key_runtime_session_identity(session_id)
    )
    if not session_exists:
        return None

    session_context = main_module._get_map_key_runtime_context_for_session(
        session_id,
        username,
    )
    if session_context is None:
        return None

    runtime_version = main_module.request.args.get("v", "")
    if not str(runtime_version or "").strip():
        return session_context
    version_context = main_module._get_map_key_runtime_context_by_version(
        runtime_version
    )
    if version_context is not session_context:
        return None
    return session_context


def _initialize_map_key_runtime():
    """为一次 Web 服务启动创建全新的非对称密钥对和运行时脚本。"""
    main_module = _main()
    with main_module._get_map_key_runtime_lock():
        main_module.map_key_runtime_cache.clear()
        main_module.map_key_runtime_session_contexts.clear()
        main_module.map_key_runtime_session_users.clear()
        main_module.map_key_runtime_user_contexts.clear()
        main_module.map_key_runtime_contexts_by_version.clear()
        context = main_module._generate_map_key_runtime_context()
        main_module.map_key_runtime_cache.update(context)
        main_module._register_map_key_runtime_context(
            main_module.map_key_runtime_cache
        )
        return main_module.map_key_runtime_cache


def _ensure_map_key_runtime_cache():
    main_module = _main()
    with main_module._get_map_key_runtime_lock():
        if not main_module.map_key_runtime_cache:
            main_module.map_key_runtime_cache.update(
                main_module._generate_map_key_runtime_context()
            )
            main_module._register_map_key_runtime_context(
                main_module.map_key_runtime_cache
            )
        return main_module.map_key_runtime_cache


def _get_map_key_runtime_script_url(runtime_version):
    version = str(runtime_version or "").strip()
    if not version:
        return f"/api/{_main().MAP_KEY_RUNTIME_SCRIPT_NAME}"
    return f"/api/{_main().MAP_KEY_RUNTIME_SCRIPT_NAME}?v={version}"


def _encrypt_map_provider_secret(secret_value, runtime_context=None):
    raw_value = str(secret_value or "").strip()
    if not raw_value:
        return ""
    main_module = _main()
    _, padding, _, hashes = main_module._get_crypto_primitives()
    runtime_context = runtime_context or main_module._ensure_map_key_runtime_cache()
    ciphertext = runtime_context["public_key"].encrypt(
        raw_value.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(
                algorithm=hashes.SHA256()
            ),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    import base64 as _base64

    return _base64.b64encode(ciphertext).decode("utf-8")


def _load_client_public_key(client_public_key):
    if not isinstance(client_public_key, dict):
        return None
    try:
        import base64 as _base64
        rsa, _, _, _ = _main()._get_crypto_primitives()

        jwk = dict(client_public_key)
        if jwk.get("kty") != "RSA":
            return None
        n_value = str(jwk.get("n") or "")
        e_value = str(jwk.get("e") or "")
        if not n_value or not e_value:
            return None

        def _decode_base64_urlsafe(value):
            padding_size = (-len(value)) % 4
            value = value + ("=" * padding_size)
            return _base64.urlsafe_b64decode(value.encode("ascii"))

        n_int = int.from_bytes(_decode_base64_urlsafe(n_value), "big")
        e_int = int.from_bytes(_decode_base64_urlsafe(e_value), "big")
        public_numbers = rsa.RSAPublicNumbers(e_int, n_int)
        return public_numbers.public_key()
    except Exception as exc:
        logging.warning(
            "[MapKeyRuntime] 客户端公钥解析失败: %s",
            type(exc).__name__,
        )
        return None


def _encrypt_map_provider_payload_for_client(
    payload_text,
    client_public_key,
):
    raw_value = str(payload_text or "").strip()
    if not raw_value or client_public_key is None:
        return {}
    _, padding, _, hashes = _main()._get_crypto_primitives()
    import base64 as _base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        aes_key = secrets.token_bytes(32)
        iv = secrets.token_bytes(12)
        ciphertext = AESGCM(aes_key).encrypt(
            iv,
            raw_value.encode("utf-8"),
            None,
        )
        encrypted_key = client_public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception as exc:
        logging.warning(
            "[MapKeyRuntime] 客户端负载加密失败: %s",
            type(exc).__name__,
        )
        return {}

    return {
        "encrypted_key": _base64.b64encode(encrypted_key).decode("utf-8"),
        "iv": _base64.b64encode(iv).decode("utf-8"),
        "ciphertext": _base64.b64encode(ciphertext).decode("utf-8"),
    }


def _decrypt_map_provider_key_bundle(key_bundle, runtime_context):
    if not isinstance(key_bundle, dict) or not isinstance(runtime_context, dict):
        return {}
    private_key = runtime_context.get("private_key")
    if private_key is None:
        return {}
    providers_payload = key_bundle.get("providers")
    if not isinstance(providers_payload, dict):
        return {}
    main_module = _main()
    requested_provider = str(key_bundle.get("provider") or "").strip().lower()
    if requested_provider not in main_module.MAP_PROVIDER_KEY_FIELDS:
        if len(providers_payload) != 1:
            return {}
        requested_provider = str(next(iter(providers_payload)) or "").strip().lower()
    provider = main_module._normalize_map_provider(requested_provider)
    if provider != requested_provider:
        return {}
    secret_info = providers_payload.get(provider)
    if not isinstance(secret_info, dict):
        return {}
    field_name = str(secret_info.get("field") or "").strip()
    if field_name != main_module.MAP_PROVIDER_KEY_FIELDS.get(provider):
        return {}
    ciphertext = str(secret_info.get("ciphertext") or "").strip()
    if not ciphertext:
        return {}

    import base64 as _base64

    _, padding, _, hashes = main_module._get_crypto_primitives()
    try:
        plain_text = private_key.decrypt(
            _base64.b64decode(ciphertext),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        ).decode("utf-8")
    except Exception as exc:
        logging.warning(
            "[MapKeyRuntime] 地图密钥密文解密失败: provider=%s, error=%s",
            provider,
            type(exc).__name__,
        )
        return {}
    return {provider: {field_name: plain_text}}
