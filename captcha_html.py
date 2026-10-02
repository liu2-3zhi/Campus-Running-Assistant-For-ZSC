from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup


def get_captcha_original_width(html_content):
    """
    【移动端验证码缩放】获取验证码的原始宽度
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        container = soup.find("div")
        if not container:
            return None

        spans = container.find_all("span")
        if not spans:
            return None

        pixel_classes = list(set([s.get("class")[0]
                             for s in spans if s.get("class")]))
        if not pixel_classes:
            return None
        first_line_spans = 0
        for child in container.contents:
            if child.name == "br":
                break
            if child.name == "span":
                first_line_spans += 1

        num_cols = first_line_spans
        if num_cols == 0:
            return None
        style_tag = soup.find("style")
        if not style_tag:
            return None

        css_text = style_tag.string
        sample_pixel_class = pixel_classes[0]
        container_class = container.get("class")[0]
        w_match = re.search(
            rf"\.{container_class}\s+span[^}}]*width\s*:\s*(\d+(\.\d+)?)px", css_text
        )

        if not w_match:
            w_match = re.search(
                rf"\.{sample_pixel_class}[^}}]*width\s*:\s*(\d+(\.\d+)?)px", css_text
            )

        if not w_match:
            return None

        old_pixel_w = float(w_match.group(1))
        original_width = num_cols * old_pixel_w

        logging.debug(
            f"[get_captcha_original_width] 列数={num_cols}, 像素宽度={old_pixel_w}px, 总宽度={original_width}px"
        )

        return original_width

    except Exception as e:
        logging.error(f"[get_captcha_original_width] 解析失败: {e}")
        return None

def get_captcha_dimensions(html_content):
    """
    解析像素验证码 HTML，计算其在浏览器中渲染的实际宽度和高度。
    
    计算公式:
    Width  = (Cols * CellW) + ((Cols - 1) * Gap) + Padding*2 + Border*2
    Height = (Rows * CellH) + ((Rows - 1) * Gap) + Padding*2 + Border*2
    
    Returns:
        tuple: (width, height) 浮点数。如果解析失败返回 (0.0, 0.0)
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. 获取容器和基本信息
        container = soup.find("div")
        if not container:
            logging.warning("[get_dimensions] 无法找到容器 div")
            return 0.0, 0.0

        container_class = container.get("class")[0] if container.get("class") else None
        if not container_class:
            return 0.0, 0.0

        style_tag = soup.find("style")
        if not style_tag:
            return 0.0, 0.0

        css_text = style_tag.string
        
        # 2. 正则提取 CSS 参数 (复用原有逻辑)
        num_cols = 0
        pixel_w = 0.0
        pixel_h = 0.0
        gap = 0.0
        padding_w = 0.0
        border_w = 0.0

        # 提取列数和单格宽度
        grid_match = re.search(
            r"grid-template-columns\s*:\s*repeat\(\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)\s*px\s*\)",
            css_text,
            re.IGNORECASE,
        )
        if grid_match:
            num_cols = int(grid_match.group(1))
            pixel_w = float(grid_match.group(2))
        else:
            logging.warning("[get_dimensions] 无法解析 grid-template-columns")
            return 0.0, 0.0

        # 提取 Gap
        gap_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bgap\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if gap_match:
            gap = float(gap_match.group(1))

        # 提取高度 (如果没定义高度，默认是正方形，即高度=宽度)
        h_match = re.search(
            rf"\.{container_class}\s+span[^}}]*?height\s*:\s*(\d+(\.\d+)?)px",
            css_text,
            re.IGNORECASE,
        )
        if h_match:
            pixel_h = float(h_match.group(1))
        else:
            pixel_h = pixel_w

        # 提取 Padding (左右/上下一致)
        pad_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bpadding\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if pad_match:
            padding_val = float(pad_match.group(1))
            padding_w = padding_val * 2 # 左右
            # padding_h = padding_val * 2 # 上下 (通常 CSS padding: 10px 意味着四边都是 10)

        # 提取 Border
        bor_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bborder\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if bor_match:
            border_val = float(bor_match.group(1))
            border_w = border_val * 2
        
        # 3. 计算行数 (Rows) - 新增逻辑
        # 通过统计 span 标签的总数来倒推行数
        spans = container.find_all("span")
        total_cells = len(spans)
        num_rows = 0
        if num_cols > 0:
            num_rows = math.ceil(total_cells / num_cols)
        
        # 4. 计算最终宽高
        # 宽度 = (列数 * 单宽) + (列间隙数 * Gap) + Padding + Border
        final_width = (num_cols * pixel_w) + ((num_cols - 1) * gap) + padding_w + border_w
        
        # 高度 = (行数 * 单高) + (行间隙数 * Gap) + Padding + Border
        # 注意：行间隙数量通常也是 rows - 1
        final_height = (num_rows * pixel_h) + ((num_rows - 1) * gap) + padding_w + border_w

        logging.info(f"[get_dimensions] Grid: {num_cols}x{num_rows} | Cell: {pixel_w}x{pixel_h} | Gap: {gap} | Pad/Bor: {padding_w/2}/{border_w/2}")
        
        return final_width, final_height

    except Exception as e:
        logging.error(f"[get_dimensions] 计算出错: {e}", exc_info=True)
        return 0.0, 0.0


def resize_captcha_html(html_content, target_width):
    """
    自动分析并调整像素验证码HTML的大小 (Grid Layout 增强版 - 修正Padding/Border计算)。
    """
    try:
        target_width = float(target_width)
        soup = BeautifulSoup(html_content, "html.parser")
        container = soup.find("div")
        if not container:
            logging.warning("[resize_captcha_html] 无法找到容器 div")
            return html_content

        container_class = container.get("class")[0]
        style_tag = soup.find("style")
        if not style_tag:
            return html_content

        css_text = style_tag.string
        num_cols = 0
        old_pixel_w = 0.0
        old_pixel_h = 0.0
        old_gap = 0.0
        grid_match = re.search(
            r"grid-template-columns\s*:\s*repeat\(\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)\s*px\s*\)",
            css_text,
            re.IGNORECASE,
        )

        if grid_match:
            num_cols = int(grid_match.group(1))
            old_pixel_w = float(grid_match.group(2))
            logging.info(
                f"[验证码缩放] 检测到 CSS Grid 布局: {num_cols} 列, 原始宽 {old_pixel_w}px"
            )
        else:
            pass

        if num_cols == 0:
            logging.error("[resize_captcha_html] 无法解析列数，跳过缩放")
            return html_content
        gap_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bgap\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if gap_match:
            old_gap = float(gap_match.group(1))
        h_match = re.search(
            rf"\.{container_class}\s+span[^}}]*?height\s*:\s*(\d+(\.\d+)?)px",
            css_text,
            re.IGNORECASE,
        )
        if h_match:
            old_pixel_h = float(h_match.group(1))
        else:
            old_pixel_h = old_pixel_w
        padding_w = 0.0
        border_w = 0.0
        pad_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bpadding\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if pad_match:
            padding_w = float(pad_match.group(1)) * 2
        bor_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bborder\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if bor_match:
            border_w = float(bor_match.group(1)) * 2
        original_grid_width = (num_cols * old_pixel_w) + \
            ((num_cols - 1) * old_gap)

        if original_grid_width <= 0:
            return html_content
        available_grid_width = target_width - padding_w - border_w

        if available_grid_width <= 0:
            logging.warning(f"[验证码缩放] 目标宽度过小，无法容纳Padding/Border")
            return html_content
        scale_ratio = available_grid_width / original_grid_width
        if scale_ratio >= 1.0:
            logging.info(
                f"[验证码缩放] 目标宽度 ({target_width}px) 足以容纳原始尺寸，跳过放大 (Ratio: {scale_ratio:.2f})"
            )
            return html_content
        new_pixel_w = old_pixel_w * scale_ratio
        new_pixel_h = old_pixel_h * scale_ratio
        new_gap = old_gap * scale_ratio

        logging.info(
            f"[验证码缩放] Scaling: {scale_ratio:.4f} | Pad/Bor: {padding_w}/{border_w} | Target Grid: {available_grid_width:.2f}px"
        )
        new_css = css_text
        new_css = re.sub(
            r"(grid-template-columns\s*:\s*repeat\(\s*\d+\s*,\s*)(\d+(?:\.\d+)?)px",
            rf"\g<1>{new_pixel_w:.4f}px",
            new_css,
            flags=re.IGNORECASE,
        )
        if old_gap >= 0:
            new_css = re.sub(
                rf"(\.{container_class}\s*\{{.*?\bgap\s*:\s*)(\d+(?:\.\d+)?)px",
                rf"\g<1>{new_gap:.4f}px",
                new_css,
                flags=re.DOTALL | re.IGNORECASE,
            )
        new_css = re.sub(
            rf"(\.{container_class}\s+span[^}}]*?width\s*:\s*)(\d+(\.\d+)?)px",
            rf"\g<1>{new_pixel_w:.4f}px",
            new_css,
            flags=re.IGNORECASE,
        )
        new_css = re.sub(
            rf"(\.{container_class}\s+span[^}}]*?height\s*:\s*)(\d+(\.\d+)?)px",
            rf"\g<1>{new_pixel_h:.4f}px",
            new_css,
            flags=re.IGNORECASE,
        )
        spans = container.find_all("span")
        pixel_classes = set([s.get("class")[0]
                            for s in spans if s.get("class")])

        for p_class in pixel_classes:
            new_css = re.sub(
                rf"(\.{p_class}[^}}]*?(?<![-\w])width\s*:\s*)(\d+(\.\d+)?)px",
                rf"\g<1>{new_pixel_w:.4f}px",
                new_css,
                flags=re.IGNORECASE,
            )
            new_css = re.sub(
                rf"(\.{p_class}[^}}]*?(?<![-\w])height\s*:\s*)(\d+(\.\d+)?)px",
                rf"\g<1>{new_pixel_h:.4f}px",
                new_css,
                flags=re.IGNORECASE,
            )

        style_tag.string = new_css
        return str(soup)

    except Exception as e:
        logging.error(f"[resize_captcha_html] 调整失败: {e}", exc_info=True)
        return html_content
