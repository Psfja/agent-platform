"""对提交的 CSS 文本执行设计审计，输出命中项与按 Fix Priority 排序的建议。"""
import json
import re
import sys

payload = json.load(sys.stdin)
css = str(payload.get("css", ""))
html = str(payload.get("html", ""))
framework = str(payload.get("framework", "unknown"))

PRIORITY = ["typography", "color", "interaction", "layout", "components", "states", "polish"]


def hit(priority: str, rule: str, found: bool) -> dict:
    return {"priority": priority, "rule": rule, "hit": found}


checks = [
    hit("typography", "tabular-nums 用于数据密集界面", "tabular-nums" in css),
    hit("typography", "标题存在 letter-spacing 收紧", bool(re.search(r"h1[^{]*\{[^}]*letter-spacing:\s*-", css))),
    hit("typography", "标题使用 text-wrap: balance", "text-wrap" in css and "balance" in css),
    hit("color", "强调色饱和度可控（存在单一品牌变量）", bool(re.search(r"--primary\s*:", css))),
    hit("color", "阴影带背景色相（非纯黑）", bool(re.search(r"rgba\((2[0-9]|1[0-9]),\s*(3[0-9]|2[0-9]),\s*5[0-9]", css))),
    hit("color", "未使用纯黑背景", "#000" not in css.replace("#0000", "") and "background:#000" not in css),
    hit("interaction", "按钮存在 :hover", ":hover" in css),
    hit("interaction", "按钮存在 :active 按压反馈", ":active" in css),
    hit("interaction", "存在 :focus-visible 焦点环", ":focus-visible" in css),
    hit("interaction", "交互元素有过渡", "transition" in css),
    hit("interaction", "支持 prefers-reduced-motion", "prefers-reduced-motion" in css),
    hit("layout", "存在 max-width 容器约束", bool(re.search(r"max-width:\s*1[2-4]\d\dpx", css))),
    hit("layout", "未使用 100vh 全屏段（用 100dvh）", "100vh" not in css.replace("100dvh", "") or "100dvh" in css),
    hit("components", "z-index 建立令牌体系", bool(re.search(r"--z-[a-z-]+\s*:", css))),
    hit("states", "存在骨架屏/shimmer 动画", "shimmer" in css or "skeleton" in css),
    hit("states", "空状态有样式（非裸白）", bool(re.search(r"empty", css))),
    hit("polish", "自定义选区颜色", "::selection" in css),
    hit("polish", "圆角有层级（内小外大）", css.count("border-radius") >= 5),
]

result = {priority: [item["rule"] for item in checks if item["priority"] == priority and item["hit"]] for priority in PRIORITY}
missing = [{"priority": item["priority"], "rule": item["rule"]} for item in checks if not item["hit"]]

print(json.dumps({
    "framework": framework,
    "cssBytes": len(css),
    "checksTotal": len(checks),
    "passed": sum(1 for item in checks if item["hit"]),
    "passedByPriority": result,
    "missingByPriority": missing,
    "fixOrder": ["字体与数字排版", "调色板清理", "hover/active/focus", "布局与间距", "组件模式", "loading/empty/error 状态", "排版精修"],
}, ensure_ascii=False, indent=2))
