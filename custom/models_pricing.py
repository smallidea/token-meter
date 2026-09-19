# -*- coding: utf-8 -*-
"""新增模型的定价配置 (每百万 Token 美元价格)"""

CUSTOM_PRICES = {
    # Google Gemini 系列
    "gemini-3.8-flash": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
    "gemini-3.8-flash-medium": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
    "gemini-3.6-flash": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
    "gemini-3.6-flash-medium": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
    "gemini-3.5-flash-medium": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
    "gemini-3.1-pro-high": {"input": 1.25, "output": 5.00, "cache_read": 0.31, "cache_write": 1.25},
    "gemini-3.1-pro-low": {"input": 1.25, "output": 5.00, "cache_read": 0.31, "cache_write": 1.25},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00, "cache_read": 0.31, "cache_write": 1.25},
    "gemini-3-flash-preview": {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30, "cache_read": 0.01875, "cache_write": 0.075},
    "gemini-2.5-flash-lite": {"input": 0.0375, "output": 0.15, "cache_read": 0.01, "cache_write": 0.0375},
    # 字节豆包 / Trae 系列
    "doubao-seed-code": {"input": 0.12, "output": 0.30, "cache_read": 0.03, "cache_write": 0.12},
    "doubao-seed-evolving": {"input": 0.20, "output": 0.60, "cache_read": 0.05, "cache_write": 0.20},
    "doubao_1_6": {"input": 0.12, "output": 0.30, "cache_read": 0.03, "cache_write": 0.12},
    # 智谱 GLM 系列
    "glm-5.3-flash": {"input": 0.07, "output": 0.14, "cache_read": 0.01, "cache_write": 0.07},
    "glm-4": {"input": 1.40, "output": 1.40, "cache_read": 0.35, "cache_write": 1.40},
    # 腾讯混元 / WorkBuddy 系列
    "hy4-preview": {"input": 0.50, "output": 1.50, "cache_read": 0.10, "cache_write": 0.50},
    "hunyuan": {"input": 0.50, "output": 1.50, "cache_read": 0.10, "cache_write": 0.50},
}


def get_price(model_name):
    if not model_name:
        return {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10}
    clean = model_name.lower().replace("_", "-")
    for k, v in CUSTOM_PRICES.items():
        if k in clean:
            return v
    return {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10}


def calculate_cost(input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0, model_name=None):
    price = get_price(model_name)
    cost = (
        (input_tokens / 1_000_000.0) * price["input"] +
        (output_tokens / 1_000_000.0) * price["output"] +
        (cache_read_tokens / 1_000_000.0) * price["cache_read"] +
        (cache_write_tokens / 1_000_000.0) * price["cache_write"]
    )
    return round(cost, 6)
