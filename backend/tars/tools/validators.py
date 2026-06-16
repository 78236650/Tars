"""TARS Tools - 执行结果验证层
提供对工具执行结果的轻量级静态校验，防止无意义异常引发幻觉。
"""
from typing import Any, Dict, Optional, Tuple
from .base import ToolResult

class ToolResultValidator:
    """工具结果验证器"""
    
    @classmethod
    def validate(cls, tool_name: str, arguments: Dict[str, Any], result: ToolResult) -> Tuple[bool, Optional[str]]:
        """
        验证工具执行结果。
        返回: (is_valid, correction_prompt)
        如果 is_valid 为 False，修正提示(correction_prompt)将被附加到错误信息中反馈给 LLM。
        """
        if not result.success:
            # 对于已经失败的调用，我们尝试优化错误提示
            return cls._validate_failed_result(tool_name, arguments, result)
            
        # 根据不同工具类型执行校验
        if tool_name == "shell" or tool_name == "command":
            return cls._validate_shell(arguments, result)
        elif tool_name == "python_exec":
            return cls._validate_python(arguments, result)
        elif tool_name == "web_search":
            return cls._validate_web_search(arguments, result)
            
        return True, None
        
    @classmethod
    def _validate_failed_result(cls, tool_name: str, arguments: Dict[str, Any], result: ToolResult) -> Tuple[bool, Optional[str]]:
        error_msg = result.error or ""
        error_msg_lower = error_msg.lower()
        
        # 常见错误类型优化提示
        if "command not found" in error_msg_lower:
            return False, "命令未找到。请检查是否拼写错误，或考虑使用其他替代命令/工具。"
        elif "permission denied" in error_msg_lower:
            return False, "权限被拒绝。请不要尝试执行需要 sudo 权限的操作，或检查文件路径权限。"
        elif "syntaxerror" in error_msg_lower or "nameerror" in error_msg_lower:
            return False, "代码存在语法错误或未定义的变量。请仔细检查代码拼写并修复后再试。"
            
        return True, None

    @classmethod
    def _validate_shell(cls, arguments: Dict[str, Any], result: ToolResult) -> Tuple[bool, Optional[str]]:
        output = str(result.output)
        output_lower = output.lower()
        
        # 检查看似成功但实际上是错误的情况（例如返回了 stderr 但 success 仍为 true）
        if "command not found" in output_lower:
            return False, "命令执行失败（命令未找到）。请检查命令拼写或是否存在于环境中。"
            
        # 检查没有任何输出的情况（对于预期有输出的命令）
        cmd = arguments.get("command", "")
        if (cmd.startswith("ls") or cmd.startswith("cat") or cmd.startswith("grep") or cmd.startswith("echo")) and not output.strip():
            # 可能是空目录或空文件，通常算有效，但不一定有帮助
            # 对于 cat/grep 返回空，给出温和提示
            if cmd.startswith("grep"):
                return False, "命令执行成功，但没有找到匹配的结果。你可以尝试放宽搜索条件。"
                
        return True, None

    @classmethod
    def _validate_python(cls, arguments: Dict[str, Any], result: ToolResult) -> Tuple[bool, Optional[str]]:
        output = str(result.output)
        
        if "Traceback (most recent call last):" in output:
            return False, "Python 执行抛出了异常。请阅读 Traceback 信息，修复代码错误后重试。"
            
        if not output.strip():
            return False, "Python 代码执行成功，但没有任何输出(stdout)。如果你希望查看变量值，请使用 print() 打印出来。"
            
        return True, None

    @classmethod
    def _validate_web_search(cls, arguments: Dict[str, Any], result: ToolResult) -> Tuple[bool, Optional[str]]:
        output = str(result.output)
        
        if not output.strip() or output == "[]" or output == "{}":
            return False, "网页搜索没有返回任何结果。请尝试使用更简单的关键词或不同的关键词重新搜索。"
            
        return True, None
