# -*- coding: utf-8 -*-
"""
多行业商品名生成器模块

默认保留现卤现捞商品名生成能力，并支持通过顶部模式常量切换到其他行业。
生成的商品名称采用纯中文数字格式，符合支付接口对商品名的字节长度限制（最大127字节）。

使用示例：
    from product_name_generator import LoMeiGenerator

    generator = LoMeiGenerator()
    product_name = generator.generate(5)
    print(product_name)
"""

import random  # nosec B311 - 仅用于生成展示型商品名的随机文案，不用于安全场景

# ==============================
# 商品名生成器行业模式开关
# - 这是全局行业模式配置，请勿随意切换。
# - 修改前请先确认当前站点业务场景，避免因为误切换导致支付商品名风格突变。
# - 只能填写 PRODUCT_NAME_GENERATOR_MODE_CONFIGS 中已注册的模式值。
# - 若要新增行业，请先补充模式配置，再修改本常量。
# ==============================
PRODUCT_NAME_GENERATOR_MODE = "lomei"

PRODUCT_NAME_GENERATOR_MODE_CONFIGS = {
    "lomei": {
        "display_name": "现卤现捞",
        "fallback_template": "{count}份现捞小吃",
        "foods": [
            "鸭脖", "鸭翅", "鸭掌", "鸭舌", "鸭头", "锁骨",
            "鱼豆腐", "豆皮", "海带结", "藕片", "烤肠", "波波肠",
            "鸡尖", "鹌鹑蛋", "腐竹", "魔芋爽", "大鸡腿", "兰花干",
        ],
        "quantifiers": ["根", "串", "块", "份", "个", "只", "大把", "口"],
        "adj_flavor": [
            "秘制", "麻辣", "五香", "甜辣", "变态辣", "爆辣",
            "酱香", "卤味", "满口香", "红油", "脆皮", "多汁",
            "Q弹", "入味", "鲜嫩", "吮指", "藤椒",
        ],
        "adj_emotion": [
            "寂寞的", "快乐的", "治愈的", "灵魂", "让室友流泪的",
            "高贵的", "卑微的", "暴躁的", "佛系养生的", "充满希望的",
            "绝望的", "初恋般的", "热血的", "深夜的", "独自享用的",
            "令人发指的", "不仅防饿还能防脱发的", "吃完就通过考试的",
            "甚至想再来一份的", "老板含泪推荐的", "也就是个", "减肥路上的绊脚石",
        ],
        "connectors": ["搭配", "配上", "以及", "还有", "加上", "和"],
    },
    "travel_service": {
        "display_name": "旅游服务",
        "fallback_template": "{count}项旅游服务费",
        "items": [
            {"name": "资料打印费", "quantifier": "份"},
            {"name": "短信费", "quantifier": "次"},
        ],
    },
}


def get_supported_product_name_generator_modes():
    """返回当前已注册的商品名生成器模式列表。"""
    return tuple(PRODUCT_NAME_GENERATOR_MODE_CONFIGS.keys())



def validate_product_name_generator_mode(mode=None):
    """校验商品名生成器模式配置是否合法。"""
    selected_mode = str(mode if mode is not None else PRODUCT_NAME_GENERATOR_MODE).strip()
    if selected_mode not in PRODUCT_NAME_GENERATOR_MODE_CONFIGS:
        supported = ", ".join(get_supported_product_name_generator_modes())
        raise ValueError(
            f"PRODUCT_NAME_GENERATOR_MODE 配置无效: {selected_mode!r}。"
            f" 允许值: {supported}。"
            " 如需新增行业模式，请先在 PRODUCT_NAME_GENERATOR_MODE_CONFIGS 中注册。"
        )
    return selected_mode


class LoMeiGenerator:
    """兼容现有调用方式的多行业商品名生成器。"""

    def __init__(self):
        self.mode = validate_product_name_generator_mode()
        self.mode_config = PRODUCT_NAME_GENERATOR_MODE_CONFIGS[self.mode]

        self.foods = self.mode_config.get("foods", [])
        self.quantifiers = self.mode_config.get("quantifiers", [])
        self.adj_flavor = self.mode_config.get("adj_flavor", [])
        self.adj_emotion = self.mode_config.get("adj_emotion", [])
        self.connectors = self.mode_config.get("connectors", [])
        self.travel_service_items = self.mode_config.get("items", [])
        self.fallback_template = self.mode_config["fallback_template"]

        self.zh_nums = list("零一二三四五六七八九")
        self.zh_units = ["", "十", "百", "千", "万"]

    def _int_to_chinese(self, n: int) -> str:
        """
        将整数转换为中文数字字符串。
        例如: 1 -> 一, 12 -> 十二, 20 -> 二十, 105 -> 一百零五
        """
        if n == 0:
            return "零"

        s = str(n)
        length = len(s)
        result = []

        for i, digit in enumerate(s):
            d = int(digit)
            unit = self.zh_units[length - i - 1]

            if d != 0:
                result.append(self.zh_nums[d] + unit)
            else:
                if result and result[-1][-1] != "零":
                    result.append("零")

        final_str = "".join(result)

        if final_str.endswith("零"):
            final_str = final_str[:-1]

        if 10 <= n < 20 and final_str.startswith("一十"):
            final_str = final_str[1:]

        return final_str

    def _get_byte_len(self, s: str) -> int:
        """计算字符串的 UTF-8 字节长度。"""
        if s is None:
            return 0
        return len(s.encode("utf-8"))

    def _partition_integer(self, n, parts):
        """整数分拆：将 n 随机拆分为 parts 个正整数之和。"""
        if parts == 1 or n == 1:
            return [n]
        if n < parts:
            return [1] * n

        cut_points = sorted(random.sample(range(1, n), parts - 1))
        result = []
        current = 0
        for cut in cut_points:
            result.append(cut - current)
            current = cut
        result.append(n - current)
        return result

    def _build_single_desc(self, count, force_long=False):
        """构建现卤现捞模式下的单个描述。"""
        food = random.choice(self.foods)
        quant = random.choice(self.quantifiers)
        count_str = self._int_to_chinese(count)

        use_flavor = True
        use_emotion = True if force_long or random.random() > 0.3 else False

        desc_parts = [count_str, quant]

        if use_emotion:
            desc_parts.append(random.choice(self.adj_emotion))
        if use_flavor:
            desc_parts.append(random.choice(self.adj_flavor))

        desc_parts.append(food)
        return "".join(desc_parts)

    def _build_travel_service_desc(self, count):
        """构建旅游服务模式下的收费项描述。"""
        item = random.choice(self.travel_service_items)
        count_str = self._int_to_chinese(count)
        return f"{count_str}{item['quantifier']}{item['name']}"

    def _try_generate_lomei_strategy(self, n):
        """现卤现捞模式的生成策略。"""
        if n == 1:
            food = random.choice(self.foods)
            quant = random.choice(self.quantifiers)
            adj1 = random.choice(self.adj_emotion)
            adj2 = random.choice(self.adj_flavor)
            count_str = self._int_to_chinese(1)

            templates = [
                f"{count_str}{quant}{adj1}{adj2}{food}",
                f"{count_str}{quant}{adj1}但{adj2}的{food}",
                f"{count_str}{quant}老板私藏的{adj2}{food}",
            ]
            return random.choice(templates)

        if n <= 5:
            if random.random() > 0.5:
                return self._build_single_desc(n)

            counts = self._partition_integer(n, 2)
            part1 = self._build_single_desc(counts[0])
            part2 = self._build_single_desc(counts[1])
            conn = random.choice(self.connectors)
            return f"{part1}{conn}{part2}"

        if n <= 20:
            parts_num = random.choice([2, 3])
            counts = self._partition_integer(n, parts_num)
            desc_list = [self._build_single_desc(c) for c in counts]
            return "，".join(desc_list)

        return self._build_single_desc(n, force_long=True)

    def _try_generate_strategy(self, n):
        """根据当前模式选择生成策略。"""
        if self.mode == "travel_service":
            return self._build_travel_service_desc(n)
        return self._try_generate_lomei_strategy(n)

    def generate(self, n):
        if not isinstance(n, int) or n <= 0:
            return None

        max_bytes = 127
        for _ in range(15):
            result = self._try_generate_strategy(n)
            if self._get_byte_len(result) <= max_bytes:
                return result

        return self.fallback_template.format(count=self._int_to_chinese(n))


# --- 模块导出说明 ---
# 此模块可被其他 Python 文件导入使用。
# 使用方式：
#   from product_name_generator import LoMeiGenerator
#   generator = LoMeiGenerator()
#   product_name = generator.generate(5)
#
# 如需切换行业，请仅修改顶部的 PRODUCT_NAME_GENERATOR_MODE，
# 并确保目标模式已在 PRODUCT_NAME_GENERATOR_MODE_CONFIGS 中注册。
