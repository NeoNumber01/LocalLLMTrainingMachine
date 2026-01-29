"""
Rule-based Fixer Module
Automatic code fixing based on rules, referenced from LeoLLM's successful implementation
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
    Rule-based Fixer
    
    Implements automatic fixing strategies for common errors:
    1. Indentation error fixing
    2. Missing import completion
    3. Interface non-compliance fixing
    4. Empty array crash fallback
    5. Recursion protection
    6. Syntax error fixing (parentheses, colons, etc.)
    """
    
    def __init__(self):
        """Initialize fixer"""
        self._fix_history: List[str] = []
    
    def fix(self, code: str, error_type: ErrorType, error_message: str,
            signature: str = "def solve(nums: list[int]) -> int:") -> Tuple[str, List[str]]:
        """
        Attempt to fix code based on error type
        
        Args:
            code: Code to fix
            error_type: Error type
            error_message: Error message
            signature: Expected function signature
            
        Returns:
            (fixed code, list of fixes applied)
        """
        self._fix_history = []
        
        # Choose fixing strategy based on error type
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
        Apply all possible preventive fixes
        
        Args:
            code: Code to fix
            signature: Expected function signature
            
        Returns:
            (fixed code, list of fixes applied)
        """
        self._fix_history = []
        
        # 1. Normalize indentation
        code = self._normalize_indentation(code)
        
        # 2. Syntax fixes
        code = self._fix_syntax_iterative(code, signature)
        
        # 3. Auto import
        code = self._auto_import(code)
        
        # 4. Empty input fallback
        code = self._add_empty_input_guard(code, signature)
        
        # 5. Recursion protection
        code = self._add_recursion_guard(code)
        
        return code, self._fix_history
    
    # =========================================================================
    # Syntax Error Fixing
    # =========================================================================
    def _fix_syntax_error(self, code: str, error_message: str, signature: str) -> str:
        """Fix syntax errors"""
        return self._fix_syntax_iterative(code, signature, max_attempts=3)
    
    def _fix_syntax_iterative(self, code: str, signature: str, max_attempts: int = 3) -> str:
        """Iteratively fix syntax errors (referenced from LeoLLM Phase 12)"""
        for attempt in range(max_attempts):
            try:
                ast.parse(code)
                return code  # Code is valid
            except SyntaxError as e:
                logger.debug(f"Syntax fix attempt {attempt + 1}: {e}")
                code = self._attempt_syntax_fix(code, e, signature)
        
        return code
    
    def _attempt_syntax_fix(self, code: str, error: SyntaxError, signature: str) -> str:
        """
        Attempt to fix based on syntax error (referenced from LeoLLM)
        """
        lines = code.split('\n')
        error_msg = str(error).lower()
        
        if error.lineno is None:
            return code
        
        line_idx = error.lineno - 1
        if line_idx >= len(lines):
            return code
        
        problem_line = lines[line_idx]
        
        # Missing colon
        if 'expected ":"' in str(error) or "expected ':'" in str(error):
            if not problem_line.rstrip().endswith(':'):
                lines[line_idx] = problem_line.rstrip() + ':'
                self._fix_history.append("Added missing colon")
                return '\n'.join(lines)
        
        # Signature syntax error
        if 'invalid syntax' in error_msg and 'def solve' in problem_line:
            expected_sig = signature.strip()
            if not expected_sig.endswith(':'):
                expected_sig += ':'
            lines[line_idx] = expected_sig
            self._fix_history.append("Fixed function signature")
            return '\n'.join(lines)
        
        # Unexpected EOF - unbalanced brackets
        if 'unexpected eof' in error_msg or 'eof while scanning' in error_msg:
            open_count = code.count('(') - code.count(')')
            close_count = code.count('[') - code.count(']')
            brace_count = code.count('{') - code.count('}')
            
            suffix = ')' * max(0, open_count)
            suffix += ']' * max(0, close_count)
            suffix += '}' * max(0, brace_count)
            
            if suffix:
                code = code.rstrip() + suffix
                self._fix_history.append(f"Completed brackets: {suffix}")
                return code
            
            # Check unclosed strings
            single_quotes = code.count("'") - code.count("\\'")
            double_quotes = code.count('"') - code.count('\\"')
            
            if single_quotes % 2 != 0:
                code = code.rstrip() + "'"
                self._fix_history.append("Closed single quote string")
                return code
            if double_quotes % 2 != 0:
                code = code.rstrip() + '"'
                self._fix_history.append("Closed double quote string")
                return code
        
        # Indentation error
        if 'indent' in error_msg:
            if line_idx > 0:
                prev_line = lines[line_idx - 1]
                prev_indent = len(prev_line) - len(prev_line.lstrip())
                current_stripped = problem_line.lstrip()
                
                if prev_line.rstrip().endswith(':'):
                    lines[line_idx] = ' ' * (prev_indent + 4) + current_stripped
                else:
                    lines[line_idx] = ' ' * prev_indent + current_stripped
                
                self._fix_history.append(f"Fixed line {error.lineno} indentation")
                return '\n'.join(lines)
        
        # Unterminated string
        if 'unterminated string' in error_msg:
            if problem_line.count('"') % 2 != 0:
                lines[line_idx] = problem_line.rstrip() + '"'
                self._fix_history.append("Closed string")
                return '\n'.join(lines)
            if problem_line.count("'") % 2 != 0:
                lines[line_idx] = problem_line.rstrip() + "'"
                self._fix_history.append("Closed string")
                return '\n'.join(lines)
        
        # Unmatched brackets
        if 'unmatched' in error_msg:
            if ')' in problem_line and '(' not in problem_line:
                lines[line_idx] = problem_line.replace(')', '', 1)
                self._fix_history.append("Removed extra )")
                return '\n'.join(lines)
            if ']' in problem_line and '[' not in problem_line:
                lines[line_idx] = problem_line.replace(']', '', 1)
                self._fix_history.append("Removed extra ]")
                return '\n'.join(lines)
            if '}' in problem_line and '{' not in problem_line:
                lines[line_idx] = problem_line.replace('}', '', 1)
                self._fix_history.append("Removed extra }")
                return '\n'.join(lines)
        
        # Invalid character
        if 'invalid character' in error_msg:
            cleaned = ''.join(c if c.isascii() and (c.isprintable() or c in '\t\n') else '' for c in problem_line)
            lines[line_idx] = cleaned
            self._fix_history.append("Removed invalid characters")
            return '\n'.join(lines)
        
        return code
    
    # =========================================================================
    # Indentation Fixing
    # =========================================================================
    def _fix_indentation(self, code: str, error_message: str) -> str:
        """Fix indentation errors"""
        code = self._normalize_indentation(code)
        return code
    
    def _normalize_indentation(self, code: str) -> str:
        """Normalize indentation"""
        lines = code.split('\n')
        result = []
        
        for line in lines:
            if not line.strip():
                result.append('')
                continue
            
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]
            
            # Tab to 4 spaces
            original_leading = leading
            leading = leading.replace('\t', '    ')
            
            # 2 spaces to 4 spaces
            space_count = len(leading)
            if space_count > 0 and space_count % 2 == 0 and space_count % 4 != 0:
                leading = ' ' * (space_count * 2)
            
            if leading != original_leading:
                if "Normalized indentation" not in self._fix_history:
                    self._fix_history.append("Normalized indentation")
            
            result.append(leading + stripped)
        
        return '\n'.join(result)
    
    # =========================================================================
    # Name Error Fixing (Auto Import)
    # =========================================================================
    def _fix_name_error(self, code: str, error_message: str) -> str:
        """Fix NameError - auto import"""
        # Extract undefined name from error message
        match = re.search(r"name '(\w+)' is not defined", error_message)
        if match:
            undefined_name = match.group(1)
            code = self._add_import_for_name(code, undefined_name)
        else:
            code = self._auto_import(code)
        return code
    
    def _add_import_for_name(self, code: str, name: str) -> str:
        """Add import for specific name"""
        from .import_registry import IMPORT_REGISTRY
        
        if name in IMPORT_REGISTRY:
            module, style = IMPORT_REGISTRY[name]
            if style == "from":
                import_stmt = f"from {module} import {name}"
            else:
                import_stmt = f"import {module}"
            
            # Avoid duplicate additions
            if import_stmt not in code:
                code = import_stmt + "\n" + code
                self._fix_history.append(f"Added import: {import_stmt}")
        
        return code
    
    def _auto_import(self, code: str) -> str:
        """Auto-complete all missing imports"""
        required = get_required_imports(code)
        
        if not required:
            return code
        
        import_block = generate_import_statements(required)
        
        if import_block:
            # Check existing imports
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
            self._fix_history.append(f"Auto import: {', '.join(required)}")
        
        return code
    
    # =========================================================================
    # Import Error Fixing
    # =========================================================================
    def _fix_import_error(self, code: str, error_message: str) -> str:
        """Fix ImportError"""
        # Try to remove problematic import
        match = re.search(r"No module named '(\w+)'", error_message)
        if match:
            bad_module = match.group(1)
            lines = code.split('\n')
            new_lines = []
            for line in lines:
                if f"import {bad_module}" not in line and f"from {bad_module}" not in line:
                    new_lines.append(line)
                else:
                    self._fix_history.append(f"Removed invalid import: {bad_module}")
            code = '\n'.join(new_lines)
        return code
    
    # =========================================================================
    # Index Error Fixing (Empty Input Fallback)
    # =========================================================================
    def _fix_index_error(self, code: str, signature: str) -> str:
        """Fix IndexError - add empty input check"""
        return self._add_empty_input_guard(code, signature)
    
    def _add_empty_input_guard(self, code: str, signature: str) -> str:
        """Add empty input check"""
        # Check if empty input check already exists
        if "if not nums" in code or "if len(nums) == 0" in code or "if nums == []" in code:
            return code
        
        # Extract parameter name and return type from signature
        param_name = "nums"
        default_return = "0"
        
        # Try to extract parameter name from signature
        param_match = re.search(r'def\s+\w+\s*\((\w+)', signature)
        if param_match:
            param_name = param_match.group(1)
        
        # Try to extract return type from signature
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
        
        # Find function body start and insert check
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') and ':' in line:
                # Find first non-empty line after function definition
                for j in range(i + 1, len(lines)):
                    if lines[j].strip():
                        indent = len(lines[j]) - len(lines[j].lstrip())
                        guard = ' ' * indent + f"if not {param_name}: return {default_return}"
                        lines.insert(j, guard)
                        self._fix_history.append(f"Added empty input check: if not {param_name}")
                        return '\n'.join(lines)
                break
        
        return code
    
    # =========================================================================
    # Recursion Protection
    # =========================================================================
    def _fix_recursion_error(self, code: str) -> str:
        """Fix RecursionError"""
        return self._add_recursion_guard(code)
    
    def _add_recursion_guard(self, code: str) -> str:
        """Add recursion limit"""
        if "setrecursionlimit" in code:
            return code
        
        # Detect if there's recursion
        if not self._has_recursion(code):
            return code
        
        # Add recursion limit
        code = "import sys\nsys.setrecursionlimit(10**7)\n\n" + code
        self._fix_history.append("Added recursion limit: setrecursionlimit(10**7)")
        
        return code
    
    def _has_recursion(self, code: str) -> bool:
        """Detect if code contains recursion"""
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
            # Use simple heuristic
            pattern = r'def\s+(\w+).*?\1\s*\('
            return bool(re.search(pattern, code, re.DOTALL))
        return False
    
    # =========================================================================
    # Interface Fixing
    # =========================================================================
    def _fix_interface_error(self, code: str, signature: str) -> str:
        """Fix interface non-compliance"""
        expected_sig = signature.strip()
        if not expected_sig.endswith(':'):
            expected_sig += ':'
        
        # Check if there's a solve function
        if 'def solve' not in code:
            # Try to find other functions and wrap
            func_match = re.search(r'def\s+(\w+)\s*\([^)]*\)', code)
            if func_match:
                other_func = func_match.group(1)
                wrapper = f"{expected_sig}\n    return {other_func}(nums)\n\n"
                code = wrapper + code
                self._fix_history.append(f"Wrapped {other_func} as solve")
            else:
                # No function, create placeholder
                code = f"{expected_sig}\n    pass\n\n" + code
                self._fix_history.append("Created solve placeholder function")
        
        return code
    
    # =========================================================================
    # Smart Fallback Generation (referenced from LeoLLM Phase 14)
    # =========================================================================
    def generate_fallback(self, code: str, signature: str) -> str:
        """
        When all fixes fail, try to generate a runnable fallback code
        """
        # First check if code is valid
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            logger.warning("Code still invalid, trying to generate fallback")
        
        # Try to extract return logic
        returns = self._extract_return_expressions(code)
        if returns:
            fallback = self._build_from_returns(signature, returns)
            try:
                ast.parse(fallback)
                self._fix_history.append("Generated fallback code using return logic")
                return fallback
            except SyntaxError:
                pass
        
        # Last resort: return type default value
        return self._type_based_default(signature)
    
    def _extract_return_expressions(self, code: str) -> List[str]:
        """Extract return expressions"""
        returns = []
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped.startswith('return '):
                expr = stripped[7:].strip()
                if expr and expr != 'None':
                    returns.append(expr)
        return returns
    
    def _build_from_returns(self, signature: str, returns: List[str]) -> str:
        """Build code from return expressions"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        
        first_return = returns[0]
        return f"{sig}\n    return {first_return}\n"
    
    def _type_based_default(self, signature: str) -> str:
        """Generate default implementation based on return type"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        
        # Parse return type
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
        
        # Default return None
        return f"{sig}\n    return None\n"
