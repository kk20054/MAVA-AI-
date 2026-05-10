def main(args: dict) -> dict:
    """
    build_response_context v8.1
    ──────────────────────────
    v8.1 核心修复:
    - [v8.1-FIX] 加权投票检测 comp_type，完全不依赖 comp_meta
              CHANGE指标权重10 > BASE指标权重1 > 优先级偏置(yoy>mom>vs_ye)
              解决 MA_L_YE_BAL 抢先导致 comp_type 误判为 vs_year_end 的 bug
    - [v8.1] comp_meta 仅用于 date_shift 兼容（未来可传则用，不传不影响）
    - [v8.0] BANKING_DISPLAY_RULES 策略矩阵 (保留)
    - [v8.0] 全部自计算增量/增幅 (保留)
    - [v8.0] 兜底注释表后 + 币种港元 (保留)
    """
    import json, ast, re, calendar
    from datetime import date

    # ═══════════════ 可调配置 ═══════════════
    DETAIL_TOP_N     = 5
    SIGNIFICANT_PCT  = 10.0
    LARGE_CHANGE_PCT = 20.0
    SMALL_CHANGE_PCT = 3.0
    MAX_RECOMMEND    = 3

    # ═══════════════ [v8.0] 银行标准显示规则 ═══════════════
    # (curr_metric, base_metric|None, metric_label, comp_label|None, compare_flag)
    BANKING_DISPLAY_RULES = {
        ('bal_sheet','yoy'): [
            ('MA_BAL',     'MA_L_YE_BAL',    '时点余额',    '较上年末', True),
            ('MA_MTD_BAL',  None,             '当月日均余额', None,      False),
            ('MA_YTD_BAL', 'MA_L_Y_YTD_BAL', '累计日均余额', '累计同比', True),
        ],
        ('bal_sheet','mom'): [
            ('MA_BAL',     'MA_L_M_BAL',     '时点余额',    '环比',     True),
            ('MA_MTD_BAL', 'MA_L_M_MTD_BAL', '当月日均余额', '当月环比', True),
        ],
        ('bal_sheet','vs_year_end'): [
            ('MA_BAL',     'MA_L_YE_BAL',    '时点余额',    '较上年末', True),
            ('MA_MTD_BAL',  None,             '当月日均余额', None,      False),
            ('MA_YTD_BAL',  None,             '累计日均余额', None,      False),
        ],
        ('bal_sheet','point'): [
            ('MA_BAL',     None, '时点余额',    None, False),
            ('MA_MTD_BAL', None, '当月日均余额', None, False),
        ],
        ('bal_sheet','trend'): [
            ('MA_BAL',     None, '时点余额',    None, False),
            ('MA_MTD_BAL', None, '当月日均余额', None, False),
        ],
        ('revenue','yoy'): [
            ('MA_MTD_BAL', 'MA_L_Y_MTD_BAL', '当月累计', '当月同比', True),
            ('MA_YTD_BAL', 'MA_L_Y_YTD_BAL', '本年累计', '累计同比', True),
        ],
        ('revenue','mom'): [
            ('MA_MTD_BAL', 'MA_L_M_MTD_BAL', '当月累计', '当月环比', True),
        ],
        ('revenue','vs_year_end'): [
            ('MA_YTD_BAL', None, '本年累计', None, False),
        ],
        ('revenue','point'): [
            ('MA_MTD_BAL', None, '当月累计', None, False),
            ('MA_YTD_BAL', None, '本年累计', None, False),
        ],
        ('revenue','trend'): [
            ('MA_MTD_BAL', None, '当月累计', None, False),
            ('MA_YTD_BAL', None, '本年累计', None, False),
        ],
    }

    UNSUPPORTED_DIMS = {
        'customer': {
            'phrases': ['客户数','客户增长','支薪户','支薪客户','AUM','aum',
                        '客户占比','客户结构','客户分层','新增客户','流失客户',
                        '活跃客户','客户规模','管户客户数','客户维','客户贡献'],
            'desc': '客户维相关指标（如客户数量、AUM、支薪户增长率等）',
        },
        'department': {
            'phrases': ['部门排名','部门维','团队汇总','条线维','分行维','支行维','网点维'],
            'desc': '部门维相关指标（如团队/分行/条线汇总等）',
        },
        'visualization': {
            'phrases': ['趋势图','折线图','柱状图','饼图','可视化','Excel图','图表','报表图','走势图'],
            'desc': '可视化图表功能',
        },
    }

    # ═══════════════ 常量注册表 ═══════════════
    CURRENT_METRICS = {'MA_BAL','MA_MTD_BAL','MA_YTD_BAL'}
    BASE_TO_CURRENT = {
        'MA_L_M_BAL':'MA_BAL','MA_L_M_MTD_BAL':'MA_MTD_BAL',
        'MA_L_Y_BAL':'MA_BAL','MA_L_Y_MTD_BAL':'MA_MTD_BAL',
        'MA_L_Y_YTD_BAL':'MA_YTD_BAL','MA_L_YE_BAL':'MA_BAL',
    }
    ALL_EXTENDED_ATTRS = {
        'MA_L_M_BAL','MA_L_M_MTD_BAL','MA_L_Y_BAL','MA_L_Y_MTD_BAL',
        'MA_L_Y_YTD_BAL','MA_L_YE_BAL','MA_YOY_INCREMENT','MA_YOY_GROWTH',
        'MA_MOM_INCREMENT','MA_MOM_GROWTH','MA_L_YE_INCREMENT','MA_L_YE_GROWTH',
    }
    TYPE_DISPLAY_ORDER = ['Revenue','Assets','Liabilities']
    TYPE_CN = {'Revenue':'损益端','Assets':'资产端','Liabilities':'负债端'}

    # ═══════════════ 工具函数 ═══════════════
    def safe_json(obj):
        if isinstance(obj,dict): return obj
        if not obj: return {}
        if isinstance(obj,str):
            s=obj.strip()
            if not s: return {}
            try: return json.loads(s)
            except:
                try: return ast.literal_eval(s)
                except: return {}
        return {}
    def unwrap(d,key):
        if isinstance(d,dict) and key in d and len(d)==1:
            inner=d[key]
            return safe_json(inner) if isinstance(inner,str) else (inner if isinstance(inner,dict) else d)
        return d
    def nl(v):
        if v is None: return []
        if isinstance(v,list): return v
        if isinstance(v,str) and ',' in v: return [x.strip() for x in v.split(',') if x.strip()]
        return [v]
    def nd(s):
        s=str(s).strip()
        if re.fullmatch(r'\d{8}',s): return s
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',s): return s.replace('-','')
        return s
    def to_date(s):
        s=nd(s)
        if not re.fullmatch(r'\d{8}',s): return None
        try: return date(int(s[:4]),int(s[4:6]),int(s[6:8]))
        except: return None
    def fmt_date(s):
        s=nd(s); return f'{s[:4]}-{s[4:6]}-{s[6:8]}' if re.fullmatch(r'\d{8}',s) else str(s)
    def is_month_end(d):
        if d is None: return False
        _,ld=calendar.monthrange(d.year,d.month); return d.day==ld
    def sf(v):
        try: return float(v)
        except: return None
    def fmt_num(v):
        if v is None: return '-'
        a=abs(v)
        if a>=1e8: return f'{v/1e8:.2f}亿元'
        if a>=1e4: return f'{v/1e4:.2f}万元'
        if a==0: return '0.00元'
        return f'{v:,.2f}元'
    def calc_pct(chg,base):
        if base is None or base==0: return None
        return chg/abs(base)*100
    def fmt_pct(pct):
        if pct is None: return 'N/A'
        return f'{pct:+.2f}%' if pct!=0 else '0.00%'
    def dir_word(chg,pct=None):
        if chg==0: return '持平'
        ap=abs(pct) if pct is not None else 0
        if chg>0:
            if ap>=LARGE_CHANGE_PCT: return '大幅增长'
            if ap>=SIGNIFICANT_PCT: return '显著增长'
            if ap<=SMALL_CHANGE_PCT: return '小幅增长'
            return '增长'
        else:
            if ap>=LARGE_CHANGE_PCT: return '大幅下降'
            if ap>=SIGNIFICANT_PCT: return '显著下降'
            if ap<=SMALL_CHANGE_PCT: return '小幅下降'
            return '下降'
    def trend_word(nums):
        if len(nums)<2: return ''
        if all(nums[i]<=nums[i+1] for i in range(len(nums)-1)): return '持续上升'
        if all(nums[i]>=nums[i+1] for i in range(len(nums)-1)): return '持续下降'
        if nums[-1]>nums[0]: return '震荡上行'
        if nums[-1]<nums[0]: return '震荡下行'
        return '有所波动'

    def _metric_base_date_label(d_str, base_metric):
        """根据基期指标推导基期日期标签"""
        d=to_date(d_str)
        if d is None: return ''
        if base_metric in ('MA_L_YE_BAL',):
            return f'{d.year-1}-12-31'
        elif base_metric in ('MA_L_Y_BAL','MA_L_Y_MTD_BAL','MA_L_Y_YTD_BAL'):
            _,ld=calendar.monthrange(d.year-1,d.month)
            return date(d.year-1,d.month,min(d.day,ld)).strftime('%Y-%m-%d')
        elif base_metric in ('MA_L_M_BAL','MA_L_M_MTD_BAL'):
            if d.month==1: return f'{d.year-1}-12-31'
            _,ld=calendar.monthrange(d.year,d.month-1)
            return date(d.year,d.month-1,ld).strftime('%Y-%m-%d')
        return ''

    def _type_key(code):
        t=ind_info.get(code,{}).get('type','')
        return 'revenue' if t=='Revenue' else 'bal_sheet'

    # ═══════════════ [v8.1-FIX] 加权投票检测比较模式 ═══════════════
    def _detect_consolidated_comp(metrics_set):
        """
        从返回指标集推断合并对比模式。
        CHANGE/GROWTH指标(权重10) >> BASE指标(权重1) >> 优先级偏置(yoy>mom>vs_ye)。
        解决：MA_L_YE_BAL 与 MA_L_Y_* 共存时误判为 vs_year_end。
        """
        CHANGE_MAP = {
            'MA_YOY_INCREMENT':'yoy','MA_YOY_GROWTH':'yoy',
            'MA_MOM_INCREMENT':'mom','MA_MOM_GROWTH':'mom',
            'MA_L_YE_INCREMENT':'vs_year_end','MA_L_YE_GROWTH':'vs_year_end',
        }
        BASE_MAP = {
            'MA_L_Y_BAL':'yoy','MA_L_Y_MTD_BAL':'yoy','MA_L_Y_YTD_BAL':'yoy',
            'MA_L_M_BAL':'mom','MA_L_M_MTD_BAL':'mom',
            'MA_L_YE_BAL':'vs_year_end',
        }
        # 偏置: yoy(0.3) > mom(0.2) > vs_year_end(0.1)，仅在同分时起作用
        PRIORITY = {'yoy':0.3,'mom':0.2,'vs_year_end':0.1}
        votes = {}
        for m in metrics_set:
            if m in CHANGE_MAP:
                ct=CHANGE_MAP[m]; votes[ct]=votes.get(ct,0)+10
        for m in metrics_set:
            if m in BASE_MAP:
                ct=BASE_MAP[m]; votes[ct]=votes.get(ct,0)+1
        for ct in votes:
            votes[ct]+=PRIORITY.get(ct,0)
        if not votes: return None
        return max(votes, key=votes.get)

    def _classify_two_dates(dl):
        d1,d2=to_date(dl[0]),to_date(dl[1])
        if d1 is None or d2 is None: return 'two_period'
        if d1>d2: d1,d2=d2,d1
        mg=(d2.year-d1.year)*12+(d2.month-d1.month)
        if d1.month==12 and d1.day==31 and d2.year==d1.year+1: return 'vs_year_end'
        if d2.year==d1.year+1 and d1.month==d2.month:
            if d1.day==d2.day or (is_month_end(d1) and is_month_end(d2)): return 'yoy'
        if mg==1 and is_month_end(d1) and is_month_end(d2): return 'mom'
        return 'two_period'

    # ═══════════════ 解析输入 ═══════════════
    raw_data      = safe_json(args.get('data_dict','{}'))
    mapping_table = safe_json(args.get('mapping_table','{}'))
    user_query    = str(args.get('user_query','') or args.get('query','') or '')

    raw_data      = unwrap(raw_data,'data_dict')
    mapping_table = unwrap(mapping_table,'mapping_table')
    if not isinstance(raw_data,dict): raw_data={}
    if not isinstance(mapping_table,dict): mapping_table={}

    # [v8.1] comp_meta: 尝试获取但不依赖
    comp_meta = safe_json(args.get('comp_meta','{}'))
    if not comp_meta: comp_meta = raw_data.get('_comp_meta',{}) or {}
    if not isinstance(comp_meta,dict): comp_meta={}

    oic_name = raw_data.get('OIC_NAME','未知')
    oic_no   = raw_data.get('OIC','')

    # ═══════════════ 兜底注释 ═══════════════
    def detect_unsupported(query_text):
        if not query_text: return ''
        hits=[]
        for cat,cfg in UNSUPPORTED_DIMS.items():
            for phrase in cfg['phrases']:
                if phrase.lower() in query_text.lower():
                    hits.append((cat,cfg['desc'])); break
        if not hits: return ''
        descs=list(dict.fromkeys(d for _,d in hits))
        return (f'注：您询问的{"、".join(descs)}暂未包含在当前提供的预计算数据中。'
                f'目前已覆盖OIC维度下的资负、损益核心经营指标；'
                f'客户维、部门维及可视化图表等功能正在紧密开发中，预计近期上线。'
                f'如需即时查询上述指标，建议通过其他业务系统获取。')
    fallback_note = detect_unsupported(user_query)

    # ═══════════════ 指标索引 ═══════════════
    ind_info={}; children_map={}; code_order={}; oidx=0
    for tk in TYPE_DISPLAY_ORDER:
        for ind in mapping_table.get(tk,{}).get('indicators',[]):
            code=ind.get('code')
            if not code: continue
            ind_info[code]={'name':ind.get('name',code),'level':int(ind.get('level',0) or 0),
                            'parent_code':ind.get('parent_code'),'type':tk}
            pc=ind.get('parent_code')
            if pc: children_map.setdefault(pc,[]).append(code)
            if code not in code_order: code_order[code]=oidx; oidx+=1

    # ═══════════════ 解析数据键值 ═══════════════
    META_KEYS={'LOB_CODE','TEAM_CODE','AC_BK_BRNO','OIC_NAME','OIC',
               'ZONENO','batchDate','type','level','data_dict','_comp_meta','_date_warnings'}
    parsed={}
    for key,val in raw_data.items():
        if key in META_KEYS or not isinstance(key,str): continue
        parts=key.split('-')
        if len(parts)<3: continue
        code=parts[0]; date_raw=nd(parts[-1])
        mr='-'.join(parts[1:-1])
        mb=mr[:-3] if mr.endswith('-BD') else mr
        fv=sf(val)
        if fv is None: continue
        parsed[(code,mb,date_raw)]=fv

    if not parsed:
        empty_note=fallback_note or ''
        return {
            'response_prompt':'你是一名银行MAVA系统财务分析助手。当前未查询到有效数据。'
                              '请仅输出：未查询到相关数据，请确认查询条件后重试。'
                              +(f'\n\n{empty_note}' if empty_note else ''),
            'md_table':'','template_type':'empty','comp_type':'none','comp_label':'',
            'recommended_questions':'[]','fallback_note':empty_note,
        }

    # ═══════════════ 提取维度 ═══════════════
    all_codes_set={c for c,_,_ in parsed}
    all_codes=sorted(all_codes_set,key=lambda c:code_order.get(c,99999))
    all_metrics_set={m for _,m,_ in parsed}
    all_dates=sorted({d for _,_,d in parsed})

    dtset,dlset=set(),set()
    for c in all_codes:
        info=ind_info.get(c,{})
        if info.get('type'): dtset.add(info['type'])
        if info.get('level',0)>0: dlset.add(info['level'])

    rt=raw_data.get('type')
    detected_types=nl(rt) if rt else [t for t in TYPE_DISPLAY_ORDER if t in dtset]
    if not detected_types: detected_types=['Revenue']
    rl=raw_data.get('level')
    if rl:
        levels=[]
        for lv in nl(rl):
            try: levels.append(int(lv))
            except: pass
    else: levels=sorted(dlset) if dlset else [2]
    if not levels: levels=[2]

    primary_type=detected_types[0]; multi_type=len(detected_types)>1
    typed_codes=[c for c in all_codes if ind_info.get(c,{}).get('type') in dtset]
    codes=typed_codes if typed_codes else all_codes
    max_level=max(levels) if levels else 2
    is_detail=max_level>2 or any(ind_info.get(c,{}).get('level',0)>2 for c in codes)
    has_revenue=any(ind_info.get(c,{}).get('type')=='Revenue' for c in codes)
    has_bal_sheet=any(ind_info.get(c,{}).get('type') in ('Assets','Liabilities') for c in codes)
    need_split=has_revenue and has_bal_sheet
    rev_code_set={c for c in codes if ind_info.get(c,{}).get('type')=='Revenue'}
    bal_code_set={c for c in codes if ind_info.get(c,{}).get('type') in ('Assets','Liabilities')}

    # ═══════════════ [v8.1-FIX] 比较模式检测 ═══════════════
    # 优先用 comp_meta（如果未来架构支持传递），否则完全从数据推断
    is_date_shift = comp_meta.get('mode')=='date_shift'
    display_date  = comp_meta.get('display_date','')
    attr_alias    = comp_meta.get('attr_alias',{})
    dates = all_dates

    if comp_meta.get('consolidated') and comp_meta.get('mode') and not is_date_shift:
        # ── 路径A: comp_meta 可用（未来） ──
        comp_type = comp_meta['mode']
        is_consolidated=True; is_compare=True; is_point=False; is_trend=False
    elif is_date_shift:
        # ── 路径B: 日期偏移 ──
        comp_type='point'; is_point=True; is_trend=False; is_compare=False; is_consolidated=False
    else:
        # ── 路径C: [v8.1核心] 从数据推断 ──
        n_dates=len(all_dates)
        if n_dates>=3:
            comp_type='trend'; is_trend=True; is_compare=False; is_point=False; is_consolidated=False
        elif n_dates==2:
            comp_type=_classify_two_dates(all_dates)
            is_compare=comp_type not in ('point',); is_trend=False
            is_point=not is_compare; is_consolidated=False
        elif n_dates==1:
            detected=_detect_consolidated_comp(all_metrics_set)
            if detected:
                comp_type=detected; is_consolidated=True; is_compare=True
                is_point=False; is_trend=False
            else:
                comp_type='point'; is_point=True; is_compare=False
                is_trend=False; is_consolidated=False
        else:
            comp_type='point'; is_point=True; is_compare=False
            is_trend=False; is_consolidated=False

    comp_label={'point':'','mom':'环比','yoy':'同比','vs_year_end':'较上年末',
                'two_period':'对比','trend':'趋势'}.get(comp_type,'')
    template_type=f'{primary_type}_{comp_type}_{"detail" if is_detail else "summary"}'

    # ═══════════════ 自计算 + 规则获取 ═══════════════
    def _self_calc(code, curr_m, base_m, d):
        cv=parsed.get((code,curr_m,d))
        bv=parsed.get((code,base_m,d)) if base_m else None
        if cv is None: return cv,bv,None,None
        if bv is None: return cv,bv,None,None
        incr=cv-bv; grth=calc_pct(incr,bv)
        return cv,bv,incr,grth

    def _get_rules(code, eff_comp):
        tk=_type_key(code)
        return BANKING_DISPLAY_RULES.get((tk,eff_comp),BANKING_DISPLAY_RULES.get((tk,'point'),[]))

    # ═══════════════ 按类型分组 ═══════════════
    min_lv=min(levels) if levels else 1
    if multi_type:
        _dg=[]
        for tk in TYPE_DISPLAY_ORDER:
            if tk not in dtset: continue
            gc=sorted([c for c in codes if ind_info.get(c,{}).get('type')==tk],
                      key=lambda c:code_order.get(c,99999))
            if gc: _dg.append((tk,gc))
    else:
        _dg=[(primary_type,sorted(codes,key=lambda c:code_order.get(c,99999)))]

    # ═══════════════ 分析文本 ═══════════════
    analysis_lines=[]; highlight_items=[]

    def _name_cell(code):
        info=ind_info.get(code,{}); lv=info.get('level',0)
        indent='\u3000'*max(0,lv-min_lv); name=info.get('name',code)
        txt=f'{indent}{name}'
        if lv<=1: txt=f'**{txt}**'
        return txt

    def _contrib_text(code,d,curr_m=None):
        info=ind_info.get(code,{}); pc=info.get('parent_code')
        if not pc or pc not in ind_info: return ''
        rules=_get_rules(code,comp_type if is_compare else 'point')
        if not rules: return ''
        m=curr_m or rules[0][0]
        cv=parsed.get((code,m,d)); pv=parsed.get((pc,m,d))
        if cv is not None and pv is not None and pv!=0:
            return f'，占{ind_info[pc]["name"]}的{cv/pv*100:.1f}%'
        return ''

    def _describe_compare(code,d):
        rules=_get_rules(code,comp_type); segs=[]; max_pct=0
        for curr_m,base_m,mlabel,clabel,do_comp in rules:
            cv,bv,incr,grth=_self_calc(code,curr_m,base_m,d)
            if cv is None: continue
            seg=f'{mlabel}{fmt_num(cv)}'
            if do_comp and base_m and incr is not None:
                if grth is not None:
                    dw=dir_word(incr,grth)
                    seg+=f'，{clabel}{dw}{fmt_num(abs(incr))}（{fmt_pct(abs(grth))}）'
                    max_pct=max(max_pct,abs(grth))
                elif bv==0 and incr==0:
                    seg+=f'，{clabel}持平'
                else:
                    seg+=f'，{clabel}变动{fmt_num(incr)}'
            segs.append(seg)
        return segs, max_pct

    if is_compare:
        d_curr=dates[-1] if dates else ''
        d_base_trad=dates[0] if len(dates)>=2 and not is_consolidated else None
        for tk,tc in _dg:
            if multi_type: analysis_lines.append(f'**{TYPE_CN.get(tk,tk)}**')
            sc=[c for c in tc if ind_info.get(c,{}).get('level',0)<=2]
            dc=[c for c in tc if ind_info.get(c,{}).get('level',0)>2]
            for code in sc:
                name=ind_info.get(code,{}).get('name',code)
                segs,mp=_describe_compare(code,d_curr)
                if mp>=SIGNIFICANT_PCT:
                    highlight_items.append((name,mp,dir_word(1 if mp>0 else -1,mp)))
                if segs: analysis_lines.append(f'{name}{"，".join(segs)}。')
            if dc:
                first_rule=_get_rules(dc[0],comp_type)
                sort_m=first_rule[0][0] if first_rule else 'MA_BAL'
                sort_b=first_rule[0][1] if first_rule and first_rule[0][4] else None
                scored=[]
                for code in dc:
                    _,_,incr,_=_self_calc(code,sort_m,sort_b,d_curr)
                    scored.append((code,abs(incr) if incr else 0))
                scored.sort(key=lambda x:x[1],reverse=True)
                top=[c for c,_ in scored[:DETAIL_TOP_N]]; rem=len(scored)-DETAIL_TOP_N
                descs=[]
                for code in top:
                    name=ind_info.get(code,{}).get('name',code)
                    segs,_=_describe_compare(code,d_curr)
                    contrib=_contrib_text(code,d_curr)
                    if segs: descs.append(f'{name}{"，".join(segs)}{contrib}')
                if descs:
                    suffix=f'等（另有{rem}个子项）' if rem>0 else ''
                    analysis_lines.append(f'其中，{"；".join(descs)}{suffix}。')

    elif is_trend:
        for tk,tc in _dg:
            if multi_type: analysis_lines.append(f'**{TYPE_CN.get(tk,tk)}**')
            for code in tc:
                name=ind_info.get(code,{}).get('name',code)
                rules=_get_rules(code,'trend'); parts=[]
                for curr_m,_,mlabel,_,_ in rules:
                    avail=[(d,parsed.get((code,curr_m,d))) for d in dates
                           if parsed.get((code,curr_m,d)) is not None]
                    if not avail: continue
                    ct_type=ind_info.get(code,{}).get('type','')
                    if ct_type=='Revenue' and curr_m=='MA_YTD_BAL' and len(avail)>=2:
                        ld,lv=avail[-1]
                        parts.append(f'{mlabel}截至**{fmt_date(ld)}**累计为{fmt_num(lv)}')
                        continue
                    vd='、'.join(f'**{fmt_date(d)}**为{fmt_num(v)}' for d,v in avail)
                    line=f'{mlabel}：{vd}'
                    if len(avail)>=2:
                        nums=[v for _,v in avail]; tw=trend_word(nums)
                        oc=avail[-1][1]-avail[0][1]; op=calc_pct(oc,avail[0][1])
                        st='，变动显著' if op and abs(op)>=SIGNIFICANT_PCT else ''
                        line+=f'（{tw}{st}）'
                        period_segs=[]
                        for i in range(len(avail)-1):
                            sc_=avail[i+1][1]-avail[i][1]; sp=calc_pct(sc_,avail[i][1])
                            period_segs.append(f'{fmt_date(avail[i][0])}→{fmt_date(avail[i+1][0])}'
                                f'{dir_word(sc_,sp)}{fmt_pct(abs(sp)) if sp else ""}')
                        line+=f'。逐期变动：{"；".join(period_segs)}'
                        if op and abs(op)>=SIGNIFICANT_PCT:
                            highlight_items.append((name,abs(op),tw))
                    parts.append(line)
                if parts:
                    contrib=_contrib_text(code,dates[-1]) if dates else ''
                    analysis_lines.append(f'{name}：{"。".join(parts)}{contrib}。')

    else:  # point
        d=dates[0] if dates else ''
        for tk,tc in _dg:
            if multi_type: analysis_lines.append(f'**{TYPE_CN.get(tk,tk)}**')
            sc=[c for c in tc if ind_info.get(c,{}).get('level',0)<=2]
            dc=[c for c in tc if ind_info.get(c,{}).get('level',0)>2]
            for code in sc:
                name=ind_info.get(code,{}).get('name',code)
                rules=_get_rules(code,'point'); pts=[]
                for curr_m,_,mlabel,_,_ in rules:
                    eff_m=curr_m
                    if is_date_shift:
                        for api_a,orig_a in attr_alias.items():
                            if orig_a==curr_m and parsed.get((code,api_a,d)) is not None:
                                eff_m=api_a; break
                    v=parsed.get((code,eff_m,d))
                    if v is not None: pts.append(f'{mlabel}{fmt_num(v)}')
                if pts: analysis_lines.append(f'{name}{"，".join(pts)}。')
            if dc:
                rules0=_get_rules(dc[0],'point')
                m0=rules0[0][0] if rules0 else 'MA_BAL'
                ds=sorted(dc,key=lambda c:abs(parsed.get((c,m0,d),0) or 0),reverse=True)
                top=ds[:DETAIL_TOP_N]; rem=len(ds)-DETAIL_TOP_N; descs=[]
                for code in top:
                    name=ind_info.get(code,{}).get('name',code)
                    rules=_get_rules(code,'point'); pts=[]
                    for curr_m,_,mlabel,_,_ in rules:
                        eff_m=curr_m
                        if is_date_shift:
                            for api_a,orig_a in attr_alias.items():
                                if orig_a==curr_m and parsed.get((code,api_a,d)) is not None:
                                    eff_m=api_a; break
                        v=parsed.get((code,eff_m,d))
                        if v is not None: pts.append(f'{mlabel}{fmt_num(v)}')
                    contrib=_contrib_text(code,d)
                    if pts: descs.append(f'{name}{"，".join(pts)}{contrib}')
                if descs:
                    suffix=f'等（另有{rem}个子项）' if rem>0 else ''
                    analysis_lines.append(f'其中，{"；".join(descs)}{suffix}。')

    exec_summary=''
    if highlight_items:
        highlight_items.sort(key=lambda x:x[1],reverse=True)
        parts=[f'{n}{dw}' for n,_,dw in highlight_items[:3]]
        exec_summary=f'**要点提示**：本期值得关注的变动包括{"、".join(parts)}。\n\n'

    # ═══════════════ Markdown 表格 ═══════════════
    def build_banking_table(section_codes, type_key, eff_comp, d_str):
        rules=BANKING_DISPLAY_RULES.get((type_key,eff_comp),[])
        if not rules: return ''
        sc=sorted(section_codes,key=lambda c:code_order.get(c,99999))
        d=nd(d_str); cd=fmt_date(d)
        header=['指标']; col_defs=[]
        for curr_m,base_m,mlabel,clabel,do_comp in rules:
            header.append(f'{cd}<br>{mlabel}'); col_defs.append(('curr',curr_m))
            if do_comp and base_m:
                bd=_metric_base_date_label(d,base_m)
                header.append(f'{bd}<br>{mlabel}'); col_defs.append(('base',base_m))
                header.append(f'{clabel}<br>增量'); col_defs.append(('change',curr_m,base_m))
                header.append(f'{clabel}<br>增幅'); col_defs.append(('growth',curr_m,base_m))
        rows=[]
        for code in sc:
            row=[_name_cell(code)]
            for cdef in col_defs:
                if cdef[0]=='curr':
                    row.append(fmt_num(parsed.get((code,cdef[1],d))))
                elif cdef[0]=='base':
                    row.append(fmt_num(parsed.get((code,cdef[1],d))))
                elif cdef[0]=='change':
                    cv=parsed.get((code,cdef[1],d)); bv=parsed.get((code,cdef[2],d))
                    row.append(fmt_num(cv-bv) if cv is not None and bv is not None else '-')
                elif cdef[0]=='growth':
                    cv=parsed.get((code,cdef[1],d)); bv=parsed.get((code,cdef[2],d))
                    if cv is not None and bv is not None and bv!=0:
                        row.append(fmt_pct((cv-bv)/abs(bv)*100))
                    else: row.append('-')
            rows.append(row)
        if not rows: return ''
        md='| '+' | '.join(header)+' |\n'
        md+='| '+' | '.join(['---']+['---:']*(len(header)-1))+' |\n'
        md+='\n'.join('| '+' | '.join(r)+' |' for r in rows)
        return md

    def build_trend_table(section_codes, type_key, dates_list):
        rules=BANKING_DISPLAY_RULES.get((type_key,'trend'),[])
        if not rules: return ''
        sc=sorted(section_codes,key=lambda c:code_order.get(c,99999))
        header=['指标']; col_defs=[]
        for d in dates_list:
            fd=fmt_date(d)
            for curr_m,_,mlabel,_,_ in rules:
                header.append(f'{fd}<br>{mlabel}'); col_defs.append((curr_m,d))
        rows=[]
        for code in sc:
            row=[_name_cell(code)]
            for m,d in col_defs: row.append(fmt_num(parsed.get((code,m,d))))
            rows.append(row)
        if not rows: return ''
        md='| '+' | '.join(header)+' |\n'
        md+='| '+' | '.join(['---']+['---:']*(len(header)-1))+' |\n'
        md+='\n'.join('| '+' | '.join(r)+' |' for r in rows)
        return md

    def build_point_table(section_codes, type_key, d_str):
        rules=BANKING_DISPLAY_RULES.get((type_key,'point'),[])
        if not rules: return ''
        sc=sorted(section_codes,key=lambda c:code_order.get(c,99999))
        d=nd(d_str); header=['指标']; metrics_in_table=[]
        for curr_m,_,mlabel,_,_ in rules:
            header.append(mlabel); metrics_in_table.append(curr_m)
        rows=[]
        for code in sc:
            row=[_name_cell(code)]
            for m in metrics_in_table:
                eff_m=m
                if is_date_shift:
                    for api_a,orig_a in attr_alias.items():
                        if orig_a==m and parsed.get((code,api_a,d)) is not None:
                            eff_m=api_a; break
                row.append(fmt_num(parsed.get((code,eff_m,d))))
            rows.append(row)
        if not rows: return ''
        md='| '+' | '.join(header)+' |\n'
        md+='| '+' | '.join(['---']+['---:']*(len(header)-1))+' |\n'
        md+='\n'.join('| '+' | '.join(r)+' |' for r in rows)
        return md

    def build_two_period_table(section_codes, type_key, d_early, d_late):
        rules=BANKING_DISPLAY_RULES.get((type_key,'point'),[])
        if not rules: return ''
        sc=sorted(section_codes,key=lambda c:code_order.get(c,99999))
        fe=fmt_date(d_early); fl=fmt_date(d_late)
        header=['指标']; metrics_list=[]
        for curr_m,_,mlabel,_,_ in rules:
            header+=[f'{fl}<br>{mlabel}',f'{fe}<br>{mlabel}',f'变动<br>增量',f'变动<br>增幅']
            metrics_list.append(curr_m)
        rows=[]
        for code in sc:
            row=[_name_cell(code)]
            for m in metrics_list:
                cv=parsed.get((code,m,d_late)); bv=parsed.get((code,m,d_early))
                row.append(fmt_num(cv)); row.append(fmt_num(bv))
                if cv is not None and bv is not None:
                    incr=cv-bv; row.append(fmt_num(incr))
                    row.append(fmt_pct(calc_pct(incr,bv)) if bv!=0 else '-')
                else: row+=['-','-']
            rows.append(row)
        if not rows: return ''
        md='| '+' | '.join(header)+' |\n'
        md+='| '+' | '.join(['---']+['---:']*(len(header)-1))+' |\n'
        md+='\n'.join('| '+' | '.join(r)+' |' for r in rows)
        return md

    def _build_section(section_codes, type_key):
        if is_compare and (is_consolidated or comp_type in ('mom','yoy','vs_year_end')):
            d=dates[-1] if dates else ''
            return build_banking_table(section_codes,type_key,comp_type,d)
        elif is_compare and comp_type=='two_period' and len(dates)==2:
            return build_two_period_table(section_codes,type_key,dates[0],dates[1])
        elif is_trend:
            return build_trend_table(section_codes,type_key,dates)
        else:
            d=dates[0] if dates else ''
            return build_point_table(section_codes,type_key,d)

    md_table=''
    if need_split:
        mp=[]
        if rev_code_set:
            rt=_build_section([c for c in codes if c in rev_code_set],'revenue')
            if rt: mp.append(f'**附：损益类数据明细表**\n\n{rt}')
        if bal_code_set:
            ha=any(ind_info.get(c,{}).get('type')=='Assets' for c in bal_code_set)
            hl=any(ind_info.get(c,{}).get('type')=='Liabilities' for c in bal_code_set)
            ttl='资产负债类' if ha and hl else ('资产类' if ha else '负债类')
            bt=_build_section([c for c in codes if c in bal_code_set],'bal_sheet')
            if bt: mp.append(f'**附：{ttl}数据明细表**\n\n{bt}')
        md_table='\n\n'.join(mp)
    else:
        tk='revenue' if has_revenue and not has_bal_sheet else 'bal_sheet'
        tbl=_build_section(codes,tk)
        md_table=f'**附：数据明细表**\n\n{tbl}' if tbl else ''

    # ═══════════════ 开头语 ═══════════════
    def build_type_cn(tl):
        ts=set(tl)
        if ts=={'Assets','Liabilities'}: return '资产负债'
        if ts>={'Assets','Liabilities','Revenue'}: return '经营'
        if ts=={'Assets','Revenue'}: return '资产及损益'
        if ts=={'Liabilities','Revenue'}: return '负债及损益'
        return {'Revenue':'损益','Assets':'资产','Liabilities':'负债'}.get(tl[0],'') if tl else ''
    type_cn=build_type_cn(detected_types)
    currency_note='币种为**港元**，'
    base_label_map={'mom':'上月末','yoy':'去年同期','vs_year_end':'上年末'}

    # [v8.1] 基期日期：优先 comp_meta，否则自推导
    def _get_opener_base_date():
        # 先尝试 comp_meta
        bdl=comp_meta.get('base_date_label','')
        if bdl and re.fullmatch(r'\d{4}-\d{2}-\d{2}',bdl): return bdl
        # 自推导
        if not dates: return ''
        ref_metric={'yoy':'MA_L_Y_BAL','mom':'MA_L_M_BAL','vs_year_end':'MA_L_YE_BAL'}.get(comp_type,'MA_L_YE_BAL')
        return _metric_base_date_label(fmt_date(dates[0]),ref_metric)

    if is_compare and is_consolidated:
        base_date_str=_get_opener_base_date()
        opener=(f'您好，以下是客户经理**{oic_name}**（工号：{oic_no}），{currency_note}'
                f'截至**{fmt_date(dates[0])}**的{type_cn}指标{comp_label}分析'
                f'（{base_label_map.get(comp_type,"基期")}：**{base_date_str}**）：')
    elif is_compare and len(dates)==2:
        cd_desc={'mom':'环比（较上月）','yoy':'同比（较去年同期）','vs_year_end':'较上年末',
                 'two_period':f'与{fmt_date(dates[0])}对比'}.get(comp_type,'对比')
        opener=(f'您好，以下是客户经理**{oic_name}**（工号：{oic_no}），{currency_note}'
                f'截至**{fmt_date(dates[-1])}**的{type_cn}指标{cd_desc}分析'
                f'（基期：**{fmt_date(dates[0])}**）：')
    elif is_trend:
        bold_dates='、'.join(f'**{fmt_date(d)}**' for d in dates)
        opener=(f'您好，以下是客户经理**{oic_name}**（工号：{oic_no}），{currency_note}'
                f'在{bold_dates}期间的{type_cn}指标变动趋势分析：')
    elif is_date_shift:
        opener=(f'您好，以下是数据日期为**{display_date}**，'
                f'客户经理**{oic_name}**（工号：{oic_no}），{currency_note}'
                f'{type_cn}情况简析：')
    else:
        bold_dates='、'.join(f'**{fmt_date(d)}**' for d in dates)
        opener=(f'您好，以下是数据日期为{bold_dates}，'
                f'客户经理**{oic_name}**（工号：{oic_no}），{currency_note}'
                f'{type_cn}情况简析：')

    dw_list=raw_data.get('_date_warnings',[])
    if isinstance(dw_list,str): dw_list=[dw_list]
    date_warn=''
    if dw_list: date_warn='\n⚠️ 注意：'+'；'.join(dw_list)+'\n'

    # ═══════════════ 推荐后续问题 ═══════════════
    def generate_recommendations():
        recs=[]; tag=oic_no or ''; prefix=f'{tag} ' if tag else ''
        if max_level<=2:
            drill=[]
            for code in codes:
                info=ind_info.get(code,{})
                if info.get('level')==2 and code in children_map:
                    name=info.get('name','')
                    is_hl=any(h[0]==name for h in highlight_items)
                    val=0; rules=_get_rules(code,comp_type if is_compare else 'point')
                    if rules:
                        m=rules[0][0]; dd=dates[-1] if dates else ''
                        v=parsed.get((code,m,dd))
                        if v is not None: val=abs(v)
                    drill.append((name,is_hl,val))
            drill.sort(key=lambda x:(not x[1],-x[2]))
            for name,_,_ in drill[:2]:
                if name: recs.append(f'进一步查看{prefix}【{name}】明细构成')
        if len(detected_types)==1 and max_level<=2:
            queried_l2={c for c in codes if ind_info.get(c,{}).get('level')==2}
            same_l2=[c for c in ind_info if ind_info[c].get('type')==detected_types[0]
                     and ind_info[c].get('level')==2 and c not in queried_l2]
            same_l2.sort(key=lambda c:code_order.get(c,99999))
            for code in same_l2[:1]:
                name=ind_info[code].get('name','')
                if name: recs.append(f'了解{prefix}【{name}】情况')
        queried=set(detected_types)
        type_cn_map={'Revenue':'损益','Assets':'资产','Liabilities':'负债'}
        if len(queried)<3:
            missing=[t for t in TYPE_DISPLAY_ORDER if t not in queried]
            if missing:
                tn=type_cn_map.get(missing[0],'')
                if tn: recs.append(f'查询{prefix}{tn}端整体表现')
        if is_point or is_date_shift: recs.append(f'分析{prefix}{type_cn}同比变化')
        elif is_compare and comp_type in ('yoy','mom'): recs.append(f'查看{prefix}{type_cn}近三个月变动趋势')
        elif is_compare and comp_type=='vs_year_end': recs.append(f'分析{prefix}{type_cn}同比变化')
        elif is_trend: recs.append(f'对比{prefix}{type_cn}较上年末变化')
        seen=set(); out=[]
        for r in recs:
            if r not in seen: seen.add(r); out.append(r)
        return out[:MAX_RECOMMEND]
    recs=generate_recommendations()

    # ═══════════════ 写作指引 ═══════════════
    cg=(f'行文原则：先总后分、异动优先。'
        f'变动幅度措辞：≥{LARGE_CHANGE_PCT}%"大幅"，{SIGNIFICANT_PCT}%-{LARGE_CHANGE_PCT}%"显著"，'
        f'{SMALL_CHANGE_PCT}%-{SIGNIFICANT_PCT}%"增长/下降"，<{SMALL_CHANGE_PCT}%"小幅"或"基本持平"。')
    banking_hint=(
        '银行经营分析标准：资负类以时点余额+较上年末/环比变动为主线，辅以累计日均余额同比；'
        '损益类环比仅比当月累计，同比兼看当月累计与本年累计。'
        '句式参考："xx时点余额xx亿元，较上年末增长xx亿元（+xx%）；累计日均余额xx亿元，累计同比增长xx亿元（+xx%）"。')
    if is_compare and multi_type and is_detail:
        sg=cg+banking_hint+'按类别分段描述，每段先概述汇总指标变动，再"其中"引出变动最大的前2~3个子指标。'
    elif is_compare and multi_type:
        sg=cg+banking_hint+'按类别分段描述，每个指标按银行标准句式描述。'
    elif is_compare:
        sg=cg+banking_hint+'先概述汇总指标，再展开明细，优先描述变动最大的指标。'
    elif is_trend: sg=cg+'先概述趋势方向，再展开子指标。损益类年累计仅引用最新值。'
    elif is_point and multi_type: sg=cg+'按类别分段描述。'
    else: sg=cg+'简要概述各指标数值。'

    # ═══════════════ LLM 提示词 ═══════════════
    ab=(exec_summary if exec_summary else '')+('\n\n'.join(analysis_lines) if analysis_lines else '（无可用分析数据）')
    note_block=''
    if fallback_note:
        note_block=f'\n\n━━━ 兜底注释（请在数据表格之后原样输出）━━━\n{fallback_note}\n'

    prompt=(
        '你是一名银行MAVA系统的财务分析助手。以下数值已由系统预计算完成，请润色为专业简洁的中文分析回复。\n\n'
        '━━━ 核心规则 ━━━\n'
        '1. 禁止修改任何数值\n'
        '2. 自然语言段落描述，禁止项目符号/编号列表\n'
        '3. 先总后分，异动优先\n'
        '4. 正文末尾原样附上全部数据表格\n'
        '5. 如存在"兜底注释"，必须在数据表格之后单独一段原样输出（以"注："开头）\n'
        '6. 金额单位已格式化为"元/万元/亿元"直接引用；币种已在开头声明，正文中不再重复\n'
        '7. 类别段首词保留Markdown加粗\n'
        '8. 客户经理姓名和日期的加粗格式保持不变\n'
        '9. 使用预计算中的分级措辞，不自行替换\n'
        '10. 单一类别禁止自行添加分类标签\n'
        '11. 表格中L1指标名的加粗保持不变\n'
        f'\n━━━ 场景写作指引 ━━━\n{sg}\n'
        f'\n━━━ 开头语（原样使用）━━━\n{opener}\n'
        f'{date_warn}'
        f'\n━━━ 预计算分析结果 ━━━\n{ab}\n'
        f'\n━━━ 数据表格（原样附末尾）━━━\n\n{md_table}\n\n'
        f'{note_block}'
        '请生成最终回复。'
    )

    return {
        'response_prompt': prompt,
        'md_table': md_table,
        'template_type': template_type,
        'comp_type': comp_type,
        'comp_label': comp_label,
        'recommended_questions': json.dumps(recs, ensure_ascii=False),
        'fallback_note': fallback_note,
    }