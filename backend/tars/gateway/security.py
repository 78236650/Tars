# TARS Gateway - Security Policy
# Layer 2: 安全策略

import os
import re
from typing import List, Tuple


class SecurityPolicy:
    """安全策略检查器"""

    def __init__(self):
        self.dangerous_patterns: List[re.Pattern] = [
            re.compile(r'rm\s+-rf\s+/\*?'),  # 危险删除
            re.compile(r'rm\s+-rf\s+/\s*$'),  # rm -rf /
            re.compile(r'chmod\s+777\s+/\w+'),  # 777 权限
            re.compile(r'DROP\s+TABLE', re.IGNORECASE),  # SQL DROP
            re.compile(r'DELETE\s+FROM', re.IGNORECASE),  # SQL DELETE
            re.compile(r'exec\s*\(.*\$'),  # 动态代码执行
            re.compile(r'eval\s*\('),  # eval
            re.compile(r'sudo\s+rm\s+-rf'),  # sudo rm
            re.compile(r'format\s+\w+:'),  # 格式化磁盘
        ]
        
        self.blocked_paths: List[str] = [
            '/etc',
            '/var',
            '/root',
            '/sys',
            '/proc',
            '/boot',
            '/dev'
        ]
        
        self._load_config()

    def _load_config(self):
        """从环境变量加载配置"""
        blocked = os.getenv("TARS_BLOCKED_PATHS")
        if blocked:
            self.blocked_paths.extend(blocked.split(','))

    def check_command(self, command: str) -> Tuple[bool, str]:
        """检查命令是否安全
        返回: (是否安全, 错误信息)
        """
        command_lower = command.lower()
        
        for pattern in self.dangerous_patterns:
            if pattern.search(command):
                return False, f"Security blocked: dangerous pattern '{pattern.pattern}' detected"
        
        return True, ""

    def check_path(self, path: str) -> Tuple[bool, str]:
        """检查路径是否可访问
        返回: (是否可访问, 错误信息)
        """
        abs_path = os.path.abspath(os.path.expanduser(path))
        
        for blocked in self.blocked_paths:
            if abs_path.startswith(blocked):
                return False, f"Security blocked: path '{blocked}' is protected"
        
        return True, ""

    def check_content(self, content: str) -> Tuple[bool, str]:
        """检查内容是否包含危险操作
        返回: (是否安全, 错误信息)
        """
        if len(content) > 100000:  # 限制内容大小
            return False, "Content too large"
        
        dangerous_strings = [
            'eval(',
            'exec(',
            '__import__(',
            'subprocess.call',
            'os.system'
        ]
        
        for dangerous in dangerous_strings:
            if dangerous in content:
                return False, f"Security blocked: dangerous pattern '{dangerous}' detected"
        
        return True, ""
