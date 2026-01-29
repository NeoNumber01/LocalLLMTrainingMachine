"""
Import 注册表模块
300+ 常见标准库符号到模块的映射，用于自动依赖注入
"""

# =============================================================================
# 符号到模块映射
# 格式: "symbol": ("module", "import_style")
# import_style: "from" = from module import symbol
#               "import" = import module (使用 module.symbol)
# =============================================================================

IMPORT_REGISTRY: dict[str, tuple[str, str]] = {
    # =========================================================================
    # typing 模块
    # =========================================================================
    "List": ("typing", "from"),
    "Dict": ("typing", "from"),
    "Set": ("typing", "from"),
    "Tuple": ("typing", "from"),
    "Optional": ("typing", "from"),
    "Union": ("typing", "from"),
    "Any": ("typing", "from"),
    "Callable": ("typing", "from"),
    "Iterable": ("typing", "from"),
    "Iterator": ("typing", "from"),
    "Sequence": ("typing", "from"),
    "Mapping": ("typing", "from"),
    "MutableMapping": ("typing", "from"),
    "MutableSequence": ("typing", "from"),
    "MutableSet": ("typing", "from"),
    "FrozenSet": ("typing", "from"),
    "DefaultDict": ("typing", "from"),
    "Counter": ("typing", "from"),
    "Deque": ("typing", "from"),
    "NamedTuple": ("typing", "from"),
    "TypedDict": ("typing", "from"),
    "Literal": ("typing", "from"),
    "Final": ("typing", "from"),
    "ClassVar": ("typing", "from"),
    "TypeVar": ("typing", "from"),
    "Generic": ("typing", "from"),
    "Protocol": ("typing", "from"),
    "overload": ("typing", "from"),
    "cast": ("typing", "from"),
    "TYPE_CHECKING": ("typing", "from"),
    
    # =========================================================================
    # collections 模块
    # =========================================================================
    "deque": ("collections", "from"),
    "defaultdict": ("collections", "from"),
    "OrderedDict": ("collections", "from"),
    "namedtuple": ("collections", "from"),
    "ChainMap": ("collections", "from"),
    "UserDict": ("collections", "from"),
    "UserList": ("collections", "from"),
    "UserString": ("collections", "from"),
    
    # =========================================================================
    # math 模块
    # =========================================================================
    "sqrt": ("math", "from"),
    "ceil": ("math", "from"),
    "floor": ("math", "from"),
    "log": ("math", "from"),
    "log2": ("math", "from"),
    "log10": ("math", "from"),
    "exp": ("math", "from"),
    "pow": ("math", "from"),
    "sin": ("math", "from"),
    "cos": ("math", "from"),
    "tan": ("math", "from"),
    "asin": ("math", "from"),
    "acos": ("math", "from"),
    "atan": ("math", "from"),
    "atan2": ("math", "from"),
    "sinh": ("math", "from"),
    "cosh": ("math", "from"),
    "tanh": ("math", "from"),
    "pi": ("math", "from"),
    "e": ("math", "from"),
    "tau": ("math", "from"),
    "inf": ("math", "from"),
    "nan": ("math", "from"),
    "isinf": ("math", "from"),
    "isnan": ("math", "from"),
    "isfinite": ("math", "from"),
    "factorial": ("math", "from"),
    "comb": ("math", "from"),
    "perm": ("math", "from"),
    "gcd": ("math", "from"),
    "lcm": ("math", "from"),
    "isqrt": ("math", "from"),
    "fabs": ("math", "from"),
    "fsum": ("math", "from"),
    "copysign": ("math", "from"),
    "fmod": ("math", "from"),
    "modf": ("math", "from"),
    "trunc": ("math", "from"),
    "hypot": ("math", "from"),
    "degrees": ("math", "from"),
    "radians": ("math", "from"),
    
    # =========================================================================
    # itertools 模块
    # =========================================================================
    "permutations": ("itertools", "from"),
    "combinations": ("itertools", "from"),
    "combinations_with_replacement": ("itertools", "from"),
    "product": ("itertools", "from"),
    "chain": ("itertools", "from"),
    "cycle": ("itertools", "from"),
    "repeat": ("itertools", "from"),
    "islice": ("itertools", "from"),
    "takewhile": ("itertools", "from"),
    "dropwhile": ("itertools", "from"),
    "accumulate": ("itertools", "from"),
    "groupby": ("itertools", "from"),
    "zip_longest": ("itertools", "from"),
    "starmap": ("itertools", "from"),
    "filterfalse": ("itertools", "from"),
    "compress": ("itertools", "from"),
    "pairwise": ("itertools", "from"),
    "batched": ("itertools", "from"),
    "count": ("itertools", "from"),
    "tee": ("itertools", "from"),
    
    # =========================================================================
    # functools 模块
    # =========================================================================
    "reduce": ("functools", "from"),
    "lru_cache": ("functools", "from"),
    "cache": ("functools", "from"),
    "cached_property": ("functools", "from"),
    "partial": ("functools", "from"),
    "partialmethod": ("functools", "from"),
    "wraps": ("functools", "from"),
    "total_ordering": ("functools", "from"),
    "cmp_to_key": ("functools", "from"),
    
    # =========================================================================
    # heapq 模块
    # =========================================================================
    "heapify": ("heapq", "from"),
    "heappush": ("heapq", "from"),
    "heappop": ("heapq", "from"),
    "heappushpop": ("heapq", "from"),
    "heapreplace": ("heapq", "from"),
    "nlargest": ("heapq", "from"),
    "nsmallest": ("heapq", "from"),
    "merge": ("heapq", "from"),
    
    # =========================================================================
    # bisect 模块
    # =========================================================================
    "bisect": ("bisect", "from"),
    "bisect_left": ("bisect", "from"),
    "bisect_right": ("bisect", "from"),
    "insort": ("bisect", "from"),
    "insort_left": ("bisect", "from"),
    "insort_right": ("bisect", "from"),
    
    # =========================================================================
    # operator 模块
    # =========================================================================
    "add": ("operator", "from"),
    "sub": ("operator", "from"),
    "mul": ("operator", "from"),
    "truediv": ("operator", "from"),
    "floordiv": ("operator", "from"),
    "mod": ("operator", "from"),
    "neg": ("operator", "from"),
    "pos": ("operator", "from"),
    "abs": ("operator", "from"),
    "eq": ("operator", "from"),
    "ne": ("operator", "from"),
    "lt": ("operator", "from"),
    "le": ("operator", "from"),
    "gt": ("operator", "from"),
    "ge": ("operator", "from"),
    "not_": ("operator", "from"),
    "and_": ("operator", "from"),
    "or_": ("operator", "from"),
    "xor": ("operator", "from"),
    "itemgetter": ("operator", "from"),
    "attrgetter": ("operator", "from"),
    "methodcaller": ("operator", "from"),
    
    # =========================================================================
    # random 模块
    # =========================================================================
    "random": ("random", "from"),
    "randint": ("random", "from"),
    "randrange": ("random", "from"),
    "choice": ("random", "from"),
    "choices": ("random", "from"),
    "sample": ("random", "from"),
    "shuffle": ("random", "from"),
    "uniform": ("random", "from"),
    "gauss": ("random", "from"),
    "seed": ("random", "from"),
    "Random": ("random", "from"),
    
    # =========================================================================
    # re 模块
    # =========================================================================
    "compile": ("re", "from"),
    "match": ("re", "from"),
    "search": ("re", "from"),
    "findall": ("re", "from"),
    "finditer": ("re", "from"),
    "sub": ("re", "from"),
    "subn": ("re", "from"),
    "split": ("re", "from"),
    "escape": ("re", "from"),
    "IGNORECASE": ("re", "from"),
    "MULTILINE": ("re", "from"),
    "DOTALL": ("re", "from"),
    "VERBOSE": ("re", "from"),
    
    # =========================================================================
    # string 模块
    # =========================================================================
    "ascii_letters": ("string", "from"),
    "ascii_lowercase": ("string", "from"),
    "ascii_uppercase": ("string", "from"),
    "digits": ("string", "from"),
    "hexdigits": ("string", "from"),
    "octdigits": ("string", "from"),
    "punctuation": ("string", "from"),
    "whitespace": ("string", "from"),
    "printable": ("string", "from"),
    
    # =========================================================================
    # datetime 模块
    # =========================================================================
    "datetime": ("datetime", "from"),
    "date": ("datetime", "from"),
    "time": ("datetime", "from"),
    "timedelta": ("datetime", "from"),
    "timezone": ("datetime", "from"),
    
    # =========================================================================
    # copy 模块
    # =========================================================================
    "copy": ("copy", "from"),
    "deepcopy": ("copy", "from"),
    
    # =========================================================================
    # json 模块
    # =========================================================================
    "dumps": ("json", "from"),
    "loads": ("json", "from"),
    "dump": ("json", "from"),
    "load": ("json", "from"),
    
    # =========================================================================
    # sys 模块 (特殊处理)
    # =========================================================================
    "maxsize": ("sys", "from"),
    "setrecursionlimit": ("sys", "from"),
    "getrecursionlimit": ("sys", "from"),
    "stdin": ("sys", "from"),
    "stdout": ("sys", "from"),
    "stderr": ("sys", "from"),
    
    # =========================================================================
    # 整个模块导入 (使用 module.symbol 格式)
    # =========================================================================
    "heapq": ("heapq", "import"),
    "bisect": ("bisect", "import"),
    "math": ("math", "import"),
    "re": ("re", "import"),
    "json": ("json", "import"),
    "sys": ("sys", "import"),
    "os": ("os", "import"),
    "collections": ("collections", "import"),
    "itertools": ("itertools", "import"),
    "functools": ("functools", "import"),
    "operator": ("operator", "import"),
    "string": ("string", "import"),
}


def get_required_imports(code: str) -> set[str]:
    """
    分析代码，找出需要的 import 语句
    
    Args:
        code: Python 源代码
        
    Returns:
        需要添加的 import 语句集合
    """
    import re
    import ast
    
    # 提取代码中使用的所有名称
    used_names: set[str] = set()
    
    # 使用正则表达式找出所有标识符
    # 匹配 word boundary 的标识符
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
    for match in re.finditer(pattern, code):
        used_names.add(match.group(1))
    
    # 尝试解析 AST 获取更准确的名称
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # 处理 module.symbol 格式
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
    except SyntaxError:
        pass  # 代码有语法错误，使用正则结果
    
    # 找出已有的 import
    existing_imports: set[str] = set()
    import_pattern = r'^(?:from\s+(\w+)|import\s+(\w+))'
    for line in code.split('\n'):
        match = re.match(import_pattern, line.strip())
        if match:
            module = match.group(1) or match.group(2)
            if module:
                existing_imports.add(module)
    
    # 找出需要添加的 import
    required_imports: set[str] = set()
    
    for name in used_names:
        if name in IMPORT_REGISTRY:
            module, style = IMPORT_REGISTRY[name]
            # 检查模块是否已导入
            if module not in existing_imports:
                if style == "from":
                    required_imports.add(f"from {module} import {name}")
                else:
                    required_imports.add(f"import {module}")
    
    return required_imports


def generate_import_statements(required_imports: set[str]) -> str:
    """
    生成优化的 import 语句块
    合并同一模块的多个 from import
    
    Args:
        required_imports: import 语句集合
        
    Returns:
        格式化的 import 语句块
    """
    # 分类 import
    plain_imports: set[str] = set()
    from_imports: dict[str, set[str]] = {}
    
    for stmt in required_imports:
        if stmt.startswith("from "):
            # from module import symbol
            parts = stmt.split()
            if len(parts) >= 4:
                module = parts[1]
                symbol = parts[3]
                if module not in from_imports:
                    from_imports[module] = set()
                from_imports[module].add(symbol)
        else:
            plain_imports.add(stmt)
    
    # 生成输出
    lines = []
    
    # 先输出 import 语句
    for stmt in sorted(plain_imports):
        lines.append(stmt)
    
    # 再输出 from import 语句
    for module in sorted(from_imports.keys()):
        symbols = sorted(from_imports[module])
        if len(symbols) == 1:
            lines.append(f"from {module} import {symbols[0]}")
        else:
            lines.append(f"from {module} import {', '.join(symbols)}")
    
    return '\n'.join(lines)
