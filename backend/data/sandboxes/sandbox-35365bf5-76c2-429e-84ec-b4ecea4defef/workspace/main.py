import json
import re
import sys

payload = json.load(sys.stdin)
text = str(payload.get("requirement", "")).strip()
role_words = ["员工", "管理员", "审批人", "HR", "负责人", "用户", "客户", "供应商"]
feature_words = ["申请", "审批", "导出", "查询", "统计", "通知", "配置", "登录", "看板", "上传"]
roles = [word for word in role_words if word.lower() in text.lower()]
features = [word for word in feature_words if word in text]
questions = []
if len(text) < 40:
    questions.append("请补充更完整的业务流程和成功标准。")
if not roles:
    questions.append("该系统包含哪些用户角色，各自拥有什么权限？")
if not any(token in text for token in ["秒", "分钟", "并发", "安全", "性能"]):
    questions.append("是否有性能、安全或并发方面的非功能要求？")
result = {
    "projectName": payload.get("project_name", "未命名项目"),
    "summary": re.split(r"[。！？]", text)[0][:120],
    "roles": roles,
    "capabilities": features,
    "clarificationQuestions": questions,
    "completenessScore": max(35, min(96, 45 + len(text) // 3 + len(roles) * 4 + len(features) * 3)),
    "strategy": "保留原始需求，缺失信息通过澄清问题补齐。"
}
print(json.dumps(result, ensure_ascii=False))
