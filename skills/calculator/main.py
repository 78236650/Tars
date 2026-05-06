"""Calculator Skill - 安全的数学表达式求值"""
import ast
import math
import operator
from typing import Any, Dict

from tars.tools.base import BaseTool, ToolResult


# 允许的运算符
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# 允许的函数
FUNCTIONS = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "pow": math.pow, "log": math.log, "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "exp": math.exp, "floor": math.floor, "ceil": math.ceil,
    "pi": math.pi, "e": math.e,
}


def _safe_eval(node):
    """安全地对 AST 节点求值"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in FUNCTIONS:
            return FUNCTIONS[node.id]
        raise ValueError(f"未知符号: {node.id}")
    if isinstance(node, ast.BinOp):
        op = OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"不支持的运算: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"不支持的一元运算: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        func = _safe_eval(node.func)
        args = [_safe_eval(a) for a in node.args]
        return func(*args)
    raise ValueError(f"不支持的表达式: {type(node).__name__}")


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = "计算数学表达式。支持四则运算（+-*/），幂运算（**），以及 sqrt/log/sin/cos/exp/pi/e 等数学函数。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 '2 + 3 * 4' 或 'sqrt(16) + log(e)'",
            },
        },
        "required": ["expression"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        expression = kwargs.get("expression", "").strip()
        if not expression:
            return ToolResult(success=False, output="", error="请提供表达式")

        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree.body)
            return ToolResult(
                success=True,
                output=f"{expression} = {result}",
                metadata={"expression": expression, "result": result},
            )
        except ZeroDivisionError:
            return ToolResult(success=False, output="", error="除零错误")
        except (ValueError, SyntaxError, TypeError) as e:
            return ToolResult(success=False, output="", error=f"表达式错误: {e}")
