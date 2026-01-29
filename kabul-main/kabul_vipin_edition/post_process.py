# -*- coding: utf-8 -*-
"""
Post-Processing Pipeline for Java to C# Translation
Three-layer post-processing pipeline: Rule-based cleaning -> Formatting -> Compiler self-healing

Layer 1: Rule-based Cleaning (Regex)
Layer 2: Syntactic Formatting (dotnet format)
Layer 3: Compiler-Aided Self-Healing (dotnet build + heuristic fixes)
"""

import re
import os
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, List, Tuple


class PostProcessor:
    """
    Post-processor for Java to C# translated code.
    Applies a 3-layer pipeline to improve code quality and compilability.
    """

    def __init__(self, use_formatting: bool = True, use_healing: bool = True, verbose: bool = False):
        """
        Args:
            use_formatting: Enable Layer 2 (dotnet format)
            use_healing: Enable Layer 3 (compiler-aided self-healing)
            verbose: Print debug information
        """
        self.use_formatting = use_formatting
        self.use_healing = use_healing
        self.verbose = verbose
        self.temp_dir = tempfile.mkdtemp(prefix="csharp_healing_")
        self.stats = {"layer1_applied": 0, "layer2_applied": 0, "layer3_fixes": 0}

    def __del__(self):
        """Cleanup temp directory on destruction."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def process(self, code: str) -> str:
        """
        Main pipeline execution.
        
        Args:
            code: Raw translated C# code (possibly with Java artifacts)
        
        Returns:
            Cleaned and potentially healed C# code
        """
        if not code:
            return ""

        # Layer 1: Rule-based Cleaning
        code = self.clean_code(code)
        self.stats["layer1_applied"] += 1

        # Layers 2 & 3 require file operations
        if self.use_formatting or self.use_healing:
            try:
                file_path = os.path.join(self.temp_dir, "Solution.cs")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code)

                # Layer 2: Formatting
                if self.use_formatting:
                    if self._format_code(file_path):
                        self.stats["layer2_applied"] += 1

                # Layer 3: Healing
                if self.use_healing:
                    fixes = self._heal_code(file_path)
                    self.stats["layer3_fixes"] += fixes

                # Read back processed code
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()

            except FileNotFoundError as e:
                if self.verbose:
                    print(f"[PostProcessor] dotnet not found, skipping Layers 2 & 3: {e}")
            except Exception as e:
                if self.verbose:
                    print(f"[PostProcessor] Warning: Post-processing failed: {e}")

        return code

    # =========================================================================
    # Layer 1: Rule-based Cleaning
    # =========================================================================
    def clean_code(self, code: str) -> str:
        """
        Layer 1: Apply regex-based transformations to clean Java artifacts.
        
        This is the core cleaning layer that handles:
        - Markdown removal
        - Keyword/type mappings
        - Collection conversions
        - Annotation handling
        - Method signature fixes
        """
        if not code:
            return ""

        # 1. Remove Markdown code blocks
        code = self._remove_markdown(code)

        # 2. Remove conversational text (common LLM artifacts)
        code = self._remove_conversational_text(code)

        # 3. Primitive type mappings
        code = self._map_primitive_types(code)

        # 4. String method mappings
        code = self._map_string_methods(code)

        # 5. Collection type and method mappings
        code = self._map_collections(code)

        # 6. I/O mappings
        code = self._map_io(code)

        # 7. Annotation handling
        code = self._handle_annotations(code)

        # 8. Remove Java-specific constructs
        code = self._remove_java_specifics(code)

        # 9. Fix method casing (common Java -> C# issues)
        code = self._fix_method_casing(code)

        return code.strip()

    def _remove_markdown(self, code: str) -> str:
        """Remove Markdown code blocks."""
        # Match ```csharp ... ``` or ```cs ... ``` or just ``` ... ```
        match = re.search(r"```(?:csharp|cs|c#)?\s*(.*?)```", code, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return code

    def _remove_conversational_text(self, code: str) -> str:
        """Remove common LLM conversational prefixes/suffixes."""
        # Remove "Here is the code:" style prefixes
        patterns = [
            r"^Here\s+is\s+the\s+(?:converted\s+)?(?:C#\s+)?code[:\s]*",
            r"^The\s+(?:converted\s+)?(?:C#\s+)?code\s+is[:\s]*",
            r"^C#\s+(?:version|code)[:\s]*",
        ]
        for pattern in patterns:
            code = re.sub(pattern, "", code, flags=re.IGNORECASE | re.MULTILINE)
        return code

    def _map_primitive_types(self, code: str) -> str:
        """Map Java primitive wrapper types to C# equivalents."""
        mappings = {
            r"\bboolean\b": "bool",
            r"\bBoolean\b": "bool",
            r"\bInteger\b": "int",
            r"\bDouble\b": "double",
            r"\bFloat\b": "float",
            r"\bLong\b": "long",
            r"\bShort\b": "short",
            r"\bByte\b": "byte",
            r"\bCharacter\b": "char",
            r"\bString\b": "string",
        }
        for java_pattern, csharp_type in mappings.items():
            code = re.sub(java_pattern, csharp_type, code)
        return code

    def _map_string_methods(self, code: str) -> str:
        """Map Java String methods to C# equivalents."""
        # .length() -> .Length
        code = re.sub(r"\.length\(\)", ".Length", code)
        
        # .charAt(i) -> [i]
        code = re.sub(r"\.charAt\(([^)]+)\)", r"[\1]", code)
        
        # .substring(start, end) -> .Substring(start, end - start) [Complex, simplified]
        # For now, just fix casing: .substring -> .Substring
        code = re.sub(r"\.substring\(", ".Substring(", code)
        
        # .indexOf(...) -> .IndexOf(...)
        code = re.sub(r"\.indexOf\(", ".IndexOf(", code)
        code = re.sub(r"\.lastIndexOf\(", ".LastIndexOf(", code)
        
        # .equals(...) -> .Equals(...)
        code = re.sub(r"\.equals\(", ".Equals(", code)
        code = re.sub(r"\.equalsIgnoreCase\(", ".Equals(", code)  # Simplified
        
        # .toLowerCase() -> .ToLower()
        code = re.sub(r"\.toLowerCase\(\)", ".ToLower()", code)
        code = re.sub(r"\.toUpperCase\(\)", ".ToUpper()", code)
        
        # .trim() -> .Trim()
        code = re.sub(r"\.trim\(\)", ".Trim()", code)
        
        # .split(...) -> .Split(...)
        code = re.sub(r"\.split\(", ".Split(", code)
        
        # .replace(...) -> .Replace(...)
        code = re.sub(r"\.replace\(", ".Replace(", code)
        
        # .startsWith(...) -> .StartsWith(...)
        code = re.sub(r"\.startsWith\(", ".StartsWith(", code)
        code = re.sub(r"\.endsWith\(", ".EndsWith(", code)
        
        # .contains(...) -> .Contains(...)
        code = re.sub(r"\.contains\(", ".Contains(", code)
        
        # .isEmpty() -> string.IsNullOrEmpty(...) or .Length == 0
        # Simplified: .isEmpty() -> .Length == 0 (requires context, risky)
        # Leave as-is for now, let compiler catch it
        
        return code

    def _map_collections(self, code: str) -> str:
        """Map Java collection types and methods to C# equivalents."""
        # Type mappings
        code = re.sub(r"\bArrayList\s*<", "List<", code)
        code = re.sub(r"\bLinkedList\s*<", "LinkedList<", code)
        code = re.sub(r"\bHashMap\s*<", "Dictionary<", code)
        code = re.sub(r"\bTreeMap\s*<", "SortedDictionary<", code)
        code = re.sub(r"\bHashSet\s*<", "HashSet<", code)
        code = re.sub(r"\bTreeSet\s*<", "SortedSet<", code)
        
        # new ArrayList<>() -> new List<Type>() [Diamond operator removal]
        code = re.sub(r"new\s+(List|Dictionary|HashSet|SortedSet|LinkedList|SortedDictionary)\s*<\s*>", r"new \1<dynamic>", code)
        
        # Method mappings
        code = re.sub(r"\.add\(", ".Add(", code)
        code = re.sub(r"\.remove\(", ".Remove(", code)
        code = re.sub(r"\.clear\(\)", ".Clear()", code)
        code = re.sub(r"\.size\(\)", ".Count", code)
        code = re.sub(r"\.isEmpty\(\)", ".Count == 0", code)
        
        # .get(index) -> [index] for lists (simplified, may not always be correct)
        # This is risky, so we'll be conservative
        # code = re.sub(r"\.get\(([^)]+)\)", r"[\1]", code)
        
        # .put(k, v) -> [k] = v (for dictionaries, complex transformation)
        # Leave for compiler to catch
        
        # .containsKey(...) -> .ContainsKey(...)
        code = re.sub(r"\.containsKey\(", ".ContainsKey(", code)
        code = re.sub(r"\.containsValue\(", ".ContainsValue(", code)
        
        # Iterator patterns: .iterator() -> .GetEnumerator()
        code = re.sub(r"\.iterator\(\)", ".GetEnumerator()", code)
        code = re.sub(r"\.hasNext\(\)", ".MoveNext()", code)  # Simplified
        
        return code

    def _map_io(self, code: str) -> str:
        """Map Java I/O to C# equivalents."""
        code = re.sub(r"System\.out\.println", "Console.WriteLine", code)
        code = re.sub(r"System\.out\.print\b", "Console.Write", code)
        code = re.sub(r"System\.err\.println", "Console.Error.WriteLine", code)
        code = re.sub(r"System\.err\.print\b", "Console.Error.Write", code)
        return code

    def _handle_annotations(self, code: str) -> str:
        """Convert or remove Java annotations."""
        # @Override -> remove (C# uses 'override' keyword)
        code = re.sub(r"@Override\s*\n?", "", code)
        
        # @Deprecated -> [Obsolete]
        code = re.sub(r"@Deprecated\s*\n?", "[Obsolete]\n", code)
        
        # @Nullable -> remove (C# nullable is handled differently)
        code = re.sub(r"@Nullable\s*", "", code)
        code = re.sub(r"@NonNull\s*", "", code)
        code = re.sub(r"@NotNull\s*", "", code)
        
        # @SuppressWarnings(...) -> remove
        code = re.sub(r"@SuppressWarnings\s*\([^)]*\)\s*\n?", "", code)
        
        # @FunctionalInterface -> remove
        code = re.sub(r"@FunctionalInterface\s*\n?", "", code)
        
        # Other common annotations to remove
        code = re.sub(r"@Serial\s*\n?", "", code)
        code = re.sub(r"@SafeVarargs\s*\n?", "", code)
        
        return code

    def _remove_java_specifics(self, code: str) -> str:
        """Remove Java-specific constructs that have no C# equivalent."""
        # Remove package declarations
        code = re.sub(r"^\s*package\s+[\w.]+;\s*\n?", "", code, flags=re.MULTILINE)
        
        # Remove import statements (C# uses 'using')
        # Note: We could convert these, but it's complex. Better to remove and let compiler guide.
        code = re.sub(r"^\s*import\s+[\w.*]+;\s*\n?", "", code, flags=re.MULTILINE)
        
        # Remove 'throws' clause from method signatures
        code = re.sub(r"\s+throws\s+[\w,\s]+(?=\s*\{)", "", code)
        
        # Remove 'final' modifier on method parameters (C# doesn't need it)
        code = re.sub(r"\bfinal\s+(?=\w+\s+\w+\s*[,)])", "", code)
        
        # 'extends' -> ':' (for class inheritance, simplified)
        code = re.sub(r"\bextends\s+", ": ", code)
        
        # 'implements' -> ':' or ',' (for interfaces)
        code = re.sub(r"\bimplements\s+", ": ", code)
        
        return code

    def _fix_method_casing(self, code: str) -> str:
        """Fix common Java method names to C# PascalCase."""
        # Common method casing fixes
        mappings = {
            r"\.toString\(\)": ".ToString()",
            r"\.hashCode\(\)": ".GetHashCode()",
            r"\.getClass\(\)": ".GetType()",
            r"\.notify\(\)": ".Notify()",  # Won't compile, but closer
            r"\.wait\(\)": ".Wait()",
            r"\.compareTo\(": ".CompareTo(",
            r"\.clone\(\)": ".Clone()",
        }
        for java_method, csharp_method in mappings.items():
            code = re.sub(java_method, csharp_method, code)
        return code

    # =========================================================================
    # Layer 2: Syntactic Formatting
    # =========================================================================
    def _format_code(self, file_path: str) -> bool:
        """
        Layer 2: Apply dotnet format to the code file.
        
        Returns:
            True if formatting was applied successfully
        """
        self._ensure_csproj()
        
        try:
            cmd = ["dotnet", "format", self.temp_dir, "--verbosity", "quiet"]
            result = subprocess.run(
                cmd,
                cwd=self.temp_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # =========================================================================
    # Layer 3: Compiler-Aided Self-Healing
    # =========================================================================
    def _heal_code(self, file_path: str, max_attempts: int = 3) -> int:
        """
        Layer 3: Iteratively compile and fix errors.
        
        Returns:
            Number of fixes applied
        """
        self._ensure_csproj()
        total_fixes = 0

        for attempt in range(max_attempts):
            # Compile
            result = subprocess.run(
                ["dotnet", "build", self.temp_dir, "--nologo", "-v", "q"],
                capture_output=True,
                cwd=self.temp_dir,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0:
                break  # Success

            # Parse errors
            errors = self._parse_errors(result.stdout + result.stderr)
            if not errors:
                break  # Unknown errors

            # Apply fixes
            fixes_applied = self._apply_fixes(file_path, errors)
            if fixes_applied == 0:
                break  # No fixes possible

            total_fixes += fixes_applied

        return total_fixes

    def _ensure_csproj(self):
        """Create a dummy .csproj if it doesn't exist."""
        csproj_path = os.path.join(self.temp_dir, "Project.csproj")
        if not os.path.exists(csproj_path):
            content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <WarningsAsErrors></WarningsAsErrors>
  </PropertyGroup>
</Project>"""
            with open(csproj_path, "w") as f:
                f.write(content)

    def _parse_errors(self, build_output: str) -> List[Dict]:
        """Parse compiler error output into structured format."""
        errors = []
        # Pattern: path(line,col): error CSxxxx: message
        pattern = re.compile(r"([^\(]+)\((\d+),(\d+)\):\s*error\s+(CS\d+):\s*(.*)")
        
        for line in build_output.splitlines():
            m = pattern.search(line)
            if m:
                errors.append({
                    "file": m.group(1).strip(),
                    "line": int(m.group(2)),
                    "col": int(m.group(3)),
                    "code": m.group(4),
                    "msg": m.group(5).strip()
                })
        return errors

    def _apply_fixes(self, file_path: str, errors: List[Dict]) -> int:
        """Apply heuristic fixes based on compiler errors."""
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        fixes_applied = 0
        errors.sort(key=lambda x: x["line"], reverse=True)

        for err in errors:
            line_idx = err["line"] - 1
            if line_idx < 0 or line_idx >= len(lines):
                continue

            line_content = lines[line_idx]
            code = err["code"]
            msg = err["msg"]

            # CS1002: ; expected
            if code == "CS1002":
                lines[line_idx] = line_content.rstrip() + ";\n"
                fixes_applied += 1

            # CS0103: The name 'xxx' does not exist in the current context
            elif code == "CS0103":
                if "Console" in msg or "Math" in msg:
                    if not any("using System;" in l for l in lines):
                        lines.insert(0, "using System;\n")
                        fixes_applied += 1

            # CS0246: The type or namespace name 'xxx' could not be found
            elif code == "CS0246":
                # System.Collections.Generic
                if any(x in msg for x in ["List", "Dictionary", "HashSet", "LinkedList", "SortedDictionary", "Queue", "Stack"]):
                    if not any("using System.Collections.Generic;" in l for l in lines):
                        lines.insert(0, "using System.Collections.Generic;\n")
                        fixes_applied += 1
                # System.Text.RegularExpressions
                elif "Regex" in msg:
                    if not any("using System.Text.RegularExpressions;" in l for l in lines):
                        lines.insert(0, "using System.Text.RegularExpressions;\n")
                        fixes_applied += 1
                # System.Linq
                elif any(x in msg for x in ["Select", "Where", "ToList", "ToArray", "Any", "All", "FirstOrDefault"]):
                    # Note: These are extensions, so CS1061 might also trigger, but sometimes CS0246 if called statically or confusion
                    # Usually LINQ methods on collections trigger CS1061, but if the compiler thinks it's a type...
                    # More commonly, missing LINQ triggers CS1061. 
                    # But if 'Enumerable' or 'Queryable' is mentioned:
                    if not any("using System.Linq;" in l for l in lines):
                        lines.insert(0, "using System.Linq;\n")
                        fixes_applied += 1
                # System.IO
                elif any(x in msg for x in ["File", "Directory", "Path", "StreamReader", "StreamWriter", "FileStream"]):
                    if not any("using System.IO;" in l for l in lines):
                        lines.insert(0, "using System.IO;\n")
                        fixes_applied += 1
                # System.Text
                elif "StringBuilder" in msg:
                    if not any("using System.Text;" in l for l in lines):
                        lines.insert(0, "using System.Text;\n")
                        fixes_applied += 1

            # CS1955: Non-invocable member '...' cannot be used like a method.
            # Example: list.Count(); -> list.Count;
            elif code == "CS1955":
                # We need to find the token that is being called as a method.
                # msg usually says: "Non-invocable member 'List<string>.Count' cannot be used like a method."
                # Regex to extract member name: 'Type.Member' or just 'Member'
                match = re.search(r"'([^']+)'", msg)
                if match:
                    member_full = match.group(1)
                    member_name = member_full.split('.')[-1] # Extract 'Count' from 'List<string>.Count'
                    
                    # Look for member_name followed by parenthesis ()
                    # We only want to remove the parenthesis.
                    # e.g. .Count() -> .Count
                    
                    # Pattern: member_name\s*\(
                    # We be careful not to match if it has arguments? 
                    # CS1955 typically means it's a property/field, so it shouldn't have args if it was intended to be a simple getter.
                    # But if it has args, just removing () might leave args dangling.
                    # Usually this happens for .Length(), .Count(). 
                    
                    regex = rf"(\.{re.escape(member_name)})\s*\(\s*\)"
                    if re.search(regex, line_content):
                        lines[line_idx] = re.sub(regex, r"\1", line_content)
                        fixes_applied += 1

            # CS0117 / CS1061: 'type' does not contain a definition for 'member'
            elif code in ("CS0117", "CS1061"):
                # 1. Check for "Did you mean 'X'?"
                did_you_mean = re.search(r"Did you mean '([^']+)'\?", msg)
                if did_you_mean:
                    suggestion = did_you_mean.group(1)
                    # Extract the wrong member name from the error message if possible,
                    # or just heuristic search in the line.
                    # Message: 'string' does not contain a definition for 'length' ...
                    wrong_member_match = re.search(r"definition for '([^']+)'", msg)
                    if wrong_member_match:
                        wrong_member = wrong_member_match.group(1)
                        if wrong_member in line_content:
                            lines[line_idx] = line_content.replace(wrong_member, suggestion)
                            fixes_applied += 1
                            continue # Skip the loop below

                # 2. Try common Java -> C# method replacements (Fallback)
                replacements = [
                    (".toString()", ".ToString()"),
                    (".length", ".Length"),
                    (".size()", ".Count"),
                    (".equals(", ".Equals("),
                    (".add(", ".Add("),
                    (".get(", "["),  # Risky but try
                    (".toLowerCase()", ".ToLower()"),
                    (".toUpperCase()", ".ToUpper()"),
                ]
                for java_form, csharp_form in replacements:
                    if java_form in line_content:
                        lines[line_idx] = line_content.replace(java_form, csharp_form)
                        fixes_applied += 1
                        break
                
                # 3. Missing LINQ check (Commonly triggers CS1061 for Select/Where/etc)
                if any(x in msg for x in ["Select", "Where", "ToList", "ToArray", "Any", "All", "FirstOrDefault"]):
                     if not any("using System.Linq;" in l for l in lines):
                        lines.insert(0, "using System.Linq;\n")
                        fixes_applied += 1

            # CS1519: Invalid token - often stray Java keywords
            elif code == "CS1519":
                # Try removing 'throws' clause if still present
                if "throws" in line_content:
                    lines[line_idx] = re.sub(r"\s+throws\s+[\w,\s]+(?=\s*\{)", "", line_content)
                    fixes_applied += 1

        if fixes_applied > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

        return fixes_applied

    def get_stats(self) -> Dict:
        """Return processing statistics."""
        return self.stats.copy()


# =============================================================================
# Convenience Functions
# =============================================================================

def post_process(code: str, use_formatting: bool = True, use_healing: bool = True) -> str:
    """
    Convenience function for one-off post-processing.
    
    Args:
        code: Raw translated C# code
        use_formatting: Enable dotnet format
        use_healing: Enable compiler-aided healing
    
    Returns:
        Processed C# code
    """
    processor = PostProcessor(use_formatting=use_formatting, use_healing=use_healing)
    return processor.process(code)


if __name__ == "__main__":
    # Quick test
    test_code = '''```csharp
package com.example;

import java.util.ArrayList;

public class Test {
    @Override
    public String toString() {
        ArrayList<String> list = new ArrayList<>();
        list.add("hello");
        System.out.println(list.size());
        return list.get(0).toLowerCase();
    }
}
```'''
    
    processor = PostProcessor(use_formatting=False, use_healing=False, verbose=True)
    result = processor.process(test_code)
    print("=== Processed Code ===")
    print(result)
