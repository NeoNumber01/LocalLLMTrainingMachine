
try:
    from metrics.codebleu_eval import HAS_NATIVE
    print(f"HAS_NATIVE in codebleu_eval: {HAS_NATIVE}")
except ImportError as e:
    print(f"ImportError importing codebleu_eval: {e}")

try:
    import metrics.native_codebleu
    print("Successfully imported metrics.native_codebleu")
except ImportError as e:
    print(f"Failed to import metrics.native_codebleu: {e}")
except Exception as e:
    print(f"Error importing metrics.native_codebleu: {e}")
