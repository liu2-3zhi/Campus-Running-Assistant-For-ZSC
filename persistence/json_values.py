"""Readable SQL JSON values with exact exceptional numeric representations.

Normal objects, arrays, strings, booleans, nulls and safe integers stay native
JSON. IEEE floats and integers outside the cross-engine safe range use one
reserved marker. Objects containing that marker are escaped as key/value pairs,
so provider data can never accidentally become storage metadata on round trip.
"""
from __future__ import annotations

import math


MARKER = '$storage'
MAX_SAFE_INTEGER = 2**53 - 1


def encode_native_json(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER else {MARKER: ['int', str(value)]}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Native JSON requires finite numbers')
        return {MARKER: ['float', value.hex()]}
    if isinstance(value, list):
        return [encode_native_json(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError('Native JSON object keys must be strings')
        if MARKER in value:
            return {MARKER: ['object', [[key, encode_native_json(item)] for key, item in value.items()]]}
        return {key: encode_native_json(item) for key, item in value.items()}
    raise ValueError('Unsupported native JSON value type')


def decode_native_json(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        # A deliberate SQL edit can introduce an ordinary JSON number. Treat
        # the value actually returned by the driver as the new authority.
        if not math.isfinite(value):
            raise ValueError('Native JSON requires finite numbers')
        return value
    if isinstance(value, list):
        return [decode_native_json(item) for item in value]
    if not isinstance(value, dict):
        raise ValueError('Unsupported stored native JSON value type')
    if MARKER not in value:
        return {key: decode_native_json(item) for key, item in value.items()}
    marker = value[MARKER]
    if len(value) != 1 or not isinstance(marker, list) or len(marker) != 2:
        raise ValueError('Invalid native JSON storage marker')
    kind, payload = marker
    if kind == 'float' and isinstance(payload, str):
        number = float.fromhex(payload)
        if not math.isfinite(number):
            raise ValueError('Native JSON requires finite numbers')
        return number
    if kind == 'int' and isinstance(payload, str):
        number = int(payload)
        if str(number) != payload:
            raise ValueError('Invalid native JSON integer representation')
        return number
    if kind == 'object' and isinstance(payload, list):
        result = {}
        for pair in payload:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str) or pair[0] in result:
                raise ValueError('Invalid escaped native JSON object')
            result[pair[0]] = decode_native_json(pair[1])
        return result
    raise ValueError('Invalid native JSON storage marker')
