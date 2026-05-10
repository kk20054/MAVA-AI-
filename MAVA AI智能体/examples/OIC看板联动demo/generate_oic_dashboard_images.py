from PIL import Image, ImageDraw, ImageFont
import math
from pathlib import Path


OUT_DIR = Path(r"D:\工银亚洲\AI智能体构建\20260506智能体构建优化版\OIC看板设计方案")
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


COL = {
    "bg": "#f6f8fb",
    "card": "#ffffff",
    "line": "#d8dee6",
    "text": "#1f2933",
    "muted": "#6b7280",
    "red": "#c9141e",
    "red_soft": "#fff1f2",
    "teal": "#0b7f86",
    "green": "#147d55",
    "orange": "#b95d21",
    "blue": "#2f6f9f",
}


DATA = {
    "deposit": {
        "title": "存款",
        "file": "01_OIC看板_存款点击态.png",
        "value": "56.90",
        "unit": "亿港元",
        "d": "+0.19",
        "dp": "+0.35%",
        "m": "+2.74",
        "mp": "+5.07%",
        "y": "+7.16",
        "yp": "+14.41%",
        "trend": "存款 30 天趋势",
        "month": "存款按月趋势",
        "rank": "存款产品贡献 Rank",
        "cust": "客户按存款贡献 Top20",
        "products": [
            ("定期存款 - 非CMB分润", 27.6, 1.12, "+6.1%"),
            ("活期存款 - 非员工", 10.8, 0.82, "+8.3%"),
            ("储蓄存款", 7.4, 0.31, "+4.6%"),
            ("发行存款证", 5.8, -0.16, "-2.7%"),
            ("定期存款 - CMB分润", 3.9, 0.24, "+3.2%"),
            ("活期存款 - 员工", 1.4, 0.06, "+2.1%"),
        ],
        "customers": [
            "ABC International Holdings Ltd.", "Global Trade Partners Ltd.",
            "Sunrise Group Co., Ltd.", "Evergreen Infrastructure Ltd.",
            "Asia Pacific Logistics Co.", "North Bay Trading Ltd."
        ],
        "analysis": "存款较上月增加，主要由定期存款及活期非员工账户拉动。建议优先查看定期存款到期续作和大额客户流入来源。",
    },
    "loan": {
        "title": "贷款",
        "file": "02_OIC看板_贷款点击态.png",
        "value": "59.92",
        "unit": "亿港元",
        "d": "-0.14",
        "dp": "-0.23%",
        "m": "+0.11",
        "mp": "+0.18%",
        "y": "+2.60",
        "yp": "+4.80%",
        "trend": "贷款 30 天趋势",
        "month": "贷款按月趋势",
        "rank": "贷款产品贡献 Rank",
        "cust": "客户按贷款贡献 Top20",
        "products": [
            ("房产按揭贷款", 20.4, -0.06, "-0.3%"),
            ("贸易融资", 9.8, 0.32, "+3.4%"),
            ("银团贷款", 7.6, -0.18, "-2.3%"),
            ("个人贷款", 6.1, 0.09, "+1.5%"),
            ("税务贷款", 4.2, 0.16, "+4.1%"),
            ("支票贴现", 3.8, -0.05, "-1.2%"),
            ("定期循环贷款", 2.9, 0.11, "+3.8%"),
            ("信用卡贷款", 1.7, 0.04, "+2.6%"),
        ],
        "customers": [
            "Harbour Property Finance Ltd.", "Pearl River Manufacturing Ltd.",
            "Pacific Trade Finance Ltd.", "Golden Bridge Holdings Ltd.",
            "Apex Import Export Ltd.", "Unity Retail Group Ltd."
        ],
        "analysis": "贷款余额较昨日回落，主要受银团贷款和房产按揭贷款下降影响；贸易融资和税务贷款仍有正贡献，可进一步下钻客户层面。",
    },
    "lowcost": {
        "title": "低息存款",
        "file": "03_OIC看板_低息存款点击态.png",
        "value": "18.17",
        "unit": "亿港元",
        "d": "+0.13",
        "dp": "+0.70%",
        "m": "+1.26",
        "mp": "+7.41%",
        "y": "+2.27",
        "yp": "+14.28%",
        "trend": "低息存款 30 天趋势",
        "month": "低息存款按月趋势",
        "rank": "低息存款产品贡献 Rank",
        "cust": "客户按低息存款贡献 Top20",
        "products": [
            ("活期存款 - 非员工", 10.5, 0.72, "+7.4%"),
            ("储蓄存款", 6.3, 0.38, "+6.2%"),
            ("活期存款 - 员工", 1.4, 0.05, "+3.0%"),
        ],
        "customers": [
            "Bright Future Holdings Ltd.", "Blue Ocean Trading Ltd.",
            "Metro Services Co., Ltd.", "Fortune Technology Ltd.",
            "Kingdom Retail Ltd.", "Loyal Capital Ltd."
        ],
        "analysis": "低息存款延续增长，是当前 OIC 负债结构改善的主要来源；建议关注活期非员工账户的稳定性和客户资金留存。",
    },
    "fee": {
        "title": "非息收入",
        "file": "04_OIC看板_非息收入点击态.png",
        "value": "1.28",
        "unit": "亿港元",
        "d": "+0.01",
        "dp": "+5.79%",
        "m": "+0.18",
        "mp": "+16.38%",
        "y": "+0.53",
        "yp": "+70.67%",
        "trend": "非息收入 30 天趋势",
        "month": "非息收入按月趋势",
        "rank": "非息收入来源 Rank",
        "cust": "客户按非息收入贡献 Top20",
        "products": [
            ("收费及佣金收入", 0.62, 0.07, "+12.5%"),
            ("交易业务净收入", 0.28, 0.04, "+16.0%"),
            ("财资业务净收入", 0.19, 0.03, "+14.1%"),
            ("FVPL金融资产及负债净收益", 0.13, 0.02, "+11.8%"),
            ("收费及佣金支出抵减", 0.06, -0.01, "-3.2%"),
        ],
        "customers": [
            "Summit Securities Ltd.", "Central Wealth Ltd.",
            "Oriental Asset Mgmt Ltd.", "Prime Insurance Brokers Ltd.",
            "Union Global Markets Ltd.", "Navigator Advisory Ltd."
        ],
        "analysis": "非息收入月内增长较快，主要来自收费及佣金收入和交易业务净收入。建议进一步核对一次性收入和可持续收入占比。",
    },
}


def text(draw, xy, s, size=16, color=None, bold=False, anchor=None):
    draw.text(xy, s, fill=color or COL["text"], font=font(size, bold), anchor=anchor)


def rounded(draw, box, fill, outline=None, width=1, radius=10):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def line_chart(draw, box, metric_key):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    p = 28
    base = {"deposit": 55, "loan": 60.5, "lowcost": 16.8, "fee": 1.0}[metric_key]
    vals = [base + math.sin(i / 4) * 0.25 + i * (-0.006 if metric_key == "loan" else 0.035) + (0.08 if i % 7 == 0 else 0) for i in range(30)]
    mn, mx = min(vals) - .2, max(vals) + .2
    pts = []
    for i, v in enumerate(vals):
        px = x1 + p + i * (w - 2 * p) / 29
        py = y2 - p - (v - mn) / (mx - mn) * (h - 2 * p)
        pts.append((px, py))
    for i in range(4):
        yy = y1 + p + i * (h - 2 * p) / 3
        draw.line((x1 + p, yy, x2 - p, yy), fill="#e6ebf1", width=1)
    draw.line(pts, fill=COL["red"], width=3)
    for i, pt in enumerate(pts):
        if i % 4 == 0 or i == 29:
            draw.ellipse((pt[0] - 4, pt[1] - 4, pt[0] + 4, pt[1] + 4), fill="white", outline=COL["red"], width=2)
    text(draw, (x1 + p, y2 - 15), "04-06", 12, COL["muted"])
    text(draw, (x1 + w / 2 - 18, y2 - 15), "04-21", 12, COL["muted"])
    text(draw, (x2 - p - 34, y2 - 15), "05-05", 12, COL["muted"])


def bar_chart(draw, box, metric_key):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    p = 32
    vals = [4.1, 4.8, 5.3, 5.0, 5.7, 6.0, 5.2, 5.5, 5.8, 6.1, 6.4, 6.8]
    vals = [v / 5 if metric_key == "fee" else v * 2.8 if metric_key == "lowcost" else v * 9 for v in vals]
    mx = max(vals) * 1.15
    for i in range(3):
        yy = y1 + p + i * (h - 2 * p) / 2
        draw.line((x1 + p, yy, x2 - p, yy), fill="#e6ebf1", width=1)
    pts = []
    for i, v in enumerate(vals):
        bw = 20
        px = x1 + p + i * 31
        py = y2 - p - v / mx * (h - 2 * p)
        draw.rectangle((px, py, px + bw, y2 - p), fill=COL["teal"])
        text(draw, (px - 2, y2 - 14), str(i + 1), 10, COL["muted"])
        pts.append((px + 10, y2 - p - (math.sin(i / 1.8) + 1.3) / 2.8 * (h - 2 * p)))
    draw.line(pts, fill=COL["red"], width=3)
    for pt in pts:
        draw.ellipse((pt[0] - 3, pt[1] - 3, pt[0] + 3, pt[1] + 3), fill="white", outline=COL["red"], width=2)
    text(draw, (x2 - 118, y1 + 12), "环比增速", 12, COL["red"])


def kpi_card(draw, box, key, selected):
    x1, y1, x2, y2 = box
    d = DATA[key]
    rounded(draw, box, "#fff5f5" if selected else "white", COL["red"] if selected else COL["line"], 2 if selected else 1, 9)
    text(draw, (x1 + 16, y1 + 16), d["title"], 17, bold=True)
    text(draw, (x1 + 16, y1 + 56), d["value"], 34, "#0f172a", True)
    text(draw, (x1 + 125, y1 + 70), d["unit"], 15, "#475569", True)
    rows = [("较昨日", d["d"], d["dp"]), ("较上月", d["m"], d["mp"]), ("较年初", d["y"], d["yp"])]
    yy = y1 + 106
    for lab, val, pct in rows:
        text(draw, (x1 + 16, yy), lab, 13, "#4b5563")
        text(draw, (x1 + 135, yy), val, 13, "#374151", True, anchor="ra")
        text(draw, (x2 - 16, yy), pct, 13, COL["green"] if not pct.startswith("-") else COL["red"], True, anchor="ra")
        yy += 25
    draw.line((x1 + 16, y2 - 25, x2 - 16, y2 - 25), fill="#edf0f4")
    text(draw, (x1 + 16, y2 - 17), "点击刷新趋势 / 产品 Rank / 客户贡献", 12, COL["muted"])


def draw_table(draw, x, y, w, headers, rows, widths, row_h=30, head_h=34):
    draw.rectangle((x, y, x + w, y + head_h), fill="#f3f6fa")
    cx = x
    for h, cw in zip(headers, widths):
        text(draw, (cx + 8, y + 9), h, 12, "#475569", True)
        cx += cw
    yy = y + head_h
    for r in rows:
        draw.line((x, yy, x + w, yy), fill="#eef1f5")
        cx = x
        for i, (cell, cw) in enumerate(zip(r, widths)):
            color = COL["green"] if str(cell).startswith("+") else COL["red"] if str(cell).startswith("-") else COL["text"]
            text(draw, (cx + 8, yy + 8), str(cell), 12, color, i >= 3 and (str(cell).startswith("+") or str(cell).startswith("-")))
            cx += cw
        yy += row_h


def render(metric_key):
    d = DATA[metric_key]
    img = Image.new("RGB", (1920, 1080), COL["bg"])
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, 1920, 64), fill="white", outline=COL["line"])
    draw.ellipse((26, 15, 60, 49), outline=COL["red"], width=3)
    text(draw, (43, 32), "工", 17, COL["red"], True, "mm")
    text(draw, (76, 22), "ICBC ASIA", 28, "#111827", True)
    draw.line((220, 14, 220, 50), fill=COL["line"])
    text(draw, (240, 22), "MAVA AI 智能财会助手 · OIC 经营看板", 18, "#111827", True)
    for i, s in enumerate(["2026-05-05", "OIC：EE001408023", "币种：港元 / 人民币折算"]):
        bx = 1190 + i * 170 if i < 2 else 1530
        bw = 150 if i < 2 else 230
        rounded(draw, (bx, 14, bx + bw, 50), "white", COL["line"], 1, 8)
        text(draw, (bx + 14, 24), s, 13, "#374151")

    draw.rectangle((0, 64, 68, 1080), fill="white", outline=COL["line"])
    for i, sym in enumerate(["⌂", "▦", "☰", "◎", "⚙"]):
        y = 86 + i * 58
        rounded(draw, (15, y, 53, y + 38), COL["red_soft"] if i == 0 else "white", None, 1, 9)
        text(draw, (34, y + 19), sym, 18, COL["red"] if i == 0 else "#64748b", True, "mm")

    x0, y0 = 88, 82
    text(draw, (x0, y0), "OIC 维度经营驾驶舱", 20, "#111827", True)
    text(draw, (x0 + 220, y0 + 3), "第一行点击决定第二行和第三行：趋势 / 产品 Rank / 客户贡献", 14, COL["muted"])

    card_y, card_w, gap = 116, 268, 14
    for i, key in enumerate(["deposit", "loan", "lowcost", "fee"]):
        kpi_card(draw, (x0 + i * (card_w + gap), card_y, x0 + i * (card_w + gap) + card_w, card_y + 190), key, key == metric_key)

    panels_y = 326
    panel_w, panel_h = 335, 300
    for i, title in enumerate([d["trend"], d["month"], d["rank"]]):
        x = x0 + i * (panel_w + gap)
        w = 420 if i == 2 else panel_w
        rounded(draw, (x, panels_y, x + w, panels_y + panel_h), "white", COL["line"], 1, 8)
        text(draw, (x + 16, panels_y + 14), title, 16, "#111827", True)
        text(draw, (x + 16, panels_y + 40), "单位：百万港元；点击可进一步筛选", 12, COL["muted"])
        if i == 0:
            line_chart(draw, (x + 10, panels_y + 62, x + w - 10, panels_y + panel_h - 10), metric_key)
        elif i == 1:
            bar_chart(draw, (x + 10, panels_y + 62, x + w - 10, panels_y + panel_h - 10), metric_key)
        else:
            rows = []
            for idx, r in enumerate(d["products"][:7], 1):
                rows.append([idx, r[0], f"{r[1]:.2f}", f"{r[2]:+.2f}", r[3]])
            draw_table(draw, x + 12, panels_y + 62, w - 24, ["Rank", "产品", "余额/收入", "较上月", "增幅"], rows, [42, 150, 72, 72, 54], 28, 32)

    bottom_y = 646
    bottom_w = 1105
    rounded(draw, (x0, bottom_y, x0 + bottom_w, bottom_y + 300), "white", COL["line"], 1, 8)
    text(draw, (x0 + 16, bottom_y + 14), d["cust"], 17, "#111827", True)
    text(draw, (x0 + 16, bottom_y + 42), "按当前指标口径排序；点击客户进入客户画像和贡献解释", 12, COL["muted"])
    rows = []
    for i, c in enumerate(d["customers"], 1):
        val = 0.08 + i * .02 if metric_key == "fee" else 7.8 - i * .72
        change = 0.62 - i * .05
        rows.append([i, c, "Corporate" if i <= 4 else "SME", ["Manufacturing", "Trading", "Real Estate", "Logistics", "Financial Services", "Retail"][i - 1], f"{val:.2f}", f"{change:+.2f}", f"+{7.8 - i * .6:.2f}%", f"{1.52 - i * .13:.2f}%"])
    draw_table(draw, x0 + 12, bottom_y + 70, bottom_w - 24, ["Rank", "客户名称", "类型", "行业", d["title"], "较上月", "增幅", "占比"], rows, [44, 245, 95, 145, 78, 78, 70, 58], 29, 34)

    chat_x = 1220
    draw.rectangle((chat_x, 64, 1920, 1080), fill="white", outline=COL["line"])
    text(draw, (chat_x + 24, 88), "✦ AI 分析助手", 19, "#111827", True)
    rounded(draw, (chat_x + 18, 126, 1890, 246), "#fffafa", "#f1b9be", 1, 8)
    draw.line((1188, 178, chat_x + 18, 178), fill=COL["red"], width=2)
    text(draw, (chat_x + 34, 142), "当前上下文（来自 OIC 看板点击）", 15, "#8b1f25", True)
    context = [("指标", d["title"]), ("OIC", "EE001408023"), ("日期", "2026-05-05"), ("粒度", "日 / 月 / 产品 / 客户")]
    for i, (a, b) in enumerate(context):
        cx = chat_x + 36 + (i % 2) * 220
        cy = 176 + (i // 2) * 42
        text(draw, (cx, cy), a, 12, COL["muted"])
        text(draw, (cx, cy + 18), b, 14, "#111827", True)
    rounded(draw, (chat_x + 18, 274, 1890, 520), "#f8fafc", COL["line"], 1, 14)
    text(draw, (chat_x + 40, 298), f"已按 OIC 维度分析 {d['title']}：", 16, "#111827", True)
    lines = [
        f"当前 {d['title']} 为 {d['value']}{d['unit']}，较上月 {d['m']}，增幅 {d['mp']}。",
        d["analysis"],
        "第二行已同步刷新为 30 天趋势、按月走势和产品贡献 Rank；第三行展示客户 Top20 贡献。",
    ]
    yy = 334
    for line in lines:
        text(draw, (chat_x + 48, yy), "• " + line, 14, "#374151")
        yy += 42
    text(draw, (chat_x + 18, 548), "推荐分析", 15, "#374151", True)
    sugg = [("分析变动原因", "拆解产品、客户和时间贡献"), ("查看产品 Rank", "按当前指标展示产品贡献"), ("查看 Top20 客户", "定位核心客户增减来源"), ("生成 OIC 摘要", "生成可放入经营报告的文字")]
    for i, (a, b) in enumerate(sugg):
        sx = chat_x + 18 + (i % 2) * 245
        sy = 576 + (i // 2) * 92
        rounded(draw, (sx, sy, sx + 230, sy + 76), "white", COL["line"], 1, 8)
        text(draw, (sx + 14, sy + 14), a, 14, "#111827", True)
        text(draw, (sx + 14, sy + 42), b, 12, COL["muted"])
    rounded(draw, (chat_x + 18, 800, 1890, 844), "white", COL["line"], 1, 8)
    text(draw, (chat_x + 36, 813), "请输入要进一步分析的问题，例如：这个指标为什么变化？哪个产品拖累？Top 客户是谁？", 13, "#9aa3af")
    for i, b in enumerate(["筛选看板", "生成报告", "附加明细"]):
        rounded(draw, (chat_x + 18 + i * 116, 860, chat_x + 118 + i * 116, 894), "#f1fbfc" if i == 0 else "white", "#b7dce0" if i == 0 else COL["line"], 1, 7)
        text(draw, (chat_x + 34 + i * 116, 869), b, 13, COL["teal"] if i == 0 else "#374151")

    draw.line((260, 986, 760, 986), fill=COL["red"], width=2)
    text(draw, (430, 1000), "Dashboard Click Sends Context to Chat", 13, COL["red"], True)
    draw.line((1280, 986, 1720, 986), fill=COL["teal"], width=2)
    text(draw, (1390, 1000), "Chat Can Filter Dashboard", 13, COL["teal"], True)

    img.save(OUT_DIR / d["file"], "PNG")


if __name__ == "__main__":
    for key in DATA:
        render(key)
    print("generated", len(DATA), "dashboard images")
