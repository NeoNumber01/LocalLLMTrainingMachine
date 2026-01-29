
import tree_sitter
import tree_sitter_c_sharp

def debug_query():
    try:
        lang = tree_sitter.Language(tree_sitter_c_sharp.language(), "c_sharp")
        parser = tree_sitter.Parser()
        parser.set_language(lang)
        
        code = b"public void M() { int a = 1; int b = a; }"
        tree = parser.parse(code)
        
        query_str = "(identifier) @id"
        query = lang.query(query_str)
        
        print("Running captures...")
        captures = query.captures(tree.root_node)
        
        print(f"Result type: {type(captures)}")
        print(f"Result length: {len(captures)}")
        
        if len(captures) > 0:
            first = captures[0]
            print(f"First item type: {type(first)}")
            print(f"First item: {first}")
            
            # Attempt unpack
            if isinstance(first, tuple):
                print("Item is tuple")
                if len(first) == 2:
                    node, name = first
                    print(f"Node: {node}, Name: {name}")
                    print(f"Node text: {code[node.start_byte:node.end_byte]}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_query()
