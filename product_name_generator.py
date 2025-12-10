import random

class LoMeiGenerator:
    """
    现卤现捞商品名生成器 (纯中文数字版)
    """

    def __init__(self):
        # 1. 食材库
        self.foods = [
            "鸭脖", "鸭翅", "鸭掌", "鸭舌", "鸭头", "锁骨", 
            "鱼豆腐", "豆皮", "海带结", "藕片", "烤肠", "波波肠", 
            "鸡尖", "鹌鹑蛋", "腐竹", "魔芋爽", "大鸡腿", "兰花干"
        ]

        # 2. 量词库
        self.quantifiers = ["根", "串", "块", "份", "个", "只", "大把", "口"]

        # 3. 风味形容词
        self.adj_flavor = [
            "秘制", "麻辣", "五香", "甜辣", "变态辣", "爆辣", 
            "酱香", "卤味", "满口香", "红油", "脆皮", "多汁", 
            "Q弹", "入味", "鲜嫩", "吮指", "藤椒"
        ]

        # 4. 趣味/情感形容词 (核心趣味来源)
        self.adj_emotion = [
            "寂寞的", "快乐的", "治愈的", "灵魂", "让室友流泪的", 
            "高贵的", "卑微的", "暴躁的", "佛系养生的", "充满希望的", 
            "绝望的", "初恋般的", "热血的", "深夜的", "独自享用的", 
            "令人发指的", "不仅防饿还能防脱发的", "吃完就通过考试的",
            "甚至想再来一份的", "老板含泪推荐的", "也就是个", "减肥路上的绊脚石"
        ]

        # 5. 连接词
        self.connectors = ["搭配", "配上", "以及", "还有", "加上", "和"]

        # 6. 中文数字映射
        self.zh_nums = list("零一二三四五六七八九")
        self.zh_units = ["", "十", "百", "千", "万"]

    def _int_to_chinese(self, n: int) -> str:
        """
        将整数转换为中文数字字符串
        例如: 1 -> 一, 12 -> 十二, 20 -> 二十, 105 -> 一百零五
        """
        if n == 0: return "零"
        
        # 简单处理万以内的数字，满足现捞场景
        s = str(n)
        length = len(s)
        result = []
        
        # 逐位处理
        for i, digit in enumerate(s):
            d = int(digit)
            unit = self.zh_units[length - i - 1]
            
            if d != 0:
                result.append(self.zh_nums[d] + unit)
            else:
                # 处理零：如果前一位不是零，且当前位不是最后一位，加零
                # (简化逻辑：对于连续零，只加一个零，且不加单位)
                if result and result[-1][-1] != "零":
                    result.append("零")
        
        # 拼接结果
        final_str = "".join(result)
        
        # 修正逻辑：去掉末尾的“零”
        if final_str.endswith("零"):
            final_str = final_str[:-1]
            
        # 口语修正：10-19 读作 "十" 到 "十九"，而不是 "一十"
        if 10 <= n < 20 and final_str.startswith("一十"):
            final_str = final_str[1:]
            
        return final_str

    def _get_byte_len(self, s: str) -> int:
        """计算字符串的 UTF-8 字节长度 (中文通常占3字节)"""
        if s is None:
            return 0
        return len(s.encode('utf-8'))

    def _partition_integer(self, n, parts):
        """整数分拆：将 n 随机拆分为 parts 个正整数之和"""
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
        """构建单个描述，count会被转为中文"""
        food = random.choice(self.foods)
        quant = random.choice(self.quantifiers)
        
        # 核心修改：将数字转为中文
        count_str = self._int_to_chinese(count)

        use_flavor = True
        # 如果强制长描述，或者随机概率触发情感词
        use_emotion = True if force_long or random.random() > 0.3 else False
        
        desc_parts = [count_str, quant]
        
        if use_emotion:
            desc_parts.append(random.choice(self.adj_emotion))
        if use_flavor:
            desc_parts.append(random.choice(self.adj_flavor))
            
        desc_parts.append(food)
        return "".join(desc_parts)

    def generate(self, n):
        # 1. 非法输入处理
        if not isinstance(n, int) or n <= 0:
            return None

        MAX_BYTES = 127
        
        # 尝试生成的循环
        for _ in range(15): # 增加尝试次数，因为中文数字占字节更多，更容易超长
            res = self._try_generate_strategy(n)
            if self._get_byte_len(res) <= MAX_BYTES:
                return res
        
        # 兜底方案 (也必须用中文数字)
        return f"{self._int_to_chinese(n)}份现捞小吃"

    def _try_generate_strategy(self, n):
        """根据 n 的大小选择生成策略"""
        
        # 策略 A: n=1
        if n == 1:
            food = random.choice(self.foods)
            quant = random.choice(self.quantifiers)
            adj1 = random.choice(self.adj_emotion)
            adj2 = random.choice(self.adj_flavor)
            count_str = self._int_to_chinese(1) # "一"
            
            # 随机模板
            templates = [
                f"{count_str}{quant}{adj1}{adj2}{food}",
                f"{count_str}{quant}{adj1}但{adj2}的{food}",
                f"{count_str}{quant}老板私藏的{adj2}{food}"
            ]
            return random.choice(templates)

        # 策略 B: 小额数量 (2-5)
        elif n <= 5:
            if random.random() > 0.5:
                # 不拆分：三根变态辣鸭脖
                return self._build_single_desc(n)
            else:
                # 拆分：一根鸭脖 和 两个鸭头
                counts = self._partition_integer(n, 2)
                part1 = self._build_single_desc(counts[0])
                part2 = self._build_single_desc(counts[1])
                conn = random.choice(self.connectors)
                return f"{part1}{conn}{part2}"

        # 策略 C: 中额数量 (6-20)
        elif n <= 20:
            # 尝试拆分成 2-3 份
            parts_num = random.choice([2, 3])
            counts = self._partition_integer(n, parts_num)
            
            desc_list = []
            for c in counts:
                desc_list.append(self._build_single_desc(c))
            
            return "，".join(desc_list)

        # 策略 D: 大额批发 (>20)
        else:
            # 即使数量很大，也要转成中文，例如：五十串
            return self._build_single_desc(n, force_long=True)

# --- 验证测试 ---
if __name__ == "__main__":
    gen = LoMeiGenerator()
    
    test_cases = [1, 2, 5, 10, 12, 23, 99, 105, 0, -1]
    
    print(f"{'Input':<5} | {'Bytes':<5} | {'Result'}")
    print("-" * 60)
    
    for val in test_cases:
        name = gen.generate(val)
        byte_len = len(name.encode('utf-8')) if name else 0
        print(f"{val:<5} | {byte_len:<5} | {name}")