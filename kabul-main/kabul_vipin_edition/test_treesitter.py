
import tree_sitter
import tree_sitter_c_sharp

def test_parsing():
    try:
        # Try passing the name argument
        print("Creating Language with name...")
        try:
            CS_LANGUAGE = tree_sitter.Language(tree_sitter_c_sharp.language(), "c_sharp")
        except TypeError:
             # If it still fails, try using tree_sitter_c_sharp.language() directly
            print("Direct instantiation failed, trying raw capsule...")
            CS_LANGUAGE = tree_sitter_c_sharp.language()

        parser = tree_sitter.Parser()
        parser.set_language(CS_LANGUAGE)
        
        code = b"public class Test { public void M() { int a = 1; } }"
        tree = parser.parse(code)
        
        print("Root node type:", tree.root_node.type)
        print("S-expression:", tree.root_node.sexp())
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_parsing()
