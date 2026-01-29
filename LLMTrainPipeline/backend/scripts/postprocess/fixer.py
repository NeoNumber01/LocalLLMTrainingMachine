"""
规则修复模块
基于规则的自动代码修复，参考 LeoLLM 的成功实现
"""

import ast
import re
import logging
from typing import Optional, List, Tuple

from .types import ErrorType
from .import_registry import get_required_imports, generate_import_statements

logger = logging.getLogger(__name__)


class RuleFixer:
    """
    规则修复器
    
    实现高频错误的自动修复策略：
    1. 缩进错误修复
    2. 缺失 import 补全
    3. 接口不符合修复
    4. 空数组崩溃兜底
    5. 递归保护
    6. 语法错误修复（括号、冒号等）
    """
    
    def __init__(self):
        """初始化修复器"""
        self._fix_history: List[str] = []
    
    def fix(self, code: str, error_type: ErrorType, error_message: str,
            signature: str = "def solve(nums: list[int]) -> int:") -> Tuple[str, List[str]]:
        """
        根据错误类型尝试修复代码
        
        Args:
            code: 待修复代码
            error_type: 错误类型
            error_message: 错误消息
            signature: 期望的函数签名
            
        Returns:
            (修复后的代码, 应用的修复列表)
        """
        self._fix_history = []
        
        # 根据错误类型选择修复策略
        if error_type == ErrorType.SYNTAX_ERROR:
            code = self._fix_syntax_error(code, error_message, signature)
        elif error_type == ErrorType.INDENTATION_ERROR:
            code = self._fix_indentation(code, error_message)
        elif error_type == ErrorType.NAME_ERROR:
            code = self._fix_name_error(code, error_message)
        elif error_type == ErrorType.IMPORT_ERROR:
            code = self._fix_import_error(code, error_message)
        elif error_type == ErrorType.INDEX_ERROR:
            code = self._fix_index_error(code, signature)
        elif error_type == ErrorType.RECURSION_ERROR:
            code = self._fix_recursion_error(code)
        elif error_type == ErrorType.INTERFACE_ERROR:
            code = self._fix_interface_error(code, signature)
        
        return code, self._fix_history
    
    def fix_all(self, code: str, signature: str = "def solve(nums: list[int]) -> int:") -> Tuple[str, List[str]]:
        """
        应用所有可能的预防性修复
        
        Args:
            code: 待修复代码
            signature: 期望的函数签名
            
        Returns:
            (修复后的代码, 应用的修复列表)
        """
        self._fix_history = []
        
        # 1. 缩进规范化
        code = self._normalize_indentation(code)
        
        # 2. 语法修复
        code = self._fix_syntax_iterative(code, signature)
        
        # 3. 自动 import
        code = self._auto_import(code)
        
        # 4. 空输入兜底
        code = self._add_empty_input_guard(code, signature)
        
        # 5. 递归保护
        code = self._add_recursion_guard(code)
        
        return code, self._fix_history
    
    # =========================================================================
    # 语法错误修复
    # =========================================================================
    def _fix_syntax_error(self, code: str, error_message: str, signature: str) -> str:
        """修复语法错误"""
        return self._fix_syntax_iterative(code, signature, max_attempts=3)
    
    def _fix_syntax_iterative(self, code: str, signature: str, max_attempts: int = 3) -> str:
        """迭代修复语法错误（参考 LeoLLM Phase 12）"""
        for attempt in range(max_attempts):
            try:
                ast.parse(code)
                return code  # 代码有效
            except SyntaxError as e:
                logger.debug(f"语法修复尝试 {attempt + 1}: {e}")
                code = self._attempt_syntax_fix(code, e, signature)
        
        return code
    
    def _attempt_syntax_fix(self, code: str, error: SyntaxError, signature: str) -> str:
        """
        根据语法错误尝试修复（参考 LeoLLM）
        """
        lines = code.split('\n')
        error_msg = str(error).lower()
        
        if error.lineno is None:
            return code
        
        line_idx = error.lineno - 1
        if line_idx >= len(lines):
            return code
        
        problem_line = lines[line_idx]
        
        # 缺少冒号
        if 'expected ":"' in str(error) or "expected ':'" in str(error):
            if not problem_line.rstrip().endswith(':'):
                lines[line_idx] = problem_line.rstrip() + ':'
                self._fix_history.append("添加缺失的冒号")
                return '\n'.join(lines)
        
        # 签名语法错误
        if 'invalid syntax' in error_msg and 'def solve' in problem_line:
            expected_sig = signature.strip()
            if not expected_sig.endswith(':'):
                expected_sig += ':'
            lines[line_idx] = expected_sig
            self._fix_history.append("修复函数签名")
            return '\n'.join(lines)
        
        # 意外的 EOF - 括号不平衡
        if 'unexpected eof' in error_msg or 'eof while scanning' in error_msg:
            open_count = code.count('(') - code.count(')')
            close_count = code.count('[') - code.count(']')
            brace_count = code.count('{') - code.count('}')
            
            suffix = ')' * max(0, open_count)
            suffix += ']' * max(0, close_count)
            suffix += '}' * max(0, brace_count)
            
            if suffix:
                code = code.rstrip() + suffix
                self._fix_history.append(f"补全括号: {suffix}")
                return code
            
            # 检查未闭合字符串
            single_quotes = code.count("'") - code.count("\\'")
            double_quotes = code.count('"') - code.count('\\"')
            
            if single_quotes % 2 != 0:
                code = code.rstrip() + "'"
                self._fix_history.append("闭合单引号字符串")
                return code
            if double_quotes % 2 != 0:
                code = code.rstrip() + '"'
                self._fix_history.append("闭合双引号字符串")
                return code
        
        # 缩进错误
        if 'indent' in error_msg:
            if line_idx > 0:
                prev_line = lines[line_idx - 1]
                prev_indent = len(prev_line) - len(prev_line.lstrip())
                current_stripped = problem_line.lstrip()
                
                if prev_line.rstrip().endswith(':'):
                    lines[line_idx] = ' ' * (prev_indent + 4) + current_stripped
                else:
                    lines[line_idx] = ' ' * prev_indent + current_stripped
                
                self._fix_history.append(f"修复第 {error.lineno} 行缩进")
                return '\n'.join(lines)
        
        # 未终结字符串
        if 'unterminated string' in error_msg:
            if problem_line.count('"') % 2 != 0:
                lines[line_idx] = problem_line.rstrip() + '"'
                self._fix_history.append("闭合字符串")
                return '\n'.join(lines)
            if problem_line.count("'") % 2 != 0:
                lines[line_idx] = problem_line.rstrip() + "'"
                self._fix_history.append("闭合字符串")
                return '\n'.join(lines)
        
        # 不匹配的括号
        if 'unmatched' in error_msg:
            if ')' in problem_line and '(' not in problem_line:
                lines[line_idx] = problem_line.replace(')', '', 1)
                self._fix_history.append("移除多余的 )")
                return '\n'.join(lines)
            if ']' in problem_line and '[' not in problem_line:
                lines[line_idx] = problem_line.replace(']', '', 1)
                self._fix_history.append("移除多余的 ]")
                return '\n'.join(lines)
            if '}' in problem_line and '{' not in problem_line:
                lines[line_idx] = problem_line.replace('}', '', 1)
                self._fix_history.append("移除多余的 }")
                return '\n'.join(lines)
        
        # 无效字符
        if 'invalid character' in error_msg:
            cleaned = ''.join(c if c.isascii() and (c.isprintable() or c in '\t\n') else '' for c in problem_line)
            lines[line_idx] = cleaned
            self._fix_history.append("移除无效字符")
            return '\n'.join(lines)
        
        return code
    
    # =========================================================================
    # 缩进修复
    # =========================================================================
    def _fix_indentation(self, code: str, error_message: str) -> str:
        """修复缩进错误"""
        code = self._normalize_indentation(code)
        return code
    
    def _normalize_indentation(self, code: str) -> str:
        """规范化缩进"""
        lines = code.split('\n')
        result = []
        
        for line in lines:
            if not line.strip():
                result.append('')
                continue
            
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]
            
            # Tab 转 4 空格
            original_leading = leading
            leading = leading.replace('\t', '    ')
            
            # 2 空格转 4 空格
            space_count = len(leading)
            if space_count > 0 and space_count % 2 == 0 and space_count % 4 != 0:
                leading = ' ' * (space_count * 2)
            
            if leading != original_leading:
                if "规范化缩进" not in self._fix_history:
                    self._fix_history.append("规范化缩进")
            
            result.append(leading + stripped)
        
        return '\n'.join(result)
    
    # =========================================================================
    # Name Error 修复（自动 import）
    # =========================================================================
    def _fix_name_error(self, code: str, error_message: str) -> str:
        """修复 NameError - 自动 import"""
        # 从错误消息中提取未定义的名称
        match = re.search(r"name '(\w+)' is not defined", error_message)
        if match:
            undefined_name = match.group(1)
            code = self._add_import_for_name(code, undefined_name)
        else:
            code = self._auto_import(code)
        return code
    
    def _add_import_for_name(self, code: str, name: str) -> str:
        """为特定名称添加 import"""
        from .import_registry import IMPORT_REGISTRY
        
        if name in IMPORT_REGISTRY:
            module, style = IMPORT_REGISTRY[name]
            if style == "from":
                import_stmt = f"from {module} import {name}"
            else:
                import_stmt = f"import {module}"
            
            # 避免重复添加
            if import_stmt not in code:
                code = import_stmt + "\n" + code
                self._fix_history.append(f"添加 import: {import_stmt}")
        
        return code
    
    def _auto_import(self, code: str) -> str:
        """自动补全所有缺失的 import"""
        required = get_required_imports(code)
        
        if not required:
            return code
        
        import_block = generate_import_statements(required)
        
        if import_block:
            # 检查已有 import
            lines = code.split('\n')
            insert_pos = 0
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(('import ', 'from ')):
                    insert_pos = i + 1
                elif stripped and not stripped.startswith('#'):
                    break
            
            lines.insert(insert_pos, import_block)
            if insert_pos > 0 and lines[insert_pos - 1].strip():
                lines.insert(insert_pos, '')
            
            code = '\n'.join(lines)
            self._fix_history.append(f"自动 import: {', '.join(required)}")
        
        return code
    
    # =========================================================================
    # Import Error 修复
    # =========================================================================
    def _fix_import_error(self, code: str, error_message: str) -> str:
        """修复 ImportError"""
        # 尝试移除有问题的 import
        match = re.search(r"No module named '(\w+)'", error_message)
        if match:
            bad_module = match.group(1)
            lines = code.split('\n')
            new_lines = []
            for line in lines:
                if f"import {bad_module}" not in line and f"from {bad_module}" not in line:
                    new_lines.append(line)
                else:
                    self._fix_history.append(f"移除无效 import: {bad_module}")
            code = '\n'.join(new_lines)
        return code
    
    # =========================================================================
    # Index Error 修复（空输入兜底）
    # =========================================================================
    def _fix_index_error(self, code: str, signature: str) -> str:
        """修复 IndexError - 添加空输入检查"""
        return self._add_empty_input_guard(code, signature)
    
    def _add_empty_input_guard(self, code: str, signature: str) -> str:
        """添加空输入检查"""
        # 检查是否已有空输入检查
        if "if not nums" in code or "if len(nums) == 0" in code or "if nums == []" in code:
            return code
        
        # 从签名中提取参数名和返回类型
        param_name = "nums"
        default_return = "0"
        
        # 尝试从签名提取参数名
        param_match = re.search(r'def\s+\w+\s*\((\w+)', signature)
        if param_match:
            param_name = param_match.group(1)
        
        # 尝试从签名提取返回类型
        return_match = re.search(r'->\s*(\w+)', signature)
        if return_match:
            return_type = return_match.group(1)
            if return_type == "int":
                default_return = "0"
            elif return_type == "float":
                default_return = "0.0"
            elif return_type == "str":
                default_return = '""'
            elif return_type == "bool":
                default_return = "False"
            elif return_type in ("list", "List"):
                default_return = "[]"
            elif return_type in ("dict", "Dict"):
                default_return = "{}"
        
        # 找到函数体开始位置并插入检查
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') and ':' in line:
                # 找到函数定义后的第一个非空行
                for j in range(i + 1, len(lines)):
                    if lines[j].strip():
                        indent = len(lines[j]) - len(lines[j].lstrip())
                        guard = ' ' * indent + f"if not {param_name}: return {default_return}"
                        lines.insert(j, guard)
                        self._fix_history.append(f"添加空输入检查: if not {param_name}")
                        return '\n'.join(lines)
                break
        
        return code
    
    # =========================================================================
    # 递归保护
    # =========================================================================
    def _fix_recursion_error(self, code: str) -> str:
        """修复 RecursionError"""
        return self._add_recursion_guard(code)
    
    def _add_recursion_guard(self, code: str) -> str:
        """添加递归限制"""
        if "setrecursionlimit" in code:
            return code
        
        # 检测是否有递归
        if not self._has_recursion(code):
            return code
        
        # 添加递归限制
        code = "import sys\nsys.setrecursionlimit(10**7)\n\n" + code
        self._fix_history.append("添加递归限制: setrecursionlimit(10**7)")
        
        return code
    
    def _has_recursion(self, code: str) -> bool:
        """检测代码是否包含递归"""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_name = node.name
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            if isinstance(child.func, ast.Name) and child.func.id == func_name:
                                return True
        except SyntaxError:
            # 使用简单启发式
            pattern = r'def\s+(\w+).*?\1\s*\('
            return bool(re.search(pattern, code, re.DOTALL))
        return False
    
    # =========================================================================
    # 接口修复
    # =========================================================================
    def _fix_interface_error(self, code: str, signature: str) -> str:
        """修复接口不符合"""
        expected_sig = signature.strip()
        if not expected_sig.endswith(':'):
            expected_sig += ':'
        
        # 检查是否有 solve 函数
        if 'def solve' not in code:
            # 尝试找其他函数并包装
            func_match = re.search(r'def\s+(\w+)\s*\([^)]*\)', code)
            if func_match:
                other_func = func_match.group(1)
                wrapper = f"{expected_sig}\n    return {other_func}(nums)\n\n"
                code = wrapper + code
                self._fix_history.append(f"包装 {other_func} 为 solve")
            else:
                # 没有函数，创建占位
                code = f"{expected_sig}\n    pass\n\n" + code
                self._fix_history.append("创建 solve 占位函数")
        
        return code
    
    # =========================================================================
    # 智能回退生成（参考 LeoLLM Phase 14）
    # =========================================================================
    def generate_fallback(self, code: str, signature: str) -> str:
        """
        当所有修复失败时，尝试生成一个可运行的回退代码
        """
        # 首先检查代码是否有效
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            logger.warning("代码仍无效，尝试生成回退")
        
        # 尝试提取 return 逻辑
        returns = self._extract_return_expressions(code)
        if returns:
            fallback = self._build_from_returns(signature, returns)
            try:
                ast.parse(fallback)
                self._fix_history.append("使用 return 逻辑生成回退代码")
                return fallback
            except SyntaxError:
                pass
        
        # 最后手段：返回类型默认值
        return self._type_based_default(signature)
    
    def _extract_return_expressions(self, code: str) -> List[str]:
        """提取 return 表达式"""
        returns = []
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped.startswith('return '):
                expr = stripped[7:].strip()
                if expr and expr != 'None':
                    returns.append(expr)
        return returns
    
    def _build_from_returns(self, signature: str, returns: List[str]) -> str:
        """从 return 表达式构建代码"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        
        first_return = returns[0]
        return f"{sig}\n    return {first_return}\n"
    
    def _type_based_default(self, signature: str) -> str:
        """根据返回类型生成默认实现"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        
        # 解析返回类型
        return_match = re.search(r'->\s*([^:]+):', sig)
        if return_match:
            return_type = return_match.group(1).strip()
            if 'int' in return_type.lower():
                return f"{sig}\n    return 0\n"
            elif 'float' in return_type.lower():
                return f"{sig}\n    return 0.0\n"
            elif 'str' in return_type.lower():
                return f'{sig}\n    return ""\n'
            elif 'bool' in return_type.lower():
                return f"{sig}\n    return False\n"
            elif 'list' in return_type.lower():
                return f"{sig}\n    return []\n"
            elif 'dict' in return_type.lower():
                return f"{sig}\n    return {{}}\n"
        
        # 默认返回 None
        return f"{sig}\n    return None\n"
