"""
Import Registry Module
300+ common standard library symbol to module mappings for automatic dependency injection
"""

# =============================================================================
# Symbol to Module Mapping
# Format: "symbol": ("module", "import_style")
# import_style: "from" = from module import symbol
#               "import" = import module (use module.symbol)
# =============================================================================

IMPORT_REGISTRY: dict[str, tuple[str, str]] = {
    # =========================================================================
    # typing module
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
    # collections module
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
    # math module
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
    # itertools module
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
    # functools module
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
    # heapq module
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
    # bisect module
    # =========================================================================
    "bisect": ("bisect", "from"),
    "bisect_left": ("bisect", "from"),
    "bisect_right": ("bisect", "from"),
    "insort": ("bisect", "from"),
    "insort_left": ("bisect", "from"),
    "insort_right": ("bisect", "from"),
    
    # =========================================================================
    # operator module
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
    # random module
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
    # re module
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
    # string module
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
    # datetime module
    # =========================================================================
    "datetime": ("datetime", "from"),
    "date": ("datetime", "from"),
    "time": ("datetime", "from"),
    "timedelta": ("datetime", "from"),
    "timezone": ("datetime", "from"),
    
    # =========================================================================
    # copy module
    # =========================================================================
    "copy": ("copy", "from"),
    "deepcopy": ("copy", "from"),
    
    # =========================================================================
    # json module
    # =========================================================================
    "dumps": ("json", "from"),
    "loads": ("json", "from"),
    "dump": ("json", "from"),
    "load": ("json", "from"),
    
    # =========================================================================
    # sys module (special handling)
    # =========================================================================
    "maxsize": ("sys", "from"),
    "setrecursionlimit": ("sys", "from"),
    "getrecursionlimit": ("sys", "from"),
    "stdin": ("sys", "from"),
    "stdout": ("sys", "from"),
    "stderr": ("sys", "from"),
    
    # =========================================================================
    # Whole module imports (use module.symbol format)
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
    Analyze code to find required import statements
    
    Args:
        code: Python source code
        
    Returns:
        Set of import statements to add
    """
    import re
    import ast
    
    # Extract all names used in code
    used_names: set[str] = set()
    
    # Use regex to find all identifiers
    # Match word boundary identifiers
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
    for match in re.finditer(pattern, code):
        used_names.add(match.group(1))
    
    # Try parsing AST for more accurate names
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Handle module.symbol format
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
    except SyntaxError:
        pass  # Code has syntax error, use regex results
    
    # Find existing imports
    existing_imports: set[str] = set()
    import_pattern = r'^(?:from\s+(\w+)|import\s+(\w+))'
    for line in code.split('\n'):
        match = re.match(import_pattern, line.strip())
        if match:
            module = match.group(1) or match.group(2)
            if module:
                existing_imports.add(module)
    
    # Find required imports
    required_imports: set[str] = set()
    
    for name in used_names:
        if name in IMPORT_REGISTRY:
            module, style = IMPORT_REGISTRY[name]
            # Check if module is already imported
            if module not in existing_imports:
                if style == "from":
                    required_imports.add(f"from {module} import {name}")
                else:
                    required_imports.add(f"import {module}")
    
    return required_imports


def generate_import_statements(required_imports: set[str]) -> str:
    """
    Generate optimized import statement block
    Merge multiple from imports from same module
    
    Args:
        required_imports: Set of import statements
        
    Returns:
        Formatted import statement block
    """
    # Categorize imports
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
    
    # Generate output
    lines = []
    
    # Output import statements first
    for stmt in sorted(plain_imports):
        lines.append(stmt)
    
    # Then output from import statements
    for module in sorted(from_imports.keys()):
        symbols = sorted(from_imports[module])
        if len(symbols) == 1:
            lines.append(f"from {module} import {symbols[0]}")
        else:
            lines.append(f"from {module} import {', '.join(symbols)}")
    
    return '\n'.join(lines)
