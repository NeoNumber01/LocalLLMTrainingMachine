import json
import os
from collections import defaultdict
from datasets import Dataset
from transformers import AutoTokenizer

class JavaCSharpDataset:
    def __init__(self, config, tokenizer):
        self.config = config
        self.tokenizer = tokenizer
        
    def _load_json_lines(self, path):
        """Load JSON file with one object per line or a list of objects."""
        data = []
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Try parsing as a single list first
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            
            # Fallback to lines
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Skipping invalid line in {path}")
        return data

    def _get_description(self, item):
        """
        Extract description for alignment. 
        Splits by '|' to remove language-specific suffixes (e.g., ' | Java Program...').
        """
        text = item.get('text', '').strip()
        if '|' in text:
            return text.split('|')[0].strip()
        return text

    def align_data(self, java_path, csharp_path):
        """
        Aligns Java and C# datasets based on description text.
        Includes code-level deduplication to remove duplicate code snippets.
        """
        print(f"Loading data from {java_path} and {csharp_path}...")
        java_data = self._load_json_lines(java_path)
        csharp_data = self._load_json_lines(csharp_path)
        
        # Group by description
        java_by_desc = defaultdict(list)
        for item in java_data:
            desc = self._get_description(item)
            if desc:
                java_by_desc[desc].append(item)
                
        csharp_by_desc = defaultdict(list)
        for item in csharp_data:
            desc = self._get_description(item)
            if desc:
                csharp_by_desc[desc].append(item)
                
        # Align
        aligned_pairs = []
        processed_descs = set()
        
        # Iterate through Java descriptions to find matches in C#
        for item in java_data:
            desc = self._get_description(item)
            
            if desc not in csharp_by_desc:
                continue
                
            if desc in processed_descs:
                continue
                
            java_list = java_by_desc[desc]
            csharp_list = csharp_by_desc[desc]
            
            # Match minimum count
            count = min(len(java_list), len(csharp_list))
            
            for k in range(count):
                aligned_pairs.append({
                    "java_code": java_list[k]['code'],
                    "csharp_code": csharp_list[k]['code'],
                    "description": desc
                })
            
            processed_descs.add(desc)
        
        print(f"Aligned {len(aligned_pairs)} pairs (before dedup)...")
        
        # Code-level deduplication
        seen_java = set()
        seen_csharp = set()
        deduped_pairs = []
        
        for pair in aligned_pairs:
            java_hash = hash(pair["java_code"])
            csharp_hash = hash(pair["csharp_code"])
            
            # Skip if either code has been seen before
            if java_hash in seen_java or csharp_hash in seen_csharp:
                continue
                
            seen_java.add(java_hash)
            seen_csharp.add(csharp_hash)
            deduped_pairs.append(pair)
        
        print(f"After dedup: {len(deduped_pairs)} pairs from {len(java_data)} Java and {len(csharp_data)} C# samples.")
        return deduped_pairs


    def preprocess_function(self, examples):
        inputs = ["translate Java to C#: " + code for code in examples["java_code"]]
        targets = examples["csharp_code"]
        
        model_inputs = self.tokenizer(
            inputs, 
            max_length=self.config.max_length, 
            padding="max_length", 
            truncation=True
        )
        
        labels = self.tokenizer(
            targets, 
            max_length=self.config.max_length, 
            padding="max_length", 
            truncation=True
        )
        
        # Replace padding token id's of the labels by -100 so it's ignored by the loss
        labels["input_ids"] = [
            [(l if l != self.tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
        ]
        
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    def get_train_dataset(self):
        pairs = self.align_data(self.config.java_train_path, self.config.csharp_train_path)
        dataset = Dataset.from_list(pairs)
        return dataset.map(self.preprocess_function, batched=True, remove_columns=dataset.column_names)

    def get_valid_dataset(self):
        pairs = self.align_data(self.config.java_valid_path, self.config.csharp_valid_path)
        dataset = Dataset.from_list(pairs)
        return dataset.map(self.preprocess_function, batched=True, remove_columns=dataset.column_names)
