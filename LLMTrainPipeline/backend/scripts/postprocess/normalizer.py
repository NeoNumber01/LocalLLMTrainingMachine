"""
代码规范化模块
强制接口、修复语法、自动 import
"""

import ast
import re
import logging
from typing import Optional

from .import_registry import get_required_imports, generate_import_statements

logger = logging.getLogger(__name__)


class CodeNormalizer:
    """
    代码规范化器
    
    处理阶段：
    1. 签名强制
    2. I/O 移除
    3. 缩进规范化
    4. 关键字修正
    5. 类型翻译
    6. 自动 import
    """
    
    # 关键字修正映射
    KEYWORD_FIXES = {
        # 控制流
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
        
        # 变量声明（移除）
        r'\bvar\s+': '',
        r'\blet\s+': '',
        r'\bconst\s+': '',
        r'\bfinal\s+': '',
        r'\bstatic\s+': '',
        r'\bpublic\s+': '',
        r'\bprivate\s+': '',
        r'\bprotected\s+': '',
        
        # 运算符
        r'===': '==',
        r'!==': '!=',
        r'&&': ' and ',
        r'\|\|': ' or ',
        r'<>': '!=',
        r'\bmod\b': '%',
        r'\bdiv\b': '//',
        
        # 布尔值
        r'\btrue\b': 'True',
        r'\bTRUE\b': 'True',
        r'\bfalse\b': 'False',
        r'\bFALSE\b': 'False',
        
        # 空值
        r'\bnull\b': 'None',
        r'\bNULL\b': 'None',
        r'\bnil\b': 'None',
        r'\bundefined\b': 'None',
        r'\bnullptr\b': 'None',
        
        # 类型
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
    
    # 泛型类型翻译
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
        """初始化规范化器"""
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
        规范化代码
        
        Args:
            code: 输入代码
            signature: 期望的函数签名
            function_name: 函数名
            
        Returns:
            规范化后的代码
        """
        if not code:
            return self._create_stub(signature)
        
        # 1. 强制签名
        code = self._enforce_signature(code, signature, function_name)
        
        # 2. 移除 I/O
        code = self._remove_io(code)
        
        # 3. 缩进规范化
        code = self._normalize_indentation(code)
        
        # 4. 关键字修正
        code = self._fix_keywords(code)
        
        # 5. 类型翻译
        code = self._translate_types(code)
        
        # 6. 自动 import
        code = self._inject_imports(code)
        
        return code
    
    def _create_stub(self, signature: str) -> str:
        """创建占位函数"""
        sig = signature.strip()
        if not sig.endswith(':'):
            sig += ':'
        return f"{sig}\n    pass"
    
    def _enforce_signature(self, code: str, signature: str, function_name: str) -> str:
        """
        强制函数签名
        """
        expected_sig = signature.strip()
        if not expected_sig.endswith(':'):
            expected_sig += ':'
        
        # 匹配现有的函数定义
        pattern = rf'^def\s+{function_name}[^\n]*'
        
        if re.search(pattern, code, re.MULTILINE):
            # 替换现有签名
            code = re.sub(pattern, expected_sig, code, count=1, flags=re.MULTILINE)
        else:
            # 尝试找其他可能的核心函数
            other_func_pattern = r'^def\s+(\w+)\s*\([^)]*\)\s*(?:->.*?)?:'
            match = re.search(other_func_pattern, code, re.MULTILINE)
            
            if match:
                # 找到其他函数，在其前面添加包装
                other_name = match.group(1)
                wrapper = f"{expected_sig}\n    return {other_name}(nums)\n\n"
                code = wrapper + code
                logger.debug(f"包装 {other_name} 为 {function_name}")
            else:
                # 没有函数定义，尝试检测是否有函数体
                lines = code.strip().split('\n')
                if lines:
                    first_line = lines[0]
                    if first_line.startswith('    ') or first_line.startswith('\t'):
                        # 有缩进，可能是函数体
                        code = expected_sig + '\n' + code
                    else:
                        # 没有缩进，添加缩进
                        indented = '\n'.join('    ' + line for line in lines)
                        code = expected_sig + '\n' + indented
        
        return code
    
    def _remove_io(self, code: str) -> str:
        """
        移除 I/O 操作
        """
        # 移除 print 语句（保留注释掉的版本方便调试）
        code = re.sub(r'^(\s*)print\s*\([^)]*\)\s*$', r'\1pass  # print removed', code, flags=re.MULTILINE)
        
        # 移除 input() 调用
        code = re.sub(r'\binput\s*\([^)]*\)', '""', code)
        
        # 移除 sys.stdin 读取
        code = re.sub(r'\bsys\.stdin\.read\s*\([^)]*\)', '""', code)
        code = re.sub(r'\bsys\.stdin\.readline\s*\([^)]*\)', '""', code)
        
        return code
    
    def _normalize_indentation(self, code: str) -> str:
        """
        规范化缩进为 4 空格
        """
        lines = code.split('\n')
        result = []
        
        for line in lines:
            if not line.strip():
                result.append('')
                continue
            
            # 计算前导空白
            stripped = line.lstrip()
            leading = line[:len(line) - len(stripped)]
            
            # Tab 转 4 空格
            leading = leading.replace('\t', '    ')
            
            # 检测 2 空格缩进并转换
            space_count = len(leading)
            if space_count > 0 and space_count % 2 == 0 and space_count % 4 != 0:
                leading = ' ' * (space_count * 2)
            
            result.append(leading + stripped)
        
        return '\n'.join(result)
    
    def _fix_keywords(self, code: str) -> str:
        """
        修正关键字和语法
        """
        # 应用关键字替换
        for pattern, replacement in self._keyword_patterns:
            code = pattern.sub(replacement, code)
        
        # 修复 ++/--
        code = re.sub(r'(\w+)\s*\+\+', r'\1 += 1', code)
        code = re.sub(r'(\w+)\s*--', r'\1 -= 1', code)
        code = re.sub(r'\+\+\s*(\w+)', r'\1 += 1', code)
        code = re.sub(r'--\s*(\w+)', r'\1 -= 1', code)
        
        # 修复 ! 作为逻辑非
        code = re.sub(r'!\s*([a-zA-Z_(])', r'not \1', code)
        
        # 修复 foreach
        code = re.sub(r'\bforeach\s+', 'for ', code)
        
        # 修复 C 风格注释
        lines = code.split('\n')
        fixed_lines = []
        for line in lines:
            # 检查 // 是否在字符串外
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
        
        # 移除 C 风格块注释
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        
        # 移除行尾分号
        code = re.sub(r';\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r';\s*#', ' #', code)
        
        # 修复 new 关键字
        code = re.sub(r'\bnew\s+(\w+)\s*\(', r'\1(', code)
        
        # 修复 this.
        code = re.sub(r'\bthis\.', 'self.', code)
        
        # 修复常见输出函数
        code = re.sub(r'\bSystem\.out\.println\s*\(', 'print(', code)
        code = re.sub(r'\bconsole\.log\s*\(', 'print(', code)
        code = re.sub(r'\bprintf\s*\(', 'print(', code)
        code = re.sub(r'\bprintln\s*\(', 'print(', code)
        
        # 修复数组长度
        code = re.sub(r'(\w+)\.length\b(?!\s*\()', r'len(\1)', code)
        code = re.sub(r'(\w+)\.size\(\)', r'len(\1)', code)
        
        # 修复常见方法
        code = re.sub(r'\.push\s*\(', '.append(', code)
        code = re.sub(r'\.add\s*\(', '.append(', code)
        code = re.sub(r'\.trim\s*\(\)', '.strip()', code)
        code = re.sub(r'\.toUpperCase\s*\(\)', '.upper()', code)
        code = re.sub(r'\.toLowerCase\s*\(\)', '.lower()', code)
        
        # 修复 Math 函数
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
        翻译泛型类型
        """
        for pattern, replacement in self._generic_patterns:
            code = pattern.sub(replacement, code)
        return code
    
    def _inject_imports(self, code: str) -> str:
        """
        自动注入缺失的 import
        """
        # 获取需要的 import
        required = get_required_imports(code)
        
        if not required:
            return code
        
        # 生成 import 语句
        import_block = generate_import_statements(required)
        
        if not import_block:
            return code
        
        # 找到合适的插入位置
        lines = code.split('\n')
        insert_pos = 0
        
        # 跳过已有的 import 和空行
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                insert_pos = i + 1
            elif stripped and not stripped.startswith('#'):
                break
        
        # 插入 import
        lines.insert(insert_pos, import_block)
        if insert_pos > 0 and lines[insert_pos - 1].strip():
            lines.insert(insert_pos, '')  # 添加空行分隔
        
        logger.debug(f"注入 import: {required}")
        
        return '\n'.join(lines)
    
    def add_safety_guards(self, code: str) -> str:
        """
        添加安全防护代码
        """
        modifications = []
        
        # 添加递归限制
        if 'def ' in code and ('dfs' in code.lower() or 'recursive' in code.lower() or self._has_recursion(code)):
            if 'setrecursionlimit' not in code:
                code = "import sys\nsys.setrecursionlimit(10**7)\n\n" + code
                modifications.append("添加递归限制")
        
        return code
    
    def _has_recursion(self, code: str) -> bool:
        """检测是否有递归"""
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
            # 代码有语法错误，使用简单启发式
            pattern = r'def\s+(\w+).*?\1\s*\('
            return bool(re.search(pattern, code, re.DOTALL))
        return False
