import json
import sys

payload = json.load(sys.stdin)
modules = [str(item) for item in payload.get("changed_modules", [])]
risk = str(payload.get("risk_level", "low"))
suites = []
for module in modules:
    suites.append({"module": module, "tests": ["新增功能正向验证", "已有接口兼容性", "异常与边界条件"]})
suites.append({"module": "cross-module", "tests": ["核心业务 E2E", "角色权限回归", "审计日志完整性"]})
if risk in {"medium", "high"}:
    suites.append({"module": "risk-protection", "tests": ["数据迁移验证", "性能基线对比", "版本回滚演练"]})
print(json.dumps({
    "riskLevel": risk,
    "suiteCount": len(suites),
    "estimatedCases": sum(len(item["tests"]) for item in suites) * 4,
    "suites": suites,
    "gate": "全部 P0/P1 用例通过且无已有功能回归后允许部署"
}, ensure_ascii=False))
