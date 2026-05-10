import json


def main(args: dict) -> dict:
    """
    兼容原知识问答链路的 type999 输出整理节点。
    """
    question_analysis = {"type999_res": "Cannot find type999 res"}
    for key in ("type999_res", "type2_redirect_res", "type1_redirect_res"):
        value = args.get(key)
        if value:
            question_analysis["type999_res"] = value
            break
    question_analysis["requestType"] = "999"
    return {"question_analysis": json.dumps(question_analysis, ensure_ascii=False)}
