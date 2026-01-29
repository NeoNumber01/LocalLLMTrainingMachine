"""
代码验证模块
AST 解析、编译检查、危险代码检测
"""

import ast
import re
import py_compile
import tempfile
import os
import logging
from typing import Optional, List, Tuple

from .types import ErrorType

logger = logging.getLogger(__name__)


class CodeValidator:
    """
    代码验证器
    
    功能：
    1. AST 语法检查
    2. py_compile 编译门禁
    3. 危险代码检测
    4. 接口合规检查
    """
    
    # 默认危险模式
    DEFAULT_DANGEROUS_PATTERNS = [
        r'\beval\s*\(',
        r'\bexec\s*\(',
        r'\bcompile\s*\(',
        r'\bopen\s*\(',
        r'\bos\.system\s*\(',
        r'\bos\.popen\s*\(',
        r'\bsubprocess\.',
        r'\b__import__\s*\(',
        r'\bimportlib\.',
        r'\bglobals\s*\(\)',
        r'\blocals\s*\(\)',
        r'\bsetattr\s*\(',
        r'\bgetattr\s*\(',
        r'\bdelattr\s*\(',
        r'\b__builtins__',
    ]
    
    def __init__(self, dangerous_patterns: Optional[List[str]] = None):
        """
        初始化验证器
        
        Args:
            dangerous_patterns: 危险代码模式列表
        """
        patterns = dangerous_patterns or self.DEFAULT_DANGEROUS_PATTERNS
        self._dangerous_patterns = [re.compile(p) for p in patterns]
    
    def validate(self, code: str, function_name: str = "solve") -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        完整验证代码
        
        Args:
            code: 待验证代码
            function_name: 期望的函数名
            
        Returns:
            (是否通过, 错误类型, 错误消息)
        """
        # 1. AST 语法检查
        valid, error_type, error_msg = self.check_syntax(code)
        if not valid:
            return False, error_type, error_msg
        
        # 2. 编译检查
        valid, error_type, error_msg = self.check_compile(code)
        if not valid:
            return False, error_type, error_msg
        
        # 3. 危险代码检测
        valid, error_type, error_msg = self.check_dangerous(code)
        if not valid:
            return False, error_type, error_msg
        
        # 4. 接口检查
        valid, error_type, error_msg = self.check_interface(code, function_name)
        if not valid:
            return False, error_type, error_msg
        
        return True, None, None
    
    def check_syntax(self, code: str) -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        AST 语法检查
        """
        try:
            ast.parse(code)
            return True, None, None
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            if "indent" in str(e.msg).lower():
                return False, ErrorType.INDENTATION_ERROR, error_msg
            return False, ErrorType.SYNTAX_ERROR, error_msg
        except Exception as e:
            return False, ErrorType.SYNTAX_ERROR, str(e)
    
    def check_compile(self, code: str) -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        py_compile 编译检查
        """
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_path = f.name
            
            try:
                py_compile.compile(temp_path, doraise=True)
                return True, None, None
            finally:
                os.unlink(temp_path)
                
        except py_compile.PyCompileError as e:
            return False, ErrorType.SYNTAX_ERROR, str(e)
        except Exception as e:
            return False, ErrorType.SYNTAX_ERROR, str(e)
    
    def check_dangerous(self, code: str) -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        危险代码检测
        """
        for pattern in self._dangerous_patterns:
            match = pattern.search(code)
            if match:
                return False, ErrorType.DANGEROUS_CODE, f"检测到危险代码: {match.group()}"
        return True, None, None
    
    def check_interface(self, code: str, function_name: str = "solve") -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        检查函数接口是否存在
        """
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    return True, None, None
            return False, ErrorType.INTERFACE_ERROR, f"未找到函数 {function_name}"
        except SyntaxError:
            # 语法错误已在前面检查，这里只关注接口
            pattern = rf'def\s+{function_name}\s*\('
            if re.search(pattern, code):
                return True, None, None
            return False, ErrorType.INTERFACE_ERROR, f"未找到函数 {function_name}"
    
    def get_syntax_error_info(self, code: str) -> Optional[dict]:
        """
        获取语法错误详细信息
        
        Returns:
            包含 lineno, offset, msg, text 的字典
        """
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return {
                "lineno": e.lineno,
                "offset": e.offset,
                "msg": e.msg,
                "text": e.text,
            }
    
    def analyze_code_quality(self, code: str) -> dict:
        """
        分析代码质量
        """
        lines = code.split('\n')
        
        # 检查是否有额外 I/O
        has_print = bool(re.search(r'\bprint\s*\(', code))
        has_input = bool(re.search(r'\binput\s*\(', code))
        
        # 检查函数定义
        has_function = bool(re.search(r'\bdef\s+\w+\s*\(', code))
        
        # 检查调试语句
        has_debug = bool(re.search(r'#\s*debug|print\s*\(\s*["\']debug', code, re.IGNORECASE))
        
        # 统计
        return {
            "code_length": len(code),
            "line_count": len(lines),
            "has_print": has_print,
            "has_input": has_input,
            "has_function": has_function,
            "has_debug": has_debug,
            "extra_io": has_print or has_input,
        }
