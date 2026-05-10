def main(args: dict) -> dict:
    """
    查询数据模块 - 预处理脚本 v8.1
    ─────────────────────────────
    v8.1 = v8.0 无实质变更（bug 在 data_slicing 端）
    v8.0 变更回顾:
    - TREND_MAX_LEVELS=1
    - 资负类始终请求 MA_BAL+MA_MTD_BAL+MA_YTD_BAL
    - YoY 追加 MA_L_YE_BAL
    """
    import json, ast, calendar
    from datetime import date as Date

    MAX_LEVELS        = 3
    MIN_LEVELS        = 2
    TREND_MAX_LEVELS  = 1
    MAX_INDICATORS    = 50
    MAX_CELLS_EST     = 300
    EARLIEST_VALID    = Date(2025, 12, 31)

    COMP_ATTR_CFG = {
        'mom': {
            'base_map':  {'MA_BAL':'MA_L_M_BAL','MA_MTD_BAL':'MA_L_M_MTD_BAL'},
            'extras':    ['MA_MOM_INCREMENT','MA_MOM_GROWTH'],
            'label':     '环比',
        },
        'yoy': {
            'base_map':  {'MA_BAL':'MA_L_Y_BAL','MA_MTD_BAL':'MA_L_Y_MTD_BAL',
                          'MA_YTD_BAL':'MA_L_Y_YTD_BAL'},
            'extras':    ['MA_YOY_INCREMENT','MA_YOY_GROWTH'],
            'label':     '同比',
        },
        'vs_year_end': {
            'base_map':  {'MA_BAL':'MA_L_YE_BAL'},
            'extras':    ['MA_L_YE_INCREMENT','MA_L_YE_GROWTH'],
            'label':     '较上年末',
        },
    }
    ALL_EXTENDED_ATTRS = {
        'MA_L_M_BAL','MA_L_M_MTD_BAL',
        'MA_L_Y_BAL','MA_L_Y_MTD_BAL','MA_L_Y_YTD_BAL','MA_L_YE_BAL',
        'MA_YOY_INCREMENT','MA_YOY_GROWTH',
        'MA_MOM_INCREMENT','MA_MOM_GROWTH',
        'MA_L_YE_INCREMENT','MA_L_YE_GROWTH',
    }

    def _parse_d(s):
        s = str(s).strip().replace('-','')
        if len(s)==8:
            try: return Date(int(s[:4]),int(s[4:6]),int(s[6:8]))
            except: return None
        return None
    def _fmt_d(d): return d.strftime('%Y-%m-%d')
    def _month_end(y,m):
        _,ld=calendar.monthrange(y,m); return Date(y,m,ld)
    def _is_month_end(d):
        _,ld=calendar.monthrange(d.year,d.month); return d.day==ld
    def _add_months(d,n):
        m=d.month+n; y=d.year+(m-1)//12; m=(m-1)%12+1; return _month_end(y,m)
    def _is_valid_api_date(d):
        if d is None: return False
        today=Date.today()
        if d>today: return False
        if d==EARLIEST_VALID: return True
        if d.year>=2026 and _is_month_end(d): return True
        if d==today: return True
        return False
    def _calc_base_date(d_late, comp_key):
        if comp_key=='mom': return _add_months(d_late,-1)
        elif comp_key=='yoy':
            try: return _month_end(d_late.year-1,d_late.month)
            except: return None
        elif comp_key=='vs_year_end': return Date(d_late.year-1,12,31)
        return None

    is_redirect=args.get('is_redirect',False)
    redirect_message=args.get('redirect_message','')
    if isinstance(is_redirect,str): is_redirect=is_redirect.lower() in ('true','1','yes')
    if is_redirect:
        return {"intent2_output":json.dumps({"requestType":0,"is_redirect":True,
            "redirect_source":"data_query","redirect_message":redirect_message},ensure_ascii=False)}

    intent2_output={"requestType":None}
    ai_output=args.get('ai_output','')
    mapping_table_str=args.get('mapping_table','')
    mapping_table={}
    if mapping_table_str:
        try: mapping_table=json.loads(mapping_table_str)
        except:
            try: mapping_table=ast.literal_eval(mapping_table_str)
            except Exception as e:
                intent2_output['requestType']=999
                intent2_output['type999_res']=f"mapping_table 解析失败: {e}"
                return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}

    if not ai_output or not ai_output.strip():
        intent2_output['requestType']=999; intent2_output['type999_res']="ai_output 为空"
        return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}

    si=ai_output.find('{'); ei=ai_output.rfind('}')
    if si==-1 or ei==-1:
        intent2_output['requestType']=999; intent2_output['type999_res']="未找到有效 JSON"
        return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}
    try: ai_json=json.loads(ai_output[si:ei+1])
    except:
        try: ai_json=json.loads(ai_output[si:ei+1].replace(", }","}").replace(", ]","]"))
        except Exception as e:
            intent2_output['requestType']=999; intent2_output['type999_res']=f"JSON 解析失败: {e}"
            return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}

    bdl=ai_json.get('batch_date',[])
    if not isinstance(bdl,list): bdl=[bdl] if bdl else []; ai_json['batch_date']=bdl
    if len(bdl)>3:
        intent2_output['requestType']=999; intent2_output['type999_res']="查询日期超过3个，请重新指定。"
        return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}
    ai_json['requestType']=2

    def fill_overview_fallback(pj,mt):
        ind=pj.get('ind_name',[]); types=pj.get('type',[]); lvls=pj.get('level',[])
        if not isinstance(ind,list): ind=[]
        if not isinstance(types,list): types=[types] if types else []
        if not isinstance(lvls,list): lvls=[lvls] if lvls else []
        if ind: return pj
        if not types:
            if isinstance(pj.get('batch_date'),list) and pj.get('batch_date'):
                vt=[k for k in mt if k in ('Revenue','Assets','Liabilities')]
                if vt: types=vt; lvls=["1","2"]; pj['type']=types; pj['level']=lvls
            else: return pj
        if not lvls: lvls=["1","2"]; pj['level']=lvls
        try: tgt={int(l) for l in lvls}
        except: tgt={1,2}; pj['level']=["1","2"]
        codes=[]
        for tk in types:
            for i in mt.get(tk,{}).get('indicators',[]):
                if isinstance(i,dict):
                    c,l=i.get('code'),i.get('level')
                    if c and l is not None:
                        try:
                            if int(l) in tgt: codes.append(c)
                        except: pass
        pj['ind_name']=codes; return pj
    try: ai_json=fill_overview_fallback(ai_json,mapping_table)
    except: pass

    def enrich_params(pj,mt):
        types=pj.get('type',[])
        if not isinstance(types,list): types=[types] if types else []
        try: li=sorted({int(l) for l in pj.get('level',[])})
        except: li=[]
        ac=set(pj.get('ind_name',[])); attrs=set(pj.get('attr_id',[])); enriched=set(ac)
        avc=set(); ava=set()
        for tk in types:
            if tk not in mt: continue
            tm=mt[tk]; indicators=tm.get('indicators',[])
            c2l={}; p2c={}
            for ind in indicators:
                if not isinstance(ind,dict): continue
                c=ind.get('code')
                if not c: continue
                avc.add(c)
                l=ind.get('level'); p=ind.get('parent_code')
                if l is not None:
                    try: c2l[c]=int(l)
                    except: pass
                if p: p2c.setdefault(p,[]).append(c)
            if li:
                for tl in li:
                    for pc in [c for c in list(enriched) if c2l.get(c,-1)<tl]:
                        for cc in p2c.get(pc,[]):
                            if c2l.get(cc)==tl: enriched.add(cc)
            avail=tm.get('available_metrics',{})
            mk=set(avail.keys()) if isinstance(avail,dict) else set(avail) if isinstance(avail,list) else set()
            ava.update(mk)
            if tk=='Revenue':
                req={k for k in mk if 'MTD' in k or 'YTD' in k}
                attrs.update(req if req else mk)
            elif tk in ('Assets','Liabilities'):
                bal_full={'MA_BAL','MA_MTD_BAL','MA_YTD_BAL'}
                hit=bal_full&mk; attrs.update(hit if hit else mk)
        vc=enriched&avc; pj['ind_name']=sorted(vc if vc else enriched)
        base_attrs={a for a in attrs if a not in ALL_EXTENDED_ATTRS}
        va=base_attrs&ava; pj['attr_id']=sorted(va if va else base_attrs)
        return pj
    try: ai_json=enrich_params(ai_json,mapping_table)
    except Exception as e:
        intent2_output['requestType']=999; intent2_output['type999_res']=f"参数补全异常: {e}"
        return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}

    def _get_code_level(code,mt):
        for tk in ('Revenue','Assets','Liabilities'):
            for ind in mt.get(tk,{}).get('indicators',[]):
                if ind.get('code')==code:
                    try: return int(ind.get('level',0))
                    except: return 0
        return 0

    def cap_data_volume(pj,mt):
        levels=pj.get('level',[]); dates=pj.get('batch_date',[])
        ind_names=pj.get('ind_name',[]); attrs=pj.get('attr_id',[]); types=pj.get('type',[])
        if not isinstance(levels,list): levels=[levels] if levels else []
        if not isinstance(dates,list): dates=[dates] if dates else []
        if not isinstance(ind_names,list): ind_names=[ind_names] if ind_names else []
        if not isinstance(types,list): types=[types] if types else []
        try: li=sorted(set(int(l) for l in levels if l))
        except: li=[1,2]
        n_d=len(dates); na=max(len(attrs),1)
        is_trend_query=n_d>=3
        em=TREND_MAX_LEVELS if is_trend_query else MAX_LEVELS
        while len(li)>em: li.pop()
        if len(li)<MIN_LEVELS and li and not is_trend_query:
            cand=min(li)+len(li)
            if cand<=6: li.append(cand)
            else:
                cu=min(li)-1
                if cu>=1: li.insert(0,cu)
            li=sorted(set(li))
        al=set(li)
        if ind_names: ind_names=[c for c in ind_names if _get_code_level(c,mt) in al]
        ni=len(ind_names) if ind_names else len(types)*len(li)*5
        if ni*n_d*na>MAX_CELLS_EST and len(li)>1:
            li.pop(); al=set(li)
            if ind_names: ind_names=[c for c in ind_names if _get_code_level(c,mt) in al]
        if ind_names and len(ind_names)>MAX_INDICATORS: ind_names=ind_names[:MAX_INDICATORS]
        pj['level']=[str(l) for l in li]; pj['ind_name']=ind_names
        return pj
    try: ai_json=cap_data_volume(ai_json,mapping_table)
    except: pass

    def smart_date_remap(pj):
        bd=pj.get('batch_date',[])
        if not isinstance(bd,list): bd=[bd] if bd else []
        attr_set=set(pj.get('attr_id',[])); pj.setdefault('_date_warnings',[])
        if attr_set&ALL_EXTENDED_ATTRS:
            validated=[]
            for s in bd:
                d=_parse_d(s)
                if d and _is_valid_api_date(d): validated.append(_fmt_d(d))
                elif d: pj['_date_warnings'].append(f"{_fmt_d(d)} 不在可用范围内")
            pj['batch_date']=validated if validated else bd; return pj
        d_objs=[(_parse_d(s),s) for s in bd]; n=len(d_objs)
        if n==1:
            d,orig=d_objs[0]
            if d is None: return pj
            if _is_valid_api_date(d): pj['batch_date']=[_fmt_d(d)]; return pj
            for shift,sk,am in [
                (1,'last_month',{'MA_BAL':'MA_L_M_BAL','MA_MTD_BAL':'MA_L_M_MTD_BAL'}),
                (12,'last_year',{'MA_BAL':'MA_L_Y_BAL','MA_MTD_BAL':'MA_L_Y_MTD_BAL','MA_YTD_BAL':'MA_L_Y_YTD_BAL'}),
            ]:
                anchor=_add_months(d,shift)
                if _is_valid_api_date(anchor):
                    na=set(); alias={}
                    for a in attr_set:
                        if a in am: na.add(am[a]); alias[am[a]]=a
                        else: na.add(a)
                    pj['batch_date']=[_fmt_d(anchor)]; pj['attr_id']=sorted(na)
                    pj['_comp_meta']={'mode':'date_shift','consolidated':False,
                        'anchor_date':_fmt_d(anchor),'display_date':_fmt_d(d),'shift':sk,'attr_alias':alias}
                    return pj
            pj['_date_warnings']=[f"{_fmt_d(d)} 超出可用数据范围"]
            pj['batch_date']=[_fmt_d(d)]; return pj
        if n==2:
            (d0,_),(d1,_)=d_objs
            if d0 is None or d1 is None: return pj
            de,dl=(d0,d1) if d0<=d1 else (d1,d0)
            lok=_is_valid_api_date(dl); eok=_is_valid_api_date(de)
            if not lok:
                pj['_date_warnings']=[f"当期日期 {_fmt_d(dl)} 不在可用范围内"]; return pj
            md_=(dl.year-de.year)*12+(dl.month-de.month); ck=None
            if md_==1 and _is_month_end(de) and _is_month_end(dl): ck='mom'
            elif md_==12 and de.month==dl.month: ck='yoy'
            elif de.month==12 and de.day==31 and dl.year==de.year+1: ck='vs_year_end'
            elif not eok:
                if md_==1: ck='mom'
                elif md_==12: ck='yoy'
                elif de.month==12 and de.day==31: ck='vs_year_end'
            if ck and ck in COMP_ATTR_CFG:
                cfg=COMP_ATTR_CFG[ck]; na=set(attr_set)
                for ca,ba in cfg['base_map'].items():
                    if ca in na: na.add(ba)
                na.update(cfg['extras'])
                if ck=='yoy': na.add('MA_L_YE_BAL'); na.add('MA_BAL')
                base_d=_calc_base_date(dl,ck)
                base_label=_fmt_d(base_d) if base_d else _fmt_d(de)
                pj['batch_date']=[_fmt_d(dl)]; pj['attr_id']=sorted(na)
                pj['_comp_meta']={'mode':ck,'consolidated':True,'current_date':_fmt_d(dl),
                    'base_date_label':base_label,'base_attr_map':cfg['base_map'],
                    'change_attrs':[a for a in cfg['extras'] if 'INCREMENT' in a],
                    'growth_attrs':[a for a in cfg['extras'] if 'GROWTH' in a],'comp_label':cfg['label']}
                return pj
            if eok: pj['batch_date']=[_fmt_d(de),_fmt_d(dl)]; return pj
            pj['batch_date']=[_fmt_d(dl)]
            pj['_date_warnings']=[f"基期 {_fmt_d(de)} 不可用且无法映射到预计算指标"]; return pj
        if n>=3:
            valid,warns=[],[]
            for d,_ in d_objs:
                if d and _is_valid_api_date(d): valid.append(d)
                elif d: warns.append(_fmt_d(d))
            pj['batch_date']=sorted([_fmt_d(d) for d in valid])
            if warns: pj['_date_warnings']=[f"以下日期不在可用范围内已移除: {', '.join(warns)}"]
            return pj
        return pj
    try: ai_json=smart_date_remap(ai_json)
    except: pass

    intent2_output.update(ai_json)
    return {"intent2_output":json.dumps(intent2_output,ensure_ascii=False)}