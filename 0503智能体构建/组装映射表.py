import re
import datetime
from datetime import timedelta


def main(args: dict) -> dict:
    """
    运行代码节点会调用此函数
    :param args: 输入固定为args字典类型，kv为输入参数键值对
    :return: 输出参数为字典类型，kv为输出参数键值对
    """

    # 1.1 指标层级定义 (Indicator Hierarchy)
    revenue_key_prefix_dict = {
        "MA_A1_0": "一、营业净收入",
        "MA_A11_0": "（一）净利息收入",
        "MA_A111_0": "（1）贷款净利息收入",
        "MA_A111_1": "1.房产按揭贷款",
        "MA_A111_2": "2.房产按揭贷款 - 員工",
        "MA_A111_3": "3.个人贷款",
        "MA_A111_4": "4.税务贷款",
        "MA_A111_5": "5.透支",
        "MA_A111_6": "6.定期循环贷款",
        "MA_A111_7": "7.银团贷款",
        "MA_A111_8": "8.贸易融资",
        "MA_A111_9": "9.贸易融资 - CMB分润",
        "MA_A111_10": "10.支票贴现",
        "MA_A111_11": "11.租赁贷款",
        "MA_A111_12": "12.信用卡贷款",
        "MA_A111_13": "13.保理",
        "MA_A111_14": "14.新股认购/保证金贷款",
        "MA_A111_15": "15.其他贷款",
        "MA_A111_16": "16.不良贷款",
        "MA_A113_0": "（3）存拆同业净利息收入",
        "MA_A114_0": "（4）客户存款净利息收入",
        "MA_A1141_0": "1.低息存款",
        "MA_A11411_0": "a.活期存款",
        "MA_A11411_1": "i.活期存款 - 非员工",
        "MA_A11411_2": "ii.活期存款 - 员工",
        "MA_A1141_1": "b.储蓄存款",
        "MA_A1142_0": "2.定期存款",
        "MA_A1142_1": "a.定期存款 - 非CMB分润",
        "MA_A1142_2": "b.定期存款 - CMB分润",
        "MA_A115_1": "（5）发行存款证",
        "MA_A117_0": "（7）同业存拆利息支出",
        "MA_A12_0": "（二）中间业务净收入",
        "MA_A12_1": "其中：1.收费及佣金收入",
        "MA_A12_2": " 2.收费及佣金支出",
        "MA_A13_0": "（三）财资业务净收入",
        "MA_A13_1": "（1）交易业务净收入",
        "MA_A13_2": "（2）以FVPL入账金融资产及负债之净收益",
        "MA_D1_0": "四、拨备前利润",
        "MA_E1_0": "五、资产减值(损失)/回拨",
        "MA_E1_1": "（一）个别计提",
        "MA_E1_2": "（二）组合计提",
        "MA_E1_3": "（三）回拨",
        "MA_F1_0": "六、拨备后利润 (成本分摊前)",
        "MA_G1_0": "七、成本分摊",
        "MA_G1_1": "（一）中后台成本分摊",
        "MA_G1_2": "（二）财务池成本分摊",
        "MA_H1_0": "八、税前利润",
        "MA_H2_1": "减：所得税及递延税支出",
        "MA_J1_0": "九、税后净利润",
        "MA_K1_0": "影子收入",
        "MA_K1_1": "1.利息影子收入",
        "MA_K1_2": "2.非息影子收入"
    }

    asset_key_prefix_dict = {
        "MA_M1_0": "一、资产",
        "MA_M11_0": "（一）贷款",
        "MA_M111_0": "（1）正常贷款",
        "MA_M111_1": "1.房产按揭贷款",
        "MA_M111_2": "2.房产按揭贷款 - 员工",
        "MA_M111_3": "3.个人贷款",
        "MA_M111_4": "4.税务贷款",
        "MA_M111_5": "5.透支",
        "MA_M111_6": "6.定期循环贷款",
        "MA_M111_7": "7.银团贷款",
        "MA_M111_8": "8.贸易融资",
        "MA_M111_9": "9.支票贴现",
        "MA_M111_10": "10.租赁贷款",
        "MA_M111_11": "11.信用卡贷款",
        "MA_M111_12": "12.保理",
        "MA_M111_13": "13.新股认购/保证金贷款",
        "MA_M111_14": "14.其他贷款",
        "MA_M112_1": "（2）不良贷款",
        "MA_M12_0": "（二）债券投资",
        "MA_M12_1": "（1）AC债券投资",
        "MA_M12_2": "（2）FVOCI债券投资",
        "MA_M12_3": "（3）指定FVPL债券投资",
        "MA_M12_4": "（4）FVTPL债券投资",
        "MA_M12_5": "（5）交易性债券投资",
        "MA_M13_0": "（三）拨备余额",
        "MA_M13_1": "（1）组合",
        "MA_M13_2": "（2）个别",
        "MA_M14_0": "（四）存拆同业",
        "MA_M14_1": "（1）存放同业",
        "MA_M14_2": "（2）存拆同业",
        "MA_M14_3": "（3）REVERSE REPO"
    }

    liab_key_prefix_dict = {
        "MA_N1_0": "二、负债",
        "MA_N11_0": "（一）客户存款",
        "MA_N111_0": "（1）低息存款",
        "MA_N1111_0": "1.活期存款",
        "MA_N1111_1": "a.活期存款 - 非员工",
        "MA_N1111_2": "b.活期存款 - 员工",
        "MA_N111_2": "2.储蓄存款",
        "MA_N112_1": "（2）定期存款",
        "MA_N12_1": "（二）发行存款证",
        "MA_N13_0": "（三）发行债券",
        "MA_N13_1": "（1）发行其他债券",
        "MA_N13_2": "（2）发行后偿债券",
        "MA_N13_3": "（3）发行CLN",
        "MA_N13_4": "（4）发行ELN",
        "MA_N14_0": "（四）同业存放",
        "MA_N14_1": "（1）同业存放",
        "MA_N14_2": "（2）同业存拆",
        "MA_N14_3": "（3）REPO"
    }

    # 1.2 度量维度定义 (Metrics Definition)
    revenue_metrics = {
        'MA_MTD_BAL': 'MTD_月累计',
        'MA_YTD_BAL': 'YTD_年累计'
    }

    asset_liab_metrics = {
        'MA_BAL': 'BAL_月时点余额',
        'MA_MTD_BAL': 'MTD_月日均余额',
        'MA_YTD_BAL': 'YTD_年日均余额'
    }


    def parse_hierarchy(data_dict):
        """
        自动解析带有序号的中文指标名，生成层级结构 (Code, Name, Level, Parent)
        """
        sorted_items = list(data_dict.items())

        hierarchy_list = []
        stack = []  # 栈用于追踪父节点：[(level, code), ...]

        for code, full_name in sorted_items:
            name_stripped = full_name.strip()
            clean_name = name_stripped
            level = 0

            if re.match(r'^[一二三四五六七八九十]+、', name_stripped):
                level = 1
                clean_name = re.sub(r'^[一二三四五六七八九十]+、', '', name_stripped)
            elif re.match(r'^（[一二三四五六七八九十]+）', name_stripped) or re.match(r'^减：', name_stripped):
                level = 2
                clean_name = re.sub(r'^（[一二三四五六七八九十]+）', '', name_stripped).replace("减：", "")
            elif re.match(r'^（\d+）', name_stripped):
                level = 3
                clean_name = re.sub(r'^（\d+）', '', name_stripped)
            elif re.match(r'^\d+\.', name_stripped) or re.match(r'^其中：\d+\.', name_stripped):
                level = 4
                clean_name = re.sub(r'^其中：', '', name_stripped)
                clean_name = re.sub(r'^\d+\.', '', clean_name)
            elif re.match(r'^[a-z]+\.', name_stripped):
                level = 5
                clean_name = re.sub(r'^[a-z]+\.', '', name_stripped)
            elif re.match(r'^[ivx]+\.', name_stripped):
                level = 6
                clean_name = re.sub(r'^[ivx]+\.', '', name_stripped)
            else:
                level = stack[-1][0] + 1 if stack else 1

            while stack and stack[-1][0] >= level:
                stack.pop()

            parent_code = stack[-1][1] if stack else None
            stack.append((level, code))

            hierarchy_list.append({
                "code": code,
                "name": clean_name.strip(),
                "level": level,
                "parent_code": parent_code
            })

        return hierarchy_list


    revenue_structured = parse_hierarchy(revenue_key_prefix_dict)
    asset_structured = parse_hierarchy(asset_key_prefix_dict)
    liab_structured = parse_hierarchy(liab_key_prefix_dict)

    # 4. 组装 Mapping Table
    mapping_table = {
        "Revenue": {
            "type_cn": "损益类/收入类",
            "indicators": revenue_structured,
            "available_metrics": revenue_metrics
        },
        "Assets": {
            "type_cn": "资产类",
            "indicators": asset_structured,
            "available_metrics": asset_liab_metrics
        },
        "Liabilities": {
            "type_cn": "负债类",
            "indicators": liab_structured,
            "available_metrics": asset_liab_metrics
        }
    }

    # 获取传入日期，默认为 ''
    current_time_str = args.get('currentTime', '')
    if current_time_str:
        current_date = datetime.datetime.strptime(current_time_str[:10], "%Y-%m-%d").date()
        current_date_str = current_date.strftime("%Y-%m-%d")
    else:
        current_date = datetime.date.today()
        current_date_str = current_date.strftime("%Y-%m-%d")


    # 定义获取月末的函数
    def get_month_end(year, month):
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
        return next_month - datetime.timedelta(days=1)


    # 定义月份减法函数
    def subtract_months(date, months):
        year = date.year
        month = date.month

        month -= months
        while month <= 0:
            month += 12
            year -= 1

        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
        last_day_of_month = (next_month - datetime.timedelta(days=1)).day
        day = min(date.day, last_day_of_month)

        return datetime.date(year, month, day)


    # 计算昨天，上月，上上月，上三月
    yesterday = current_date - datetime.timedelta(days=1)
    t_minus_1 = subtract_months(current_date, 1)
    t_minus_2 = subtract_months(current_date, 2)
    t_minus_3 = subtract_months(current_date, 3)

    # 计算 T-1, T-2, T-3 月末
    month_ends = []
    temp_y, temp_m = current_date.year, current_date.month

    # 获取前三个月的月末（从当前月的前一个月开始）
    for _ in range(3):
        if temp_m == 1:
            temp_m = 12
            temp_y -= 1
        else:
            temp_m -= 1
        month_ends.append(get_month_end(temp_y, temp_m).strftime("%Y-%m-%d"))

    t_minus_1_end, t_minus_2_end, t_minus_3_end = month_ends

    # 计算去年年末
    last_year_end = datetime.date(current_date.year - 1, 12, 31).strftime("%Y-%m-%d")

    date_context = {
        "今天": current_date_str,
        "昨天": yesterday.strftime("%Y-%m-%d"),
        "上年末": last_year_end,
        "上月": t_minus_1.strftime("%Y-%m-%d"),  # 格式化为字符串
        "上上月": t_minus_2.strftime("%Y-%m-%d"),
        "上上上月": t_minus_3.strftime("%Y-%m-%d"),
        "上月末": t_minus_1_end,
        "上上月末": t_minus_2_end,
        "上上上月末": t_minus_3_end
    }

    prod_mapping_table = [
        "双边贷款类<span class=\"type\">(公司)</span>",
        "信用卡现金分期贷款",
        "贸易融资类<span class=\"type\">(资产相关)</span>",
        "定期/循环贷款类<span class=\"type\">(零售)</span>",
        "结构性融资",
        "银团贷款",
        "房产按揭类<span class=\"type\">(零售)</span>",
        "托管类",
        "信用卡类",
        "资产管理类",
        "清算类",
        "对公担保类",
        "自助银行类",
        "保险类<span class=\"type\">(公司)</span>",
        "现金管理类",
        "资产交易类",
        "债券承销类",
        "证券产品类",
        "财务顾问类",
        "电子银行类",
        "基金销售<span class=\"type\">(零售)</span>",
        "保险类<span class=\"type\">(零售)</span>"
    ]

    ret = {
        "prod_mapping_table": prod_mapping_table,
        "date_context": date_context,
        "mapping_table": mapping_table

    }
    return ret