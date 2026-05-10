import json
import datetime
import calendar

# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════

PERCENTAGE_NAMES = ['MA_YOY_GROWTH', 'MA_MOM_GROWTH', 'MA_L_YE_GROWTH']
INCREMENT_NAMES  = ['MA_MOM_INCREMENT', 'MA_YOY_INCREMENT', 'MA_L_YE_INCREMENT']

YOY_SIG   = 0.10
YOY_HIGH  = 0.20
MOM_SIG   = 0.15
LYE_SIG   = 0.10
LYE_HIGH  = 0.20

# ═══════════════════════════════════════════════════════════════════
# 基础工具函数
# ═══════════════════════════════════════════════════════════════════

def isIncrement(suffix_name):
    return any(n in suffix_name for n in INCREMENT_NAMES)

def isPercentage(suffix_name):
    return any(n in suffix_name for n in PERCENTAGE_NAMES)

def format_amount(suffix_name, balance_str):
    try:
        amount_float = float(balance_str)
        if isPercentage(suffix_name):
            amount_float *= 100
        formatted_num = f"{amount_float:,.2f}"
        if amount_float > 0 and (isPercentage(suffix_name) or isIncrement(suffix_name)):
            formatted_num = f"+{formatted_num}"
        if isPercentage(suffix_name):
            formatted_num = f"{formatted_num}%"
        return formatted_num
    except ValueError:
        return '输入无效'

def check_month_end(batchDate):
    next_day = batchDate + datetime.timedelta(days=1)
    return next_day.day == 1

def extract_between_points(text, start_key, end_key):
    start_idx = text.find(start_key)
    end_idx = len(text) if end_key is None else text.find(end_key)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        return ""
    return text[start_idx:end_idx]

def replace_str_with_actual_date(orig_str, sep_symbol, output_format, date_dict):
    parts = orig_str.split(sep=sep_symbol)
    if parts[-1] in date_dict:
        actual_date = date_dict[parts[-1]].strftime(output_format)
        orig_str = f"{''.join(parts[:-1])}{sep_symbol}{actual_date}"
    return orig_str

def create_dict_for_ind(ind_name, mapping_dict, date_dict, input_json_obj):
    ret_dict = {}
    for input_suffix, res_suffix in mapping_dict.items():
        input_suffix = replace_str_with_actual_date(input_suffix, '-', '%Y%m%d', date_dict)
        input_ind_name = f"{ind_name}-{input_suffix}"
        res_suffix = replace_str_with_actual_date(res_suffix, '_', '%Y%m%d', date_dict)
        if input_ind_name in input_json_obj:
            ret_dict[res_suffix] = format_amount(input_suffix, input_json_obj[input_ind_name])
    return ret_dict

def extract_data_from_json(prefix_list, mapping_dict, date_dict, input_json_obj):
    res_dict = {}
    for prefix in prefix_list.keys():
        value = prefix_list[prefix]
        res_dict[value] = create_dict_for_ind(prefix, mapping_dict, date_dict, input_json_obj)
    return res_dict

# ═══════════════════════════════════════════════════════════════════
# 数值格式化工具
# ═══════════════════════════════════════════════════════════════════

def safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def fmt_hkd(v):
    if v is None:
        return '-'
    a = abs(v)
    s = '-' if v < 0 else ''
    if a >= 1e8:
        return f'{s}{a/1e8:.2f}亿港元'
    if a >= 1e4:
        return f'{s}{a/1e4:.2f}万港元'
    return f'{s}{a:.2f}港元'

def fmt_hkd_sign(v):
    if v is None:
        return '-'
    a = abs(v)
    s = '+' if v > 0 else ('-' if v < 0 else '')
    if a >= 1e8:
        return f'{s}{a/1e8:.2f}亿港元'
    if a >= 1e4:
        return f'{s}{a/1e4:.2f}万港元'
    return f'{s}{a:.2f}港元'

def dir_word(v):
    if v is None or v == 0:
        return '持平'
    return '增长' if v > 0 else '下降'

def pct_str(v):
    if v is None:
        return '-'
    return f'{abs(v * 100):.2f}%'

def get_val(raw, code, metric, date_str):
    return safe_float(raw.get(f'{code}-{metric}-{date_str}'))

def _trend_label(mom_g):
    if mom_g is None:
        return ''
    if mom_g > 0.05:
        return '↑改善'
    elif mom_g < -0.05:
        return '↓走弱'
    else:
        return '→平稳'

# ═══════════════════════════════════════════════════════════════════
# 逐项分析文本（资负端）
# ═══════════════════════════════════════════════════════════════════

def build_al_analysis(prefix_dict, raw, dd, section_label, is_me):
    me = dd['ME'].strftime('%Y%m%d')
    bd = dd['BD'].strftime('%Y%m%d') if not is_me else None
    lines, hls, cns = [], [], []

    for code, name in prefix_dict.items():
        bal      = get_val(raw, code, 'MA_BAL', me)
        mtd      = get_val(raw, code, 'MA_MTD_BAL', me)
        ytd      = get_val(raw, code, 'MA_YTD_BAL', me)
        bal_lm   = get_val(raw, code, 'MA_L_M_BAL', me)
        bal_lyye = get_val(raw, code, 'MA_L_YE_BAL', me)
        mtd_ly   = get_val(raw, code, 'MA_L_Y_MTD_BAL', me)
        ytd_ly   = get_val(raw, code, 'MA_L_Y_YTD_BAL', me)
        yoy_inc  = get_val(raw, code, 'MA_YOY_INCREMENT', me)
        yoy_g    = get_val(raw, code, 'MA_YOY_GROWTH', me)
        mom_inc  = get_val(raw, code, 'MA_MOM_INCREMENT', me)
        mom_g    = get_val(raw, code, 'MA_MOM_GROWTH', me)
        lye_inc  = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
        lye_g    = get_val(raw, code, 'MA_L_YE_GROWTH', me)
        bal_bd   = get_val(raw, code, 'MA_BAL', bd) if bd else None

        if all(v is None or v == 0 for v in [bal, mtd, ytd, bal_bd]):
            continue

        parts = []
        if bal is not None:
            parts.append(f'时点余额{fmt_hkd(bal)}')
        if mtd is not None:
            parts.append(f'月日均{fmt_hkd(mtd)}')
        if ytd is not None:
            parts.append(f'年日均{fmt_hkd(ytd)}')
        if bal_bd is not None and not is_me:
            parts.append(f'实时余额{fmt_hkd(bal_bd)}')

        lye_txt = ''
        if lye_g is not None:
            pa = abs(lye_g * 100)
            d  = dir_word(lye_g)
            lye_txt = f'较上年末{d}{pa:.2f}%'
            if lye_inc is not None:
                lye_txt += f'（增量{fmt_hkd_sign(lye_inc)}）'
            if abs(lye_g) >= LYE_HIGH:
                lye_txt += '【变动显著】'
            if abs(lye_g) >= LYE_SIG:
                direction = 'up' if lye_g > 0 else 'down'
                extra = f'，时点余额{fmt_hkd(bal)}' if bal else ''
                tag = '显著增长' if (direction == 'up' and pa >= LYE_HIGH * 100) else ('增长' if direction == 'up' else ('显著下降' if pa >= LYE_HIGH * 100 else '下降'))
                sig_txt = f'{name}（较上年末）{tag}{pa:.2f}%{extra}'
                if direction == 'up':
                    hls.append(sig_txt)
                else:
                    cns.append(sig_txt)

        yoy_txt = ''
        if yoy_g is not None:
            pa = abs(yoy_g * 100)
            d  = dir_word(yoy_g)
            yoy_txt = f'年日均同比{d}{pa:.2f}%'
            if yoy_inc is not None:
                yoy_txt += f'（增量{fmt_hkd_sign(yoy_inc)}）'
            if abs(yoy_g) >= YOY_HIGH:
                yoy_txt += '【变动显著】'

        mom_txt = ''
        if mom_g is not None:
            pa = abs(mom_g * 100)
            d  = dir_word(mom_g)
            mom_txt = f'环比{d}{pa:.2f}%'
            if mom_inc is not None:
                mom_txt += f'（增量{fmt_hkd_sign(mom_inc)}）'
            if abs(mom_g) >= MOM_SIG:
                mom_txt += '【环比变动显著】'
                if mom_g < 0:
                    cns.append(f'{name}环比下降{pa:.2f}%')

        trend = _trend_label(mom_g)
        line = f'{name}：{"，".join(parts)}'
        comps = [t for t in [lye_txt, yoy_txt, mom_txt] if t]
        if comps:
            line += '；' + '，'.join(comps)
        if trend:
            line += f'  {trend}'
        refs = []
        if bal_lyye is not None:
            refs.append(f'上年末{fmt_hkd(bal_lyye)}')
        if bal_lm is not None:
            refs.append(f'上月末{fmt_hkd(bal_lm)}')
        if ytd_ly is not None:
            refs.append(f'去年年日均{fmt_hkd(ytd_ly)}')
        if refs:
            line += f'。参考：{"，".join(refs)}'
        lines.append(line)

    txt = '\n'.join(lines)
    hl_txt = '\n'.join(f'• {h}' for h in hls) if hls else '（暂无显著信号）'
    cn_txt = '\n'.join(f'• {c}' for c in cns) if cns else '（暂无显著信号）'
    return txt, hl_txt, cn_txt

# ═══════════════════════════════════════════════════════════════════
# 逐项分析文本（损益端）
# ═══════════════════════════════════════════════════════════════════

def build_revenue_analysis(prefix_dict, raw, dd, is_me):
    me = dd['ME'].strftime('%Y%m%d')
    bd = dd['BD'].strftime('%Y%m%d') if not is_me else None
    lines, hls, cns = [], [], []

    for code, name in prefix_dict.items():
        ytd      = get_val(raw, code, 'MA_YTD_BAL', me)
        mtd      = get_val(raw, code, 'MA_MTD_BAL', me)
        ytd_ly   = get_val(raw, code, 'MA_L_Y_YTD_BAL', me)
        mtd_ly   = get_val(raw, code, 'MA_L_Y_MTD_BAL', me)
        mtd_lm   = get_val(raw, code, 'MA_L_M_MTD_BAL', me)
        yoy_inc  = get_val(raw, code, 'MA_YOY_INCREMENT', me)
        yoy_g    = get_val(raw, code, 'MA_YOY_GROWTH', me)
        mom_inc  = get_val(raw, code, 'MA_MOM_INCREMENT', me)
        mom_g    = get_val(raw, code, 'MA_MOM_GROWTH', me)
        ytd_bd   = get_val(raw, code, 'MA_YTD_BAL', bd) if bd else None
        mtd_bd   = get_val(raw, code, 'MA_MTD_BAL', bd) if bd else None

        if all(v is None or v == 0 for v in [ytd, mtd, ytd_bd, mtd_bd]):
            continue

        parts = []
        if ytd is not None:
            parts.append(f'年累计{fmt_hkd(ytd)}')
        if mtd is not None:
            parts.append(f'当月{fmt_hkd(mtd)}')
        if ytd_bd is not None and not is_me:
            parts.append(f'实时年累计{fmt_hkd(ytd_bd)}')

        yoy_txt = ''
        if yoy_g is not None:
            pa = abs(yoy_g * 100)
            d  = dir_word(yoy_g)
            yoy_txt = f'同比{d}{pa:.2f}%'
            if yoy_inc is not None:
                yoy_txt += f'（增量{fmt_hkd_sign(yoy_inc)}）'
            if abs(yoy_g) >= YOY_HIGH:
                yoy_txt += '【变动显著】'
            if abs(yoy_g) >= YOY_SIG:
                direction = 'up' if yoy_g > 0 else 'down'
                extra = f'，年累计{fmt_hkd(ytd)}' if ytd else ''
                tag = '显著增长' if (direction == 'up' and pa >= YOY_HIGH * 100) else ('增长' if direction == 'up' else ('显著下降' if pa >= YOY_HIGH * 100 else '下降'))
                sig_txt = f'{name}（年累计同比）{tag}{pa:.2f}%{extra}'
                if direction == 'up':
                    hls.append(sig_txt)
                else:
                    cns.append(sig_txt)

        mom_txt = ''
        if mom_g is not None:
            pa = abs(mom_g * 100)
            d  = dir_word(mom_g)
            mom_txt = f'环比{d}{pa:.2f}%'
            if mom_inc is not None:
                mom_txt += f'（增量{fmt_hkd_sign(mom_inc)}）'
            if abs(mom_g) >= MOM_SIG:
                mom_txt += '【环比变动显著】'
                if mom_g < 0:
                    cns.append(f'{name}当月环比下降{pa:.2f}%')
                elif mom_g > 0:
                    hls.append(f'{name}当月环比增长{pa:.2f}%')

        trend = _trend_label(mom_g)
        line = f'{name}：{"，".join(parts)}'
        comps = [t for t in [yoy_txt, mom_txt] if t]
        if comps:
            line += '；' + '，'.join(comps)
        if trend:
            line += f'  {trend}'
        refs = []
        if ytd_ly is not None:
            refs.append(f'去年同期年累计{fmt_hkd(ytd_ly)}')
        if mtd_lm is not None:
            refs.append(f'上月{fmt_hkd(mtd_lm)}')
        if mtd_ly is not None:
            refs.append(f'去年同月{fmt_hkd(mtd_ly)}')
        if refs:
            line += f'。参考：{"，".join(refs)}'
        lines.append(line)

    txt = '\n'.join(lines)
    hl_txt = '\n'.join(f'• {h}' for h in hls) if hls else '（暂无显著信号）'
    cn_txt = '\n'.join(f'• {c}' for c in cns) if cns else '（暂无显著信号）'
    return txt, hl_txt, cn_txt

# ═══════════════════════════════════════════════════════════════════
# 结构性洞察（跨指标交叉分析）
# ═══════════════════════════════════════════════════════════════════

def build_structural_insights(raw, dd, asset_prefix, liab_prefix, revenue_prefix):
    me = dd['ME'].strftime('%Y%m%d')
    insights = []

    # ── 1. 存款结构 ──
    dep_total    = get_val(raw, 'MA_N11_0', 'MA_BAL', me)
    low_int      = get_val(raw, 'MA_N111_0', 'MA_BAL', me)
    dep_total_ly = get_val(raw, 'MA_N11_0', 'MA_L_YE_BAL', me)
    low_int_ly   = get_val(raw, 'MA_N111_0', 'MA_L_YE_BAL', me)
    fixed_dep    = get_val(raw, 'MA_N112_1', 'MA_BAL', me)
    fixed_dep_ly = get_val(raw, 'MA_N112_1', 'MA_L_YE_BAL', me)

    if dep_total and dep_total != 0 and low_int is not None:
        casa = low_int / dep_total * 100
        insights.append(f'【低息存款占比】低息存款占客户存款比：{casa:.2f}%（时点口径）')
        if dep_total_ly and dep_total_ly != 0 and low_int_ly is not None:
            casa_ly = low_int_ly / dep_total_ly * 100
            chg = casa - casa_ly
            d = '提升' if chg > 0 else '下降'
            insights.append(f'  └ 较上年末（{casa_ly:.2f}%）{d}{abs(chg):.2f}个百分点')
        if fixed_dep is not None:
            fd_pct = fixed_dep / dep_total * 100
            insights.append(f'  └ 定期存款占比：{fd_pct:.2f}%')
            if fixed_dep_ly is not None and dep_total_ly and dep_total_ly != 0:
                fd_pct_ly = fixed_dep_ly / dep_total_ly * 100
                fd_chg = fd_pct - fd_pct_ly
                fd_d = '上升' if fd_chg > 0 else '下降'
                insights.append(f'    较上年末{fd_d}{abs(fd_chg):.2f}个百分点')

    # ── 2. 收入结构 ──
    rev_total = get_val(raw, 'MA_A1_0', 'MA_YTD_BAL', me)
    nii       = get_val(raw, 'MA_A11_0', 'MA_YTD_BAL', me)
    fee       = get_val(raw, 'MA_A12_0', 'MA_YTD_BAL', me)
    tsy       = get_val(raw, 'MA_A13_0', 'MA_YTD_BAL', me)
    rev_total_ly = get_val(raw, 'MA_A1_0', 'MA_L_Y_YTD_BAL', me)
    nii_ly    = get_val(raw, 'MA_A11_0', 'MA_L_Y_YTD_BAL', me)
    fee_ly    = get_val(raw, 'MA_A12_0', 'MA_L_Y_YTD_BAL', me)
    tsy_ly    = get_val(raw, 'MA_A13_0', 'MA_L_Y_YTD_BAL', me)

    if rev_total and rev_total != 0:
        insights.append('【收入结构】')
        for val, val_ly, label in [(nii, nii_ly, '净利息收入'), (fee, fee_ly, '中间业务净收入'), (tsy, tsy_ly, '财资业务净收入')]:
            if val is not None:
                pct = val / rev_total * 100
                line = f'  {label}占比：{pct:.2f}%'
                if rev_total_ly and rev_total_ly != 0 and val_ly is not None:
                    pct_ly = val_ly / rev_total_ly * 100
                    chg = pct - pct_ly
                    line += f'（去年同期{pct_ly:.2f}%，{"上升" if chg > 0 else "下降"}{abs(chg):.2f}个百分点）'
                insights.append(line)

    # ── 3. 收入变动分解 ──
    rev_yoy_inc = get_val(raw, 'MA_A1_0', 'MA_YOY_INCREMENT', me)
    nii_yoy_inc = get_val(raw, 'MA_A11_0', 'MA_YOY_INCREMENT', me)
    fee_yoy_inc = get_val(raw, 'MA_A12_0', 'MA_YOY_INCREMENT', me)
    tsy_yoy_inc = get_val(raw, 'MA_A13_0', 'MA_YOY_INCREMENT', me)
    if rev_yoy_inc is not None and rev_yoy_inc != 0:
        insights.append('【收入变动分解（同比增量拆分）】')
        insights.append(f'  营业净收入同比变动：{fmt_hkd_sign(rev_yoy_inc)}')
        contribs = []
        for inc, label in [(nii_yoy_inc, '净利息收入'), (fee_yoy_inc, '中间业务净收入'), (tsy_yoy_inc, '财资业务净收入')]:
            if inc is not None:
                contribs.append(f'{label}贡献{fmt_hkd_sign(inc)}')
        if contribs:
            insights.append(f'  分解：{"，".join(contribs)}')

    # ── 4. 贷款集中度 ──
    normal = get_val(raw, 'MA_M111_0', 'MA_BAL', me)
    if normal and normal != 0:
        loan_types = []
        for i in range(1, 15):
            lc = f'MA_M111_{i}'
            v = get_val(raw, lc, 'MA_BAL', me)
            if v and v != 0:
                nm = asset_prefix.get(lc, lc)
                loan_types.append((nm, v / normal * 100, v))
        if loan_types:
            loan_types.sort(key=lambda x: -abs(x[1]))
            top3 = loan_types[:3]
            insights.append('【贷款集中度】前三大品种：')
            for nm, sh, _ in top3:
                insights.append(f'  {nm}占比{sh:.2f}%')
            if top3[0][1] > 50:
                insights.append(f'  风险提示：{top3[0][0]}占比超50%，集中度偏高')

    # ── 5. 不良贷款 ──
    total_loan = get_val(raw, 'MA_M11_0', 'MA_BAL', me)
    npl        = get_val(raw, 'MA_M112_1', 'MA_BAL', me)
    if total_loan and total_loan != 0 and npl is not None and npl != 0:
        npl_ratio = npl / total_loan * 100
        insights.append(f'【不良贷款占比】{npl_ratio:.2f}%')
        npl_ly = get_val(raw, 'MA_M112_1', 'MA_L_YE_BAL', me)
        loan_ly = get_val(raw, 'MA_M11_0', 'MA_L_YE_BAL', me)
        if npl_ly is not None and loan_ly and loan_ly != 0:
            npl_ratio_ly = npl_ly / loan_ly * 100
            chg = npl_ratio - npl_ratio_ly
            d = '上升' if chg > 0 else '下降'
            insights.append(f'  └ 较上年末（{npl_ratio_ly:.2f}%）{d}{abs(chg):.2f}个百分点')

    # ── 6. 拨备覆盖率 ──
    provision = get_val(raw, 'MA_M13_0', 'MA_BAL', me)
    if provision is not None and npl and npl != 0:
        cov = abs(provision) / npl * 100
        insights.append(f'【拨备/不良】拨备余额{fmt_hkd(provision)}，覆盖率约{cov:.2f}%')

    return '\n'.join(insights) if insights else '（结构数据不足）'

# ═══════════════════════════════════════════════════════════════════
# 整体经营概览
# ═══════════════════════════════════════════════════════════════════

def build_overview_context(raw, dd, is_me):
    me = dd['ME'].strftime('%Y%m%d')
    items = []

    items.append('【盈利概览】')
    for code, label in [
        ('MA_A1_0', '营业净收入'), ('MA_D1_0', '拨备前利润'),
        ('MA_E1_0', '资产减值（损失）/回拨'), ('MA_F1_0', '拨备后利润')
    ]:
        ytd = get_val(raw, code, 'MA_YTD_BAL', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        yoy_inc = get_val(raw, code, 'MA_YOY_INCREMENT', me)
        mom_g = get_val(raw, code, 'MA_MOM_GROWTH', me)
        if ytd is not None:
            line = f'  {label}：年累计{fmt_hkd(ytd)}'
            if yoy_g is not None:
                line += f'，同比{dir_word(yoy_g)}{pct_str(yoy_g)}'
            if yoy_inc is not None:
                line += f'（变动{fmt_hkd_sign(yoy_inc)}）'
            if mom_g is not None:
                line += f'，当月环比{dir_word(mom_g)}{pct_str(mom_g)}'
            items.append(line)

    items.append('【收入板块拆分】')
    rev_total = get_val(raw, 'MA_A1_0', 'MA_YTD_BAL', me)
    for code, label in [
        ('MA_A11_0', '净利息收入'), ('MA_A12_0', '中间业务净收入'),
        ('MA_A13_0', '财资业务净收入')
    ]:
        ytd = get_val(raw, code, 'MA_YTD_BAL', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        if ytd is not None:
            share = f'（占营收{ytd / rev_total * 100:.1f}%）' if rev_total and rev_total != 0 else ''
            yoy_str = f'，同比{dir_word(yoy_g)}{pct_str(yoy_g)}' if yoy_g is not None else ''
            items.append(f'  {label}：年累计{fmt_hkd(ytd)}{share}{yoy_str}')

    items.append('【资产概览】')
    for code, label in [
        ('MA_M1_0', '总资产'), ('MA_M11_0', '贷款'), ('MA_M12_0', '债券投资'),
        ('MA_M14_0', '存拆同业')
    ]:
        bal = get_val(raw, code, 'MA_BAL', me)
        lye_g = get_val(raw, code, 'MA_L_YE_GROWTH', me)
        lye_inc = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        if bal is not None and bal != 0:
            line = f'  {label}：时点余额{fmt_hkd(bal)}'
            if lye_g is not None:
                line += f'，较上年末{dir_word(lye_g)}{pct_str(lye_g)}'
            if lye_inc is not None:
                line += f'（增量{fmt_hkd_sign(lye_inc)}）'
            if yoy_g is not None:
                line += f'，年日均同比{dir_word(yoy_g)}{pct_str(yoy_g)}'
            items.append(line)

    items.append('【负债概览】')
    for code, label in [
        ('MA_N1_0', '总负债'), ('MA_N11_0', '客户存款'), ('MA_N111_0', '低息存款'),
        ('MA_N112_1', '定期存款')
    ]:
        bal = get_val(raw, code, 'MA_BAL', me)
        lye_g = get_val(raw, code, 'MA_L_YE_GROWTH', me)
        lye_inc = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        if bal is not None and bal != 0:
            line = f'  {label}：时点余额{fmt_hkd(bal)}'
            if lye_g is not None:
                line += f'，较上年末{dir_word(lye_g)}{pct_str(lye_g)}'
            if lye_inc is not None:
                line += f'（增量{fmt_hkd_sign(lye_inc)}）'
            if yoy_g is not None:
                line += f'，年日均同比{dir_word(yoy_g)}{pct_str(yoy_g)}'
            items.append(line)

    return '\n'.join(items)

# ═══════════════════════════════════════════════════════════════════
# 叙事草稿（预填充结构化分析文本，LLM只需润色）
# ═══════════════════════════════════════════════════════════════════

def _line_if(label, val, yoy_g=None, yoy_inc=None, mom_g=None, mom_inc=None,
             lye_g=None, lye_inc=None, ref_val=None, ref_label=None, share_pct=None):
    if val is None:
        return None
    parts = [f'{label}为{fmt_hkd(val)}']
    if share_pct is not None:
        parts.append(f'占比{share_pct:.2f}%')
    if lye_g is not None:
        seg = f'较上年末{dir_word(lye_g)}{pct_str(lye_g)}'
        if lye_inc is not None:
            seg += f'（变动{fmt_hkd_sign(lye_inc)}）'
        parts.append(seg)
    if yoy_g is not None:
        seg = f'同比{dir_word(yoy_g)}{pct_str(yoy_g)}'
        if yoy_inc is not None:
            seg += f'（变动{fmt_hkd_sign(yoy_inc)}）'
        parts.append(seg)
    if mom_g is not None:
        seg = f'环比{dir_word(mom_g)}{pct_str(mom_g)}'
        if mom_inc is not None:
            seg += f'（变动{fmt_hkd_sign(mom_inc)}）'
        parts.append(seg)
    if ref_val is not None and ref_label:
        parts.append(f'{ref_label}{fmt_hkd(ref_val)}')
    return '，'.join(parts)

def build_narrative_draft(raw, dd, asset_prefix, liab_prefix, revenue_prefix, oic_name, me_display):
    me = dd['ME'].strftime('%Y%m%d')
    sections = []

    # ════════ 总体概述 ════════
    rev_total = get_val(raw, 'MA_A1_0', 'MA_YTD_BAL', me)
    rev_yoy_g = get_val(raw, 'MA_A1_0', 'MA_YOY_GROWTH', me)
    preprov = get_val(raw, 'MA_D1_0', 'MA_YTD_BAL', me)
    preprov_yoy_g = get_val(raw, 'MA_D1_0', 'MA_YOY_GROWTH', me)
    postprov = get_val(raw, 'MA_F1_0', 'MA_YTD_BAL', me)
    postprov_yoy_g = get_val(raw, 'MA_F1_0', 'MA_YOY_GROWTH', me)
    total_asset = get_val(raw, 'MA_M1_0', 'MA_BAL', me)
    total_asset_lye_g = get_val(raw, 'MA_M1_0', 'MA_L_YE_GROWTH', me)
    total_dep = get_val(raw, 'MA_N11_0', 'MA_BAL', me)
    total_dep_lye_g = get_val(raw, 'MA_N11_0', 'MA_L_YE_GROWTH', me)
    total_loan = get_val(raw, 'MA_M11_0', 'MA_BAL', me)
    total_loan_lye_g = get_val(raw, 'MA_M11_0', 'MA_L_YE_GROWTH', me)

    overview_parts = [f'截至{me_display}']
    if rev_total is not None:
        seg = f'该客户经理实现营业净收入{fmt_hkd(rev_total)}'
        if rev_yoy_g is not None:
            seg += f'，同比{dir_word(rev_yoy_g)}{pct_str(rev_yoy_g)}'
        overview_parts.append(seg)
    if preprov is not None:
        seg = f'拨备前利润{fmt_hkd(preprov)}'
        if preprov_yoy_g is not None:
            seg += f'，同比{dir_word(preprov_yoy_g)}{pct_str(preprov_yoy_g)}'
        overview_parts.append(seg)
    if total_asset is not None:
        seg = f'管户总资产时点余额{fmt_hkd(total_asset)}'
        if total_asset_lye_g is not None:
            seg += f'，较上年末{dir_word(total_asset_lye_g)}{pct_str(total_asset_lye_g)}'
        overview_parts.append(seg)
    if total_dep is not None:
        seg = f'客户存款时点余额{fmt_hkd(total_dep)}'
        if total_dep_lye_g is not None:
            seg += f'，较上年末{dir_word(total_dep_lye_g)}{pct_str(total_dep_lye_g)}'
        overview_parts.append(seg)

    sections.append('§总体概述§')
    sections.append('；'.join(overview_parts) + '。')

    # ════════ 盈利能力分析 ════════
    sections.append('')
    sections.append('§盈利能力分析§')

    rev_yoy_inc = get_val(raw, 'MA_A1_0', 'MA_YOY_INCREMENT', me)
    rev_mom_g = get_val(raw, 'MA_A1_0', 'MA_MOM_GROWTH', me)
    rev_line = _line_if('营业净收入年累计', rev_total, yoy_g=rev_yoy_g, yoy_inc=rev_yoy_inc, mom_g=rev_mom_g)
    if rev_line:
        sections.append(rev_line + '。')

    for code, label in [('MA_A11_0', '净利息收入'), ('MA_A12_0', '中间业务净收入'), ('MA_A13_0', '财资业务净收入')]:
        ytd = get_val(raw, code, 'MA_YTD_BAL', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        yoy_inc = get_val(raw, code, 'MA_YOY_INCREMENT', me)
        mom_g = get_val(raw, code, 'MA_MOM_GROWTH', me)
        share = (ytd / rev_total * 100) if (ytd is not None and rev_total and rev_total != 0) else None
        line = _line_if(f'{label}年累计', ytd, yoy_g=yoy_g, yoy_inc=yoy_inc, mom_g=mom_g, share_pct=share)
        if line:
            sections.append(f'  {line}。')
            if code == 'MA_A11_0':
                for sub_code, sub_label in [('MA_A111_0', '贷款净利息收入'), ('MA_A113_0', '存拆同业净利息收入'),
                                             ('MA_A114_0', '客户存款净利息收入'), ('MA_A115_1', '发行存款证利息支出'),
                                             ('MA_A117_0', '同业存拆利息支出')]:
                    sv = get_val(raw, sub_code, 'MA_YTD_BAL', me)
                    sg = get_val(raw, sub_code, 'MA_YOY_GROWTH', me)
                    si = get_val(raw, sub_code, 'MA_YOY_INCREMENT', me)
                    sm = get_val(raw, sub_code, 'MA_MOM_GROWTH', me)
                    if sv is not None and sv != 0:
                        sl = _line_if(f'    {sub_label}', sv, yoy_g=sg, yoy_inc=si, mom_g=sm)
                        if sl:
                            sections.append(sl)
            if code == 'MA_A12_0':
                for sub_code, sub_label in [('MA_A12_1', '收费及佣金收入'), ('MA_A12_2', '收费及佣金支出')]:
                    sv = get_val(raw, sub_code, 'MA_YTD_BAL', me)
                    sg = get_val(raw, sub_code, 'MA_YOY_GROWTH', me)
                    si = get_val(raw, sub_code, 'MA_YOY_INCREMENT', me)
                    if sv is not None and sv != 0:
                        sl = _line_if(f'    {sub_label}', sv, yoy_g=sg, yoy_inc=si)
                        if sl:
                            sections.append(sl)
            if code == 'MA_A13_0':
                for sub_code, sub_label in [('MA_A13_1', '交易业务净收入'), ('MA_A13_2', '以FVPL入账金融资产及负债之净收益')]:
                    sv = get_val(raw, sub_code, 'MA_YTD_BAL', me)
                    sg = get_val(raw, sub_code, 'MA_YOY_GROWTH', me)
                    si = get_val(raw, sub_code, 'MA_YOY_INCREMENT', me)
                    if sv is not None and sv != 0:
                        sl = _line_if(f'    {sub_label}', sv, yoy_g=sg, yoy_inc=si)
                        if sl:
                            sections.append(sl)

    prov = get_val(raw, 'MA_E1_0', 'MA_YTD_BAL', me)
    prov_yoy_g = get_val(raw, 'MA_E1_0', 'MA_YOY_GROWTH', me)
    prov_yoy_inc = get_val(raw, 'MA_E1_0', 'MA_YOY_INCREMENT', me)
    prov_mom_g = get_val(raw, 'MA_E1_0', 'MA_MOM_GROWTH', me)
    if prov is not None:
        prov_line = _line_if('资产减值（损失）/回拨年累计', prov, yoy_g=prov_yoy_g, yoy_inc=prov_yoy_inc, mom_g=prov_mom_g)
        if prov_line:
            sections.append(f'  {prov_line}。')
        for sub_code, sub_label in [('MA_E1_1', '个别计提'), ('MA_E1_2', '组合计提'), ('MA_E1_3', '回拨')]:
            sv = get_val(raw, sub_code, 'MA_YTD_BAL', me)
            sg = get_val(raw, sub_code, 'MA_YOY_GROWTH', me)
            if sv is not None and sv != 0:
                sl = _line_if(f'    {sub_label}', sv, yoy_g=sg)
                if sl:
                    sections.append(sl)

    postprov_yoy_inc = get_val(raw, 'MA_F1_0', 'MA_YOY_INCREMENT', me)
    postprov_mom_g = get_val(raw, 'MA_F1_0', 'MA_MOM_GROWTH', me)
    pp_line = _line_if('拨备后利润年累计', postprov, yoy_g=postprov_yoy_g, yoy_inc=postprov_yoy_inc, mom_g=postprov_mom_g)
    if pp_line:
        sections.append(f'  {pp_line}。')

    # ════════ 资产端分析 ════════
    sections.append('')
    sections.append('§资产端分析§')

    for code, label in [('MA_M1_0', '总资产'), ('MA_M11_0', '贷款'), ('MA_M111_0', '正常贷款'),
                        ('MA_M112_1', '不良贷款'), ('MA_M12_0', '债券投资'), ('MA_M13_0', '拨备余额'),
                        ('MA_M14_0', '存拆同业')]:
        bal = get_val(raw, code, 'MA_BAL', me)
        lye_g = get_val(raw, code, 'MA_L_YE_GROWTH', me)
        lye_inc = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        yoy_inc = get_val(raw, code, 'MA_YOY_INCREMENT', me)
        mom_g = get_val(raw, code, 'MA_MOM_GROWTH', me)
        mom_inc = get_val(raw, code, 'MA_MOM_INCREMENT', me)
        if bal is not None and bal != 0:
            line = _line_if(f'{label}时点余额', bal, yoy_g=yoy_g, yoy_inc=yoy_inc,
                           mom_g=mom_g, mom_inc=mom_inc, lye_g=lye_g, lye_inc=lye_inc)
            if line:
                sections.append(line + '。')

    normal = get_val(raw, 'MA_M111_0', 'MA_BAL', me)
    if normal and normal != 0:
        sub_lines = []
        for i in range(1, 15):
            lc = f'MA_M111_{i}'
            v = get_val(raw, lc, 'MA_BAL', me)
            lg = get_val(raw, lc, 'MA_L_YE_GROWTH', me)
            li = get_val(raw, lc, 'MA_L_YE_INCREMENT', me)
            mg = get_val(raw, lc, 'MA_MOM_GROWTH', me)
            if v and v != 0:
                nm = asset_prefix.get(lc, lc)
                share = v / normal * 100
                sl = _line_if(f'  {nm}', v, lye_g=lg, lye_inc=li, mom_g=mg, share_pct=share)
                if sl:
                    sub_lines.append(sl)
        if sub_lines:
            sections.append('  贷款明细：')
            sections.extend(sub_lines)

    # 债券细项
    bond_total = get_val(raw, 'MA_M12_0', 'MA_BAL', me)
    if bond_total and bond_total != 0:
        sub_lines = []
        for code, label in [('MA_M12_1', 'AC债券投资'), ('MA_M12_2', 'FVOCI债券投资'),
                             ('MA_M12_3', '指定FVPL债券投资'), ('MA_M12_4', 'FVTPL债券投资'),
                             ('MA_M12_5', '交易性债券投资')]:
            v = get_val(raw, code, 'MA_BAL', me)
            lg = get_val(raw, code, 'MA_L_YE_GROWTH', me)
            if v and v != 0:
                share = v / bond_total * 100
                sl = _line_if(f'  {label}', v, lye_g=lg, share_pct=share)
                if sl:
                    sub_lines.append(sl)
        if sub_lines:
            sections.append('  债券投资明细：')
            sections.extend(sub_lines)

    # ════════ 负债端分析 ════════
    sections.append('')
    sections.append('§负债端分析§')

    for code, label in [('MA_N1_0', '总负债'), ('MA_N11_0', '客户存款'), ('MA_N111_0', '低息存款'),
                        ('MA_N112_1', '定期存款'), ('MA_N12_1', '发行存款证'), ('MA_N13_0', '发行债券'),
                        ('MA_N14_0', '同业存放')]:
        bal = get_val(raw, code, 'MA_BAL', me)
        lye_g = get_val(raw, code, 'MA_L_YE_GROWTH', me)
        lye_inc = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
        yoy_g = get_val(raw, code, 'MA_YOY_GROWTH', me)
        yoy_inc = get_val(raw, code, 'MA_YOY_INCREMENT', me)
        mom_g = get_val(raw, code, 'MA_MOM_GROWTH', me)
        if bal is not None and bal != 0:
            line = _line_if(f'{label}时点余额', bal, yoy_g=yoy_g, yoy_inc=yoy_inc,
                           mom_g=mom_g, lye_g=lye_g, lye_inc=lye_inc)
            if line:
                sections.append(line + '。')

    dep_total = get_val(raw, 'MA_N11_0', 'MA_BAL', me)
    if dep_total and dep_total != 0:
        sub_lines = []
        for code, label in [('MA_N1111_0', '活期存款'), ('MA_N1111_1', '活期存款-非员工'),
                             ('MA_N1111_2', '活期存款-员工'), ('MA_N111_2', '储蓄存款')]:
            v = get_val(raw, code, 'MA_BAL', me)
            lg = get_val(raw, code, 'MA_L_YE_GROWTH', me)
            li = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
            if v and v != 0:
                share = v / dep_total * 100
                sl = _line_if(f'  {label}', v, lye_g=lg, lye_inc=li, share_pct=share)
                if sl:
                    sub_lines.append(sl)
        if sub_lines:
            sections.append('  存款结构明细：')
            sections.extend(sub_lines)

    # 发行债券细项
    bond_liab = get_val(raw, 'MA_N13_0', 'MA_BAL', me)
    if bond_liab and bond_liab != 0:
        sub_lines = []
        for code, label in [('MA_N13_1', '发行其他债券'), ('MA_N13_2', '发行后偿债券'),
                             ('MA_N13_3', '发行CLN'), ('MA_N13_4', '发行ELN')]:
            v = get_val(raw, code, 'MA_BAL', me)
            lg = get_val(raw, code, 'MA_L_YE_GROWTH', me)
            if v and v != 0:
                sl = _line_if(f'  {label}', v, lye_g=lg)
                if sl:
                    sub_lines.append(sl)
        if sub_lines:
            sections.append('  发行债券明细：')
            sections.extend(sub_lines)

    # 同业存放细项
    interbank = get_val(raw, 'MA_N14_0', 'MA_BAL', me)
    if interbank and interbank != 0:
        sub_lines = []
        for code, label in [('MA_N14_1', '同业存放'), ('MA_N14_2', '同业存拆'), ('MA_N14_3', 'REPO')]:
            v = get_val(raw, code, 'MA_BAL', me)
            lg = get_val(raw, code, 'MA_L_YE_GROWTH', me)
            if v and v != 0:
                sl = _line_if(f'  {label}', v, lye_g=lg)
                if sl:
                    sub_lines.append(sl)
        if sub_lines:
            sections.append('  同业存放明细：')
            sections.extend(sub_lines)

    return '\n'.join(sections)

# ═══════════════════════════════════════════════════════════════════
# 【新增】信号汇总（合并资负+损益所有信号）
# ═══════════════════════════════════════════════════════════════════

def build_signals_summary(asset_hl, asset_cn, liab_hl, liab_cn, rev_hl, rev_cn):
    lines = []
    lines.append('▎突出表现（建议在报告中重点提及）')
    for src, txt in [('资产端', asset_hl), ('负债端', liab_hl), ('损益端', rev_hl)]:
        if '暂无' not in txt:
            lines.append(f'  [{src}]')
            lines.append(f'  {txt}')
    if all('暂无' in t for t in [asset_hl, liab_hl, rev_hl]):
        lines.append('  （各维度暂无显著突出表现）')

    lines.append('')
    lines.append('▎待关注项（建议在"下一步建议"中体现）')
    for src, txt in [('资产端', asset_cn), ('负债端', liab_cn), ('损益端', rev_cn)]:
        if '暂无' not in txt:
            lines.append(f'  [{src}]')
            lines.append(f'  {txt}')
    if all('暂无' in t for t in [asset_cn, liab_cn, rev_cn]):
        lines.append('  （各维度暂无显著待关注项）')

    return '\n'.join(lines)

# ═══════════════════════════════════════════════════════════════════
# 管理视角诊断素材（v8：把关注点前置为“信号-影响-动作”）
# ═══════════════════════════════════════════════════════════════════

def _risk_level(rate):
    if rate is None:
        return '观察'
    ar = abs(rate)
    if ar >= 0.20:
        return '重点关注'
    if ar >= 0.10:
        return '关注'
    return '观察'

def _append_metric_signal(lines, raw, me, code, label, metric, basis, dimension, good_when_up=True):
    rate = get_val(raw, code, metric, me)
    inc = None
    if metric == 'MA_YOY_GROWTH':
        inc = get_val(raw, code, 'MA_YOY_INCREMENT', me)
    elif metric == 'MA_MOM_GROWTH':
        inc = get_val(raw, code, 'MA_MOM_INCREMENT', me)
    elif metric == 'MA_L_YE_GROWTH':
        inc = get_val(raw, code, 'MA_L_YE_INCREMENT', me)
    if rate is None or abs(rate) < 0.08:
        return

    direction = dir_word(rate)
    level = _risk_level(rate)
    tone = '正向拉动' if ((rate > 0 and good_when_up) or (rate < 0 and not good_when_up)) else '承压因素'
    inc_txt = f'，增量{fmt_hkd_sign(inc)}' if inc is not None else ''
    lines.append(
        f'【{level}｜{dimension}】{label}{basis}{direction}{pct_str(rate)}{inc_txt}，'
        f'可作为本期{tone}展开。'
    )

def build_management_diagnosis(raw, dd):
    me = dd['ME'].strftime('%Y%m%d')
    lines = []

    _append_metric_signal(lines, raw, me, 'MA_A1_0', '营业净收入', 'MA_YOY_GROWTH', '累计同比', '收益')
    _append_metric_signal(lines, raw, me, 'MA_A11_0', '净利息收入', 'MA_YOY_GROWTH', '累计同比', '收益')
    _append_metric_signal(lines, raw, me, 'MA_A12_0', '中间业务净收入', 'MA_YOY_GROWTH', '累计同比', '收益')
    _append_metric_signal(lines, raw, me, 'MA_F1_0', '拨备后利润', 'MA_YOY_GROWTH', '累计同比', '收益')
    _append_metric_signal(lines, raw, me, 'MA_M11_0', '贷款时点余额', 'MA_L_YE_GROWTH', '较上年末', '规模')
    _append_metric_signal(lines, raw, me, 'MA_N11_0', '客户存款时点余额', 'MA_L_YE_GROWTH', '较上年末', '规模')
    _append_metric_signal(lines, raw, me, 'MA_N111_0', '低息存款时点余额', 'MA_L_YE_GROWTH', '较上年末', '结构')
    _append_metric_signal(lines, raw, me, 'MA_N112_1', '定期存款时点余额', 'MA_L_YE_GROWTH', '较上年末', '结构', good_when_up=False)
    _append_metric_signal(lines, raw, me, 'MA_M112_1', '不良贷款时点余额', 'MA_L_YE_GROWTH', '较上年末', '风险', good_when_up=False)

    rev_total = get_val(raw, 'MA_A1_0', 'MA_YTD_BAL', me)
    nii = get_val(raw, 'MA_A11_0', 'MA_YTD_BAL', me)
    fee = get_val(raw, 'MA_A12_0', 'MA_YTD_BAL', me)
    tsy = get_val(raw, 'MA_A13_0', 'MA_YTD_BAL', me)
    if rev_total and rev_total != 0:
        parts = []
        for val, label in [(nii, '净利息收入'), (fee, '中间业务净收入'), (tsy, '财资业务净收入')]:
            if val is not None and val != 0:
                parts.append(f'{label}占比{val / rev_total * 100:.2f}%')
        if parts:
            lines.append(f'【结构｜收益】收入结构为{"、".join(parts)}，报告中应说明主导收入来源及结构均衡度。')

    dep_total = get_val(raw, 'MA_N11_0', 'MA_BAL', me)
    low_int = get_val(raw, 'MA_N111_0', 'MA_BAL', me)
    fixed_dep = get_val(raw, 'MA_N112_1', 'MA_BAL', me)
    if dep_total and dep_total != 0:
        parts = []
        if low_int is not None:
            parts.append(f'低息存款占客户存款{low_int / dep_total * 100:.2f}%')
        if fixed_dep is not None:
            parts.append(f'定期存款占客户存款{fixed_dep / dep_total * 100:.2f}%')
        if parts:
            lines.append(f'【结构｜负债】{"，".join(parts)}，需结合资金成本和稳定性评价负债质量。')

    if not lines:
        lines.append('【观察】未识别到显著异动，报告可侧重总体稳健性、结构均衡性和后续持续跟踪事项。')
    return '\n'.join(lines)

# ═══════════════════════════════════════════════════════════════════
# 【新增】建议候选草稿（规则生成，供LLM选用）
# ═══════════════════════════════════════════════════════════════════

def build_suggestion_candidates(raw, dd, asset_prefix):
    me = dd['ME'].strftime('%Y%m%d')
    sugs = []

    # ── 存款结构 ──
    dep_total = get_val(raw, 'MA_N11_0', 'MA_BAL', me)
    low_int   = get_val(raw, 'MA_N111_0', 'MA_BAL', me)
    low_lye_g = get_val(raw, 'MA_N111_0', 'MA_L_YE_GROWTH', me)
    fix_lye_g = get_val(raw, 'MA_N112_1', 'MA_L_YE_GROWTH', me)
    if dep_total and dep_total != 0 and low_int is not None:
        casa = low_int / dep_total * 100
        if casa < 40:
            sugs.append(f'低息存款占客户存款{casa:.2f}%，负债成本优化空间较大，建议围绕结算沉淀、代发代扣和重点客群维护提升低成本资金留存')
        if low_lye_g is not None and low_lye_g < 0:
            sugs.append(f'低息存款较上年末下降{pct_str(low_lye_g)}，建议排查重点客户资金流出、到期转存及结算活跃度变化，优先稳住核心结算户')
        if fix_lye_g is not None and fix_lye_g > 0.2:
            sugs.append(f'定期存款较上年末增长{pct_str(fix_lye_g)}，建议同步关注付息成本和到期分布，避免规模增长对净利息收入形成挤压')

    # ── 贷款集中度 ──
    normal = get_val(raw, 'MA_M111_0', 'MA_BAL', me)
    if normal and normal != 0:
        loan_types = []
        for i in range(1, 15):
            lc = f'MA_M111_{i}'
            v = get_val(raw, lc, 'MA_BAL', me)
            if v and v != 0:
                nm = asset_prefix.get(lc, lc)
                loan_types.append((nm, v / normal * 100))
        if loan_types:
            loan_types.sort(key=lambda x: -x[1])
            if loan_types[0][1] > 50:
                sugs.append(f'{loan_types[0][0]}占正常贷款{loan_types[0][1]:.2f}%，贷款结构集中度偏高，建议结合客户行业、抵质押和期限结构进一步下钻')

    # ── 贷款增长 ──
    loan_lye_g = get_val(raw, 'MA_M11_0', 'MA_L_YE_GROWTH', me)
    if loan_lye_g is not None and loan_lye_g < 0:
        sugs.append(f'贷款余额较上年末下降{pct_str(loan_lye_g)}，建议梳理存量客户提款、还款和授信使用情况，优先推动优质客户授信转化')

    # ── 不良贷款 ──
    npl = get_val(raw, 'MA_M112_1', 'MA_BAL', me)
    npl_lye_g = get_val(raw, 'MA_M112_1', 'MA_L_YE_GROWTH', me)
    if npl and npl != 0 and npl_lye_g is not None and npl_lye_g > 0:
        sugs.append(f'不良贷款较上年末上升{pct_str(npl_lye_g)}，建议将风险客户列入重点跟踪清单，结合逾期、担保和还款来源推进分类管理')

    # ── 收入多元化 ──
    rev_total = get_val(raw, 'MA_A1_0', 'MA_YTD_BAL', me)
    nii       = get_val(raw, 'MA_A11_0', 'MA_YTD_BAL', me)
    fee       = get_val(raw, 'MA_A12_0', 'MA_YTD_BAL', me)
    if rev_total and rev_total != 0 and nii is not None:
        nii_pct = nii / rev_total * 100
        if nii_pct > 85:
            sugs.append(f'净利息收入占营业净收入{nii_pct:.2f}%，收入对息差业务依赖较高，建议围绕结算、代发、贸易金融及财富类场景提升非息贡献')
    if fee is not None:
        fee_yoy_g = get_val(raw, 'MA_A12_0', 'MA_YOY_GROWTH', me)
        if fee_yoy_g is not None and fee_yoy_g < -0.1:
            sugs.append(f'中间业务净收入累计同比下降{pct_str(fee_yoy_g)}，建议拆分收费及佣金来源，定位拖累产品并跟进客户渗透率')

    # ── 盈利趋势 ──
    rev_mom_g = get_val(raw, 'MA_A1_0', 'MA_MOM_GROWTH', me)
    if rev_mom_g is not None and rev_mom_g > 0.1:
        sugs.append(f'营业净收入当月环比增长{pct_str(rev_mom_g)}，建议复盘主要贡献客户和产品，将有效打法沉淀为后续拓展清单')
    if rev_mom_g is not None and rev_mom_g < -0.1:
        sugs.append(f'营业净收入当月环比下降{pct_str(rev_mom_g)}，建议优先核查净利息收入、中收和财资业务的环比拖累项')

    if not sugs:
        sugs.append('整体经营表现未见明显异常，建议保持规模、收益、结构和风险四类指标的月度跟踪，并结合重点客户开展机会挖掘')

    return '\n'.join(f'{i+1}. {s}' for i, s in enumerate(sugs))

# ═══════════════════════════════════════════════════════════════════
# 指标字典 & 映射字典
# ═══════════════════════════════════════════════════════════════════

revenue_key_prefix_dict = {
    "MA_A1_0":"一、营业净收入",
    "MA_A11_0":"（一）净利息收入",
    "MA_A111_0":"（1）贷款净利息收入",
    "MA_A111_1":"1.房产按揭贷款",
    "MA_A111_2":"2.房产按揭贷款 - 員工",
    "MA_A111_3":"3.个人贷款",
    "MA_A111_4":"4.税务贷款",
    "MA_A111_5":"5.透支",
    "MA_A111_6":"6.定期循环贷款",
    "MA_A111_7":"7.银团贷款",
    "MA_A111_8":"8.贸易融资",
    "MA_A111_9":"9.贸易融资 - CMB分润",
    "MA_A111_10":"10.支票贴现",
    "MA_A111_11":"11.租赁贷款",
    "MA_A111_12":"12.信用卡贷款",
    "MA_A111_13":"13.保理",
    "MA_A111_14":"14.新股认购/保证金贷款",
    "MA_A111_15":"15.其他贷款",
    "MA_A111_16":"16.不良贷款",
    "MA_A113_0":"（2）存拆同业净利息收入",
    "MA_A114_0":"（3）客户存款净利息收入",
    "MA_A1141_0":"1.低息存款",
    "MA_A11411_0":"a.活期存款",
    "MA_A11411_1":"i.活期存款 - 非员工",
    "MA_A11411_2":"ii.活期存款 - 员工",
    "MA_A1141_1":"b.储蓄存款",
    "MA_A115_1":"（4）发行存款证",
    "MA_A117_0":"（5）同业存拆利息支出",
    "MA_A12_0":"（二）中间业务净收入",
    "MA_A12_1":"其中：1.收费及佣金收入",
    "MA_A12_2":" 2.收费及佣金支出",
    "MA_A13_0":"（三）财资业务净收入",
    "MA_A13_1":"（1）交易业务净收入",
    "MA_A13_2":"（2）以FVPL入账金融资产及负债之净收益",
    "MA_D1_0":"二、拨备前利润",
    "MA_E1_0":"三、资产减值(损失)/回拨",
    "MA_E1_1":"（一）个别计提",
    "MA_E1_2":"（二）组合计提",
    "MA_E1_3":"（三）回拨",
    "MA_F1_0":"四、拨备后利润 (成本分摊前)"
}

asset_key_prefix_dict = {
    "MA_M1_0":"一、资产",
    "MA_M11_0":"（一）贷款",
    "MA_M111_0":"（1）正常贷款",
    "MA_M111_1":"1.房产按揭贷款",
    "MA_M111_2":"2.房产按揭贷款 - 员工",
    "MA_M111_3":"3.个人贷款",
    "MA_M111_4":"4.税务贷款",
    "MA_M111_5":"5.透支",
    "MA_M111_6":"6.定期循环贷款",
    "MA_M111_7":"7.银团贷款",
    "MA_M111_8":"8.贸易融资",
    "MA_M111_9":"9.支票贴现",
    "MA_M111_10":"10.租赁贷款",
    "MA_M111_11":"11.信用卡贷款",
    "MA_M111_12":"12.保理",
    "MA_M111_13":"13.新股认购/保证金贷款",
    "MA_M111_14":"14.其他贷款",
    "MA_M112_1":"（2）不良贷款",
    "MA_M12_0":"（二）债券投资",
    "MA_M12_1":"（1）AC债券投资",
    "MA_M12_2":"（2）FVOCI债券投资",
    "MA_M12_3":"（3）指定FVPL债券投资",
    "MA_M12_4":"（4）FVTPL债券投资",
    "MA_M12_5":"（5）交易性债券投资",
    "MA_M13_0":"（三）拨备余额",
    "MA_M13_1":"（1）组合",
    "MA_M13_2":"（2）个别",
    "MA_M14_0":"（四）存拆同业",
    "MA_M14_1":"（1）存放同业",
    "MA_M14_2":"（2）存拆同业",
    "MA_M14_3":"（3）REVERSE REPO"
}

liab_key_prefix_dict = {
    "MA_N1_0":"二、负债",
    "MA_N11_0":"（一）客户存款",
    "MA_N111_0":"（1）低息存款",
    "MA_N1111_0":"1.活期存款",
    "MA_N1111_1":"a.活期存款 - 非员工",
    "MA_N1111_2":"b.活期存款 - 员工",
    "MA_N111_2":"2.储蓄存款",
    "MA_N112_1":"（2）定期存款",
    "MA_N12_1":"（二）发行存款证",
    "MA_N13_0":"（三）发行债券",
    "MA_N13_1":"（1）发行其他债券",
    "MA_N13_2":"（2）发行后偿债券",
    "MA_N13_3":"（3）发行CLN",
    "MA_N13_4":"（4）发行ELN",
    "MA_N14_0":"（四）同业存放",
    "MA_N14_1":"（1）同业存放",
    "MA_N14_2":"（2）同业存拆",
    "MA_N14_3":"（3）REPO"
}

revenue_bd_mapping_dict = {
    'MA_MTD_BAL-BD':'MTD_月累计_BD',
    'MA_YTD_BAL-BD':'YTD_年累计_BD'
}
revenue_me_mapping_dict = {
    'MA_MTD_BAL-ME':'MTD_月累计_ME',
    'MA_YTD_BAL-ME':'YTD_年累计_ME',
    'MA_L_Y_MTD_BAL-ME':'MTD_月累计_LYME',
    'MA_L_Y_YTD_BAL-ME':'YTD_年累计_LYME',
    'MA_L_M_MTD_BAL-ME':'MTD_月累计_LME',
    'MA_YOY_INCREMENT-ME':'YTD_同比增量_ME',
    'MA_YOY_GROWTH-ME':'YTD_同比增幅_ME',
    'MA_MOM_INCREMENT-ME':'MTD_环比增量_ME',
    'MA_MOM_GROWTH-ME':'MTD_环比增幅_ME'
}
asset_and_liab_bd_mapping_dict = {
    'MA_BAL-BD':'BAL_月时点余额_BD',
    'MA_MTD_BAL-BD':'MTD_月日均余额_BD',
    'MA_YTD_BAL-BD':'YTD_年日均余额_BD'
}
asset_and_liab_me_mapping_dict = {
    'MA_BAL-ME':'BAL_月时点余额_ME',
    'MA_MTD_BAL-ME':'MTD_月日均余额_ME',
    'MA_YTD_BAL-ME':'YTD_年日均余额_ME',
    'MA_L_Y_MTD_BAL-ME':'MTD_月日均余额_LYME',
    'MA_L_Y_YTD_BAL-ME':'YTD_年日均余额_LYME',
    'MA_L_M_BAL-ME':'BAL_月时点余额_LME',
    'MA_L_YE_BAL-ME':'BAL_月时点余额_LYYE',
    'MA_YOY_INCREMENT-ME':'YTD_同比增量_ME',
    'MA_YOY_GROWTH-ME':'YTD_同比增幅_ME',
    'MA_MOM_INCREMENT-ME':'BAL_环比增量_ME',
    'MA_MOM_GROWTH-ME':'BAL_环比增幅_ME',
    'MA_L_YE_INCREMENT-ME':'BAL_较上年末增量_ME',
    'MA_L_YE_GROWTH-ME':'BAL_较上年末增幅_ME'
}

# ═══════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════

def main(args: dict) -> dict:
    input_json_str = args.get('data_dict')
    input_json_obj = json.loads(input_json_str)

    batchDate = datetime.datetime.strptime(input_json_obj['batchDate'], '%Y-%m-%d').date()
    is_month_end = check_month_end(batchDate)
    monthEnd = batchDate if is_month_end else datetime.datetime.strptime(
        input_json_obj['lastMonthLastDate'], '%Y-%m-%d'
    ).date()

    date_dict = {
        "BD":   batchDate,
        "ME":   monthEnd,
        "LYME": datetime.date(monthEnd.year - 1, monthEnd.month,
                              min(monthEnd.day, calendar.monthrange(monthEnd.year - 1, monthEnd.month)[1])),
        "LME":  datetime.date(monthEnd.year, monthEnd.month, 1) - datetime.timedelta(days=1),
        "LYYE": datetime.date(monthEnd.year - 1, 12, 31)
    }

    me_display = monthEnd.strftime('%Y年%m月%d日')

    rev_map = revenue_me_mapping_dict if is_month_end else {**revenue_bd_mapping_dict, **revenue_me_mapping_dict}
    al_map  = asset_and_liab_me_mapping_dict if is_month_end else {**asset_and_liab_bd_mapping_dict, **asset_and_liab_me_mapping_dict}

    revenue_info = extract_data_from_json(revenue_key_prefix_dict, rev_map, date_dict, input_json_obj)
    asset_info   = extract_data_from_json(asset_key_prefix_dict,   al_map, date_dict, input_json_obj)
    liab_info    = extract_data_from_json(liab_key_prefix_dict,    al_map, date_dict, input_json_obj)

    # ── OIC ──
    oic_info_raw = extract_between_points(input_json_str, '"ZONENO', None)
    oic_info = json.loads("{" + oic_info_raw)
    oic_dict = {
        "业务线":       oic_info.get('LOB_CODE', ''),
        "网点号":       oic_info.get('AC_BK_BRNO', ''),
        "客户经理ID":   oic_info.get('OIC', ''),
        "客户经理名称": oic_info.get('OIC_NAME', '')
    }
    oic_name = oic_info.get('OIC_NAME', '未知')
    oic_id   = oic_info.get('OIC', '')

    # ── 预计算分析文本 ──
    rev_txt, rev_hl, rev_cn       = build_revenue_analysis(revenue_key_prefix_dict, input_json_obj, date_dict, is_month_end)
    asset_txt, asset_hl, asset_cn = build_al_analysis(asset_key_prefix_dict, input_json_obj, date_dict, '资产', is_month_end)
    liab_txt, liab_hl, liab_cn   = build_al_analysis(liab_key_prefix_dict, input_json_obj, date_dict, '负债', is_month_end)
    structural = build_structural_insights(input_json_obj, date_dict, asset_key_prefix_dict, liab_key_prefix_dict, revenue_key_prefix_dict)
    overview   = build_overview_context(input_json_obj, date_dict, is_month_end)
    narrative  = build_narrative_draft(input_json_obj, date_dict, asset_key_prefix_dict, liab_key_prefix_dict,
                                       revenue_key_prefix_dict, oic_name, me_display)
    signals    = build_signals_summary(asset_hl, asset_cn, liab_hl, liab_cn, rev_hl, rev_cn)
    management_diagnosis = build_management_diagnosis(input_json_obj, date_dict)
    suggestions = build_suggestion_candidates(input_json_obj, date_dict, asset_key_prefix_dict)

    # ── 组装Lead Integrator所需的完整上下文 ──
    al_context = (
        f'═══ 客户经理：{oic_name}（{oic_id}）| 数据截止：{me_display} ═══\n\n'
        f'▎资产端逐项分析\n{asset_txt}\n\n'
        f'▎负债端逐项分析\n{liab_txt}\n\n'
    )

    rev_context = (
        f'▎损益端逐项分析\n{rev_txt}\n\n'
    )

    return {
        # 兼容原有输出
        "asset_dict":         asset_info,
        "liab_dict":          liab_info,
        "Revenue_dict":       revenue_info,
        "OIC_dict":           oic_dict,
        # Lead Integrator 直接使用的上下文
        "al_context":         al_context,
        "rev_context":        rev_context,
        "overview_context":   overview,
        "narrative_draft":    narrative,
        "structural_insights": structural,
        "signals_summary":    signals,
        "management_diagnosis": management_diagnosis,
        "suggestion_candidates": suggestions,
        "oic_name":           oic_name,
        "oic_id":             oic_id,
        "data_date":          me_display,
    }
