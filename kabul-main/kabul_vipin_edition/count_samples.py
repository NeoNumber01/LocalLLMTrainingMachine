

def count_samples(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip())
    except FileNotFoundError:
        return "File not found"

train_java = "xlcost_data/data/Java-program-level/train.json"
train_csharp = "xlcost_data/data/Csharp-program-level/train.json"
test_java = "xlcost_data/data/Java-program-level/test.json"
test_csharp = "xlcost_data/data/Csharp-program-level/test.json"

print(f"Java Train: {count_samples(train_java)}")
print(f"C# Train: {count_samples(train_csharp)}")
print(f"Java Test: {count_samples(test_java)}")
print(f"C# Test: {count_samples(test_csharp)}")

