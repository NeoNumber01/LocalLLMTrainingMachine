"""
Code Validation Module
AST parsing, compilation check, dangerous code detection
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
    Code Validator
    
    Features:
    1. AST syntax check
    2. py_compile compilation gate
    3. Dangerous code detection
    4. Interface compliance check
    """
    
    # Default dangerous patterns
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
        Initialize validator
        
        Args:
            dangerous_patterns: List of dangerous code patterns
        """
        patterns = dangerous_patterns or self.DEFAULT_DANGEROUS_PATTERNS
        self._dangerous_patterns = [re.compile(p) for p in patterns]
    
    def validate(self, code: str, function_name: str = "solve") -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        Complete code validation
        
        Args:
            code: Code to validate
            function_name: Expected function name
            
        Returns:
            (passed, error_type, error_message)
        """
        # 1. AST syntax check
        valid, error_type, error_msg = self.check_syntax(code)
        if not valid:
            return False, error_type, error_msg
        
        # 2. Compilation check
        valid, error_type, error_msg = self.check_compile(code)
        if not valid:
            return False, error_type, error_msg
        
        # 3. Dangerous code detection
        valid, error_type, error_msg = self.check_dangerous(code)
        if not valid:
            return False, error_type, error_msg
        
        # 4. Interface check
        valid, error_type, error_msg = self.check_interface(code, function_name)
        if not valid:
            return False, error_type, error_msg
        
        return True, None, None
    
    def check_syntax(self, code: str) -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        AST syntax check
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
        py_compile compilation check
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
        Dangerous code detection
        """
        for pattern in self._dangerous_patterns:
            match = pattern.search(code)
            if match:
                return False, ErrorType.DANGEROUS_CODE, f"Dangerous code detected: {match.group()}"
        return True, None, None
    
    def check_interface(self, code: str, function_name: str = "solve") -> Tuple[bool, Optional[ErrorType], Optional[str]]:
        """
        Check if function interface exists
        """
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    return True, None, None
            return False, ErrorType.INTERFACE_ERROR, f"Function {function_name} not found"
        except SyntaxError:
            # Syntax error already checked before, only focus on interface here
            pattern = rf'def\s+{function_name}\s*\('
            if re.search(pattern, code):
                return True, None, None
            return False, ErrorType.INTERFACE_ERROR, f"Function {function_name} not found"
    
    def get_syntax_error_info(self, code: str) -> Optional[dict]:
        """
        Get syntax error details
        
        Returns:
            Dictionary containing lineno, offset, msg, text
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
        Analyze code quality
        """
        lines = code.split('\n')
        
        # Check if there is extra I/O
        has_print = bool(re.search(r'\bprint\s*\(', code))
        has_input = bool(re.search(r'\binput\s*\(', code))
        
        # Check function definition
        has_function = bool(re.search(r'\bdef\s+\w+\s*\(', code))
        
        # Check debug statements
        has_debug = bool(re.search(r'#\s*debug|print\s*\(\s*["\']debug', code, re.IGNORECASE))
        
        # Statistics
        return {
            "code_length": len(code),
            "line_count": len(lines),
            "has_print": has_print,
            "has_input": has_input,
            "has_function": has_function,
            "has_debug": has_debug,
            "extra_io": has_print or has_input,
        }
