"""
Code Normalization Module
Enforce interface, fix syntax, auto import
"""

import ast
import re
import logging
from typing import Optional

from .import_registry import get_required_imports, generate_import_statements

logger = logging.getLogger(__name__)


class CodeNormalizer:
    """
    Code Normalizer
    
    Processing phases:
    1. Signature enforcement
    2. I/O removal
    3. Indentation normalization
    4. Keyword correction
    5. Type translation
    6. Auto import
    """
    
    # Keyword correction mapping
    KEYWORD_FIXES = {
        # Control flow
        r'\belseif\b': 'elif',
        r'\belse\s+if\b': 'elif',
        r'\belsif\b': 'elif',
        r'\belif\s+if\b': 'elif',
        r'\bcatch\b': 'except',
        r'\bthrow\b': 'raise',
        r'\bfunction\b': 'def',
        r'\bfunc\b': 'def',
        r'\bfn\b': 'def',
        r'\bsub\b': 'def',
        r'\bprocedure\b': 'def',
        
        # Variable declarations (remove)
        r'\bvar\s+': '',
        r'\blet\s+': '',
        r'\bconst\s+': '',
        r'\bfinal\s+': '',
        r'\bstatic\s+': '',
        r'\bpublic\s+': '',
        r'\bprivate\s+': '',
        r'\bprotected\s+': '',
        
        # Operators
        r'===': '==',
        r'!==': '!=',
        r'&&': ' and ',
        r'\|\|': ' or ',
        r'<>': '!=',
        r'\bmod\b': '%',
        r'\bdiv\b': '//',
        
        # Boolean values
        r'\btrue\b': 'True',
        r'\bTRUE\b': 'True',
        r'\bfalse\b': 'False',
        r'\bFALSE\b': 'False',
        
        # Null values
        r'\bnull\b': 'None',
        r'\bNULL\b': 'None',
        r'\bnil\b': 'None',
        r'\bundefined\b': 'None',
        r'\bnullptr\b': 'None',
        
        # Types
        r'\bvoid\b': 'None',
        r'\bboolean\b': 'bool',
        r'\bBoolean\b': 'bool',
        r'\binteger\b': 'int',
        r'\bInteger\b': 'int',
        r'\bdouble\b': 'float',
        r'\bDouble\b': 'float',
        r'\bstring\b': 'str',
        r'\bString\b': 'str',
        
        # Misc
        r'\breturn\s+void\b': 'return None',
    }
    
    # Generic type translation
    GENERIC_TYPE_PATTERNS = [
        (r'\bList<([^>]+)>', r'List[\1]'),
        (r'\blist<([^>]+)>', r'List[\1]'),
        (r'\bDict<([^,]+),\s*([^>]+)>', r'Dict[\1, \2]'),
        (r'\bdict<([^,]+),\s*([^>]+)>', r'Dict[\1, \2]'),
        (r'\bMap<([^,]+),\s*([^>]+)>', r'Dict[\1, \2]'),
        (r'\bHashMap<([^,]+),\s*([^>]+)>', r'Dict[\1, \2]'),
        (r'\bSet<([^>]+)>', r'Set[\1]'),
        (r'\bset<([^>]+)>', r'Set[\1]'),
        (r'\bHashSet<([^>]+)>', r'Set[\1]'),
        (r'\bArray<([^>]+)>', r'List[\1]'),
        (r'\barray<([^>]+)>', r'List[\1]'),
        (r'\bArrayList<([^>]+)>', r'List[\1]'),
        (r'\bVector<([^>]+)>', r'List[\1]'),
        (r'\bvector<([^>]+)>', r'List[\1]'),
        (r'\bTuple<([^>]+)>', r'Tuple[\1]'),
        (r'\bOptional<([^>]+)>', r'Optional[\1]'),
        (r'\bOption<([^>]+)>', r'Optional[\1]'),
    ]
    
    def __init__(self):
        """Initialize normalizer"""
        self._keyword_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.KEYWORD_FIXES.items()
        ]
        self._generic_patterns = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self.GENERIC_TYPE_PATTERNS
        ]
    
    def normalize(self, code: str, signature: str, function_name: str = "solve") -> str:
        """
        Normalize code
        
        Args:
            code: Input code
            signature: Expected function signature
            function_name: Function name
            
        Returns:
            Normalized code
        """
        if not code:
            return self._create_stub(signature)
        
        # 1. Enforce signature
        code = self._enforce_signature(code, signature, function_name)
        
        # 2. Remove I/O
        code = self._remove_io(code)
        
        # 3. Normalize indentation
        code = self._normalize_indentation(code)
        
        # 4. Fix keywords
        code = self._fix_keywords(code)
        
        # 5. Translate types
        code = self._translate_types(code)
        
        # 6. Auto import
        code = self._inject_imports(code)
        
        return code
    
    def _create_stub(self, signature: str) -> str:
        """Create placeholder function"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        return f"{sig}\n    pass"
    
    def _enforce_signature(self, code: str, signature: str, function_name: str) -> str:
        """
        Enforce function signature
        """
        expected_sig = signature.strip()
        if not expected_sig.endswith(':'):
            expected_sig += ':'
        
        # Match existing function definition
        pattern = rf'^def\s+{function_name}[^\n]*'
        
        if re.search(pattern, code, re.MULTILINE):
            # Replace existing signature
            code = re.sub(pattern, expected_sig, code, count=1, flags=re.MULTILINE)
        else:
            # Try to find other possible core functions
            other_func_pattern = r'^def\s+(\w+)\s*\([^)]*\)\s*(?:->.*?)?:'
            match = re.search(other_func_pattern, code, re.MULTILINE)
            
            if match:
                # Found another function, add wrapper before it
                other_name = match.group(1)
                wrapper = f"{expected_sig}\n    return {other_name}(nums)\n\n"
                code = wrapper + code
                logger.debug(f"Wrapping {other_name} as {function_name}")
            else:
                # No function definition, check if there's a function body
                lines = code.strip().split('\n')
                if lines:
                    first_line = lines[0]
                    if first_line.startswith('    ') or first_line.startswith('\t'):
                        # Has indentation, might be function body
                        code = expected_sig + '\n' + code
                    else:
                        # No indentation, add indentation
                        indented = '\n'.join('    ' + line for line in lines)
                        code = expected_sig + '\n' + indented
        
        return code
    
    def _remove_io(self, code: str) -> str:
        """
        Remove I/O operations
        """
        # Remove print statements (keep commented version for debugging)
        code = re.sub(r'^(\s*)print\s*\([^)]*\)\s*$', r'\1pass  # print removed', code, flags=re.MULTILINE)
        
        # Remove input() calls
        code = re.sub(r'\binput\s*\([^)]*\)', '""', code)
        
        # Remove sys.stdin reads
        code = re.sub(r'\bsys\.stdin\.read\s*\([^)]*\)', '""', code)
        code = re.sub(r'\bsys\.stdin\.readline\s*\([^)]*\)', '""', code)
        
        return code
    
    def _normalize_indentation(self, code: str) -> str:
        """
        Normalize indentation to 4 spaces
        """
        lines = code.split('\n')
        result = []
        
        for line in lines:
            if not line.strip():
                result.append('')
                continue
            
            # Calculate leading whitespace
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]
            
            # Tab to 4 spaces
            leading = leading.replace('\t', '    ')
            
            # Detect 2-space indent and convert
            space_count = len(leading)
            if space_count > 0 and space_count % 2 == 0 and space_count % 4 != 0:
                leading = ' ' * (space_count * 2)
            
            result.append(leading + stripped)
        
        return '\n'.join(result)
    
    def _fix_keywords(self, code: str) -> str:
        """
        Fix keywords and syntax
        """
        # Apply keyword replacements
        for pattern, replacement in self._keyword_patterns:
            code = pattern.sub(replacement, code)
        
        # Fix ++/--
        code = re.sub(r'(\w+)\s*\+\+', r'\1 += 1', code)
        code = re.sub(r'(\w+)\s*--', r'\1 -= 1', code)
        code = re.sub(r'\+\+\s*(\w+)', r'\1 += 1', code)
        code = re.sub(r'--\s*(\w+)', r'\1 -= 1', code)
        
        # Fix ! as logical not
        code = re.sub(r'!\s*([a-zA-Z_(])', r'not \1', code)
        
        # Fix foreach
        code = re.sub(r'\bforeach\s+', 'for ', code)
        
        # Fix C-style comments
        lines = code.split('\n')
        fixed_lines = []
        for line in lines:
            # Check if // is outside string
            in_string = False
            quote_char = None
            i = 0
            while i < len(line):
                c = line[i]
                if c in '"\'':
                    if not in_string:
                        in_string = True
                        quote_char = c
                    elif c == quote_char and (i == 0 or line[i-1] != '\\'):
                        in_string = False
                elif c == '/' and i + 1 < len(line) and line[i+1] == '/' and not in_string:
                    line = line[:i] + '#' + line[i+2:]
                    break
                i += 1
            fixed_lines.append(line)
        code = '\n'.join(fixed_lines)
        
        # Remove C-style block comments
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        # Remove trailing semicolons
        code = re.sub(r';\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r';\s*#', ' #', code)
        
        # Fix new keyword
        code = re.sub(r'\bnew\s+(\w+)\s*\(', r'\1(', code)
        
        # Fix this.
        code = re.sub(r'\bthis\.', 'self.', code)
        
        # Fix common output functions
        code = re.sub(r'\bSystem\.out\.println\s*\(', 'print(', code)
        code = re.sub(r'\bconsole\.log\s*\(', 'print(', code)
        code = re.sub(r'\bprintf\s*\(', 'print(', code)
        code = re.sub(r'\bprintln\s*\(', 'print(', code)
        
        # Fix array length
        code = re.sub(r'(\w+)\.length\b(?!\s*\()', r'len(\1)', code)
        code = re.sub(r'(\w+)\.size\(\)', r'len(\1)', code)
        
        # Fix common methods
        code = re.sub(r'\.push\s*\(', '.append(', code)
        code = re.sub(r'\.add\s*\(', '.append(', code)
        code = re.sub(r'\.trim\s*\(\)', '.strip()', code)
        code = re.sub(r'\.toUpperCase\s*\(\)', '.upper()', code)
        code = re.sub(r'\.toLowerCase\s*\(\)', '.lower()', code)
        
        # Fix Math functions
        code = re.sub(r'\bMath\.abs\s*\(', 'abs(', code)
        code = re.sub(r'\bMath\.max\s*\(', 'max(', code)
        code = re.sub(r'\bMath\.min\s*\(', 'min(', code)
        code = re.sub(r'\bMath\.pow\s*\(', 'pow(', code)
        code = re.sub(r'\bMath\.sqrt\s*\(', 'sqrt(', code)
        code = re.sub(r'\bMath\.floor\s*\(', 'floor(', code)
        code = re.sub(r'\bMath\.ceil\s*\(', 'ceil(', code)
        
        return code
    
    def _translate_types(self, code: str) -> str:
        """
        Translate generic types
        """
        for pattern, replacement in self._generic_patterns:
            code = pattern.sub(replacement, code)
        return code
    
    def _inject_imports(self, code: str) -> str:
        """
        Auto-inject missing imports
        """
        # Get required imports
        required = get_required_imports(code)
        
        if not required:
            return code
        
        # Generate import statements
        import_block = generate_import_statements(required)
        
        if not import_block:
            return code
        
        # Find suitable insertion position
        lines = code.split('\n')
        insert_pos = 0
        
        # Skip existing imports and empty lines
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                insert_pos = i + 1
            elif stripped and not stripped.startswith('#'):
                break
        
        # Insert imports
        lines.insert(insert_pos, import_block)
        if insert_pos > 0 and lines[insert_pos - 1].strip():
            lines.insert(insert_pos, '')  # Add empty line separator
        
        logger.debug(f"Injected imports: {required}")
        
        return '\n'.join(lines)
    
    def add_safety_guards(self, code: str) -> str:
        """
        Add safety guard code
        """
        modifications = []
        
        # Add recursion limit
        if 'def ' in code and ('dfs' in code.lower() or 'recursive' in code.lower() or self._has_recursion(code)):
            if 'setrecursionlimit' not in code:
                code = "import sys\nsys.setrecursionlimit(10**7)\n\n" + code
                modifications.append("Added recursion limit")
        
        return code
    
    def _has_recursion(self, code: str) -> bool:
        """Detect if there is recursion"""
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
            # Code has syntax error, use simple heuristic
            pattern = r'def\s+(\w+).*?\1\s*\('
            return bool(re.search(pattern, code, re.DOTALL))
        return False
