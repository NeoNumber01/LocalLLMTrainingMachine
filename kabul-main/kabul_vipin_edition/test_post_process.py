# -*- coding: utf-8 -*-
"""
Unit tests for the enhanced PostProcessor
"""

import unittest
import os
from post_process import PostProcessor


class TestLayer1RuleBasedCleaning(unittest.TestCase):
    """Tests for Layer 1: Rule-based Cleaning"""

    def setUp(self):
        self.processor = PostProcessor(use_formatting=False, use_healing=False)

    # -------------------------------------------------------------------------
    # Markdown Removal
    # -------------------------------------------------------------------------
    def test_remove_markdown_csharp(self):
        raw = "```csharp\npublic class Test {}\n```"
        result = self.processor.clean_code(raw)
        self.assertEqual(result, "public class Test {}")

    def test_remove_markdown_cs(self):
        raw = "```cs\npublic class Test {}\n```"
        result = self.processor.clean_code(raw)
        self.assertEqual(result, "public class Test {}")

    # -------------------------------------------------------------------------
    # Primitive Type Mappings
    # -------------------------------------------------------------------------
    def test_boolean_to_bool(self):
        raw = "public boolean isValid() { return true; }"
        result = self.processor.clean_code(raw)
        self.assertIn("bool", result)
        self.assertNotIn("boolean", result)

    def test_integer_to_int(self):
        raw = "Integer count = 10;"
        result = self.processor.clean_code(raw)
        self.assertIn("int count", result)

    def test_string_lowercase(self):
        raw = "String name = \"test\";"
        result = self.processor.clean_code(raw)
        self.assertIn("string name", result)

    # -------------------------------------------------------------------------
    # String Method Mappings
    # -------------------------------------------------------------------------
    def test_length_method(self):
        raw = "int len = str.length();"
        result = self.processor.clean_code(raw)
        self.assertIn(".Length", result)
        self.assertNotIn(".length()", result)

    def test_charat_to_indexer(self):
        raw = "char c = str.charAt(0);"
        result = self.processor.clean_code(raw)
        self.assertIn("str[0]", result)

    def test_substring_casing(self):
        raw = "String sub = str.substring(1, 5);"
        result = self.processor.clean_code(raw)
        self.assertIn(".Substring(", result)

    def test_tolowercase(self):
        raw = "String lower = str.toLowerCase();"
        result = self.processor.clean_code(raw)
        self.assertIn(".ToLower()", result)

    def test_equals(self):
        raw = "if (a.equals(b)) {}"
        result = self.processor.clean_code(raw)
        self.assertIn(".Equals(", result)

    # -------------------------------------------------------------------------
    # Collection Mappings
    # -------------------------------------------------------------------------
    def test_arraylist_to_list(self):
        raw = "ArrayList<String> list = new ArrayList<>();"
        result = self.processor.clean_code(raw)
        self.assertIn("List<", result)
        self.assertNotIn("ArrayList", result)

    def test_hashmap_to_dictionary(self):
        raw = "HashMap<String, Integer> map = new HashMap<>();"
        result = self.processor.clean_code(raw)
        self.assertIn("Dictionary<", result)

    def test_size_to_count(self):
        raw = "int n = list.size();"
        result = self.processor.clean_code(raw)
        self.assertIn(".Count", result)
        self.assertNotIn(".size()", result)

    def test_add_to_Add(self):
        raw = "list.add(item);"
        result = self.processor.clean_code(raw)
        self.assertIn(".Add(", result)

    def test_isEmpty_to_count_zero(self):
        raw = "if (list.isEmpty()) {}"
        result = self.processor.clean_code(raw)
        self.assertIn(".Count == 0", result)

    # -------------------------------------------------------------------------
    # I/O Mappings
    # -------------------------------------------------------------------------
    def test_system_out_println(self):
        raw = "System.out.println(\"Hello\");"
        result = self.processor.clean_code(raw)
        self.assertIn("Console.WriteLine", result)

    def test_system_err_println(self):
        raw = "System.err.println(\"Error\");"
        result = self.processor.clean_code(raw)
        self.assertIn("Console.Error.WriteLine", result)

    # -------------------------------------------------------------------------
    # Annotation Handling
    # -------------------------------------------------------------------------
    def test_remove_override(self):
        raw = "@Override\npublic void run() {}"
        result = self.processor.clean_code(raw)
        self.assertNotIn("@Override", result)
        self.assertIn("public void run()", result)

    def test_deprecated_to_obsolete(self):
        raw = "@Deprecated\npublic void oldMethod() {}"
        result = self.processor.clean_code(raw)
        self.assertIn("[Obsolete]", result)
        self.assertNotIn("@Deprecated", result)

    def test_remove_nullable(self):
        raw = "@Nullable String name;"
        result = self.processor.clean_code(raw)
        self.assertNotIn("@Nullable", result)

    def test_remove_suppresswarnings(self):
        raw = "@SuppressWarnings(\"unchecked\")\npublic void test() {}"
        result = self.processor.clean_code(raw)
        self.assertNotIn("@SuppressWarnings", result)

    # -------------------------------------------------------------------------
    # Java Specifics Removal
    # -------------------------------------------------------------------------
    def test_remove_package(self):
        raw = "package com.example;\npublic class Test {}"
        result = self.processor.clean_code(raw)
        self.assertNotIn("package", result)

    def test_remove_import(self):
        raw = "import java.util.List;\npublic class Test {}"
        result = self.processor.clean_code(raw)
        self.assertNotIn("import", result)

    def test_remove_throws(self):
        raw = "public void test() throws Exception { }"
        result = self.processor.clean_code(raw)
        self.assertNotIn("throws", result)
        self.assertIn("public void test()", result)

    def test_extends_to_colon(self):
        raw = "public class Dog extends Animal {}"
        result = self.processor.clean_code(raw)
        self.assertIn(": Animal", result)
        self.assertNotIn("extends", result)

    # -------------------------------------------------------------------------
    # Method Casing
    # -------------------------------------------------------------------------
    def test_tostring_casing(self):
        raw = "String s = obj.toString();"
        result = self.processor.clean_code(raw)
        self.assertIn(".ToString()", result)

    def test_hashcode_casing(self):
        raw = "int h = obj.hashCode();"
        result = self.processor.clean_code(raw)
        self.assertIn(".GetHashCode()", result)


class TestFullPipeline(unittest.TestCase):
    """Tests for the full pipeline with graceful fallback"""

    def test_pipeline_without_dotnet(self):
        """Ensure pipeline doesn't crash when dotnet is missing"""
        processor = PostProcessor(use_formatting=True, use_healing=True)
        raw = "public boolean foo() { return true; }"
        result = processor.process(raw)
        # Should at least apply Layer 1 cleaning
        self.assertIn("bool", result)

    def test_comprehensive_java_to_csharp(self):
        """Test a comprehensive Java snippet"""
        raw = '''```csharp
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
        processor = PostProcessor(use_formatting=False, use_healing=False)
        result = processor.process(raw)
        
        # Verify key transformations
        self.assertNotIn("package", result)
        self.assertNotIn("import", result)
        self.assertNotIn("@Override", result)
        self.assertIn("List<", result)
        self.assertIn(".Add(", result)
        self.assertIn(".Count", result)
        self.assertIn("Console.WriteLine", result)
        self.assertIn(".ToLower()", result)


class TestStatistics(unittest.TestCase):
    """Test processing statistics"""

    def test_stats_tracking(self):
        processor = PostProcessor(use_formatting=False, use_healing=False)
        processor.process("boolean x = true;")
        processor.process("String y = \"test\";")
        
        stats = processor.get_stats()
        self.assertEqual(stats["layer1_applied"], 2)



class TestLayer3SelfHealingLogic(unittest.TestCase):
    """
    Tests for Layer 3 Self-Healing Logic.
    Since we cannot easily invoke dotnet build in this env, we test _apply_fixes directly
    by mocking the error structures.
    """
    def setUp(self):
        self.processor = PostProcessor(use_formatting=False, use_healing=False)
        self.temp_file = "test_healing_mock.cs"
    
    def tearDown(self):
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

    def _apply_fixes_helper(self, content, errors):
        with open(self.temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        fixes = self.processor._apply_fixes(self.temp_file, errors)
        
        with open(self.temp_file, "r", encoding="utf-8") as f:
            new_content = f.read()
        return fixes, new_content

    def test_cs1955_remove_parentheses(self):
        # Error: Non-invocable member 'List<string>.Count' cannot be used like a method.
        content = "int n = list.Count();"
        errors = [{
            "line": 1, "col": 1, "code": "CS1955", 
            "msg": "Non-invocable member 'List<string>.Count' cannot be used like a method."
        }]
        
        fixes, new_content = self._apply_fixes_helper(content, errors)
        self.assertEqual(fixes, 1)
        self.assertEqual(new_content.strip(), "int n = list.Count;")

    def test_cs0246_missing_linq(self):
        content = "var x = list.Where(i => i > 0).ToList();"
        errors = [{"line": 1, "col": 1, "code": "CS0246", "msg": "The type or namespace name 'Where' could not be found"}]
        # Note: Often this is CS1061, but our logic handles CS0246 or CS1061 for Linq keywords
        
        fixes, new_content = self._apply_fixes_helper(content, errors)
        self.assertEqual(fixes, 1)
        self.assertIn("using System.Linq;", new_content)

    def test_cs0246_missing_io(self):
        content = "File.ReadAllText(\"path\");"
        errors = [{"line": 1, "col": 1, "code": "CS0246", "msg": "The name 'File' does not exist..."}]
        
        fixes, new_content = self._apply_fixes_helper(content, errors)
        self.assertEqual(fixes, 1)
        self.assertIn("using System.IO;", new_content)

    def test_cs1061_did_you_mean(self):
        content = "int len = str.length;"
        # Typical Roslyn message: 'string' does not contain a definition for 'length' ... Did you mean 'Length'?
        errors = [{
            "line": 1, "col": 1, "code": "CS1061", 
            "msg": "'string' does not contain a definition for 'length' and no accessible extension method ... Did you mean 'Length'?"
        }]
        
        fixes, new_content = self._apply_fixes_helper(content, errors)
        self.assertEqual(fixes, 1)
        self.assertEqual(new_content.strip(), "int len = str.Length;")


if __name__ == "__main__":
    unittest.main(verbosity=2)
