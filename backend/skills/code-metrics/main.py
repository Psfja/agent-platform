import json
import re
import sys

payload = json.load(sys.stdin)
code = str(payload.get("code", ""))
lines = code.splitlines()
non_empty = [line for line in lines if line.strip()]
functions = len(re.findall(r"^\s*(?:async\s+)?def\s+\w+|\bfunction\s+\w+|\w+\s*=\s*\([^)]*\)\s*=>", code, re.M))
classes = len(re.findall(r"^\s*class\s+\w+", code, re.M))
branches = len(re.findall(r"\b(if|elif|else|for|while|case|catch|except)\b", code))
comments = len([line for line in lines if line.strip().startswith(("#", "//", "/*", "*"))])
print(json.dumps({
    "language": payload.get("language", "unknown"),
    "totalLines": len(lines),
    "nonEmptyLines": len(non_empty),
    "functions": functions,
    "classes": classes,
    "branchPoints": branches,
    "commentRatio": round(comments / max(1, len(non_empty)), 3),
    "reviewRisk": "high" if branches > 30 else "medium" if branches > 15 else "low"
}, ensure_ascii=False))
