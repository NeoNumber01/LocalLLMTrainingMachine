import os

# Directory containing the files
source_dir = r"c:\Users\Shu Leo\Desktop\practical course\kabul-main\论文材料"
output_file = os.path.join(source_dir, "merged_documents.md")

# List of files to merge (based on previous list_dir, filtering for .md and excluding the output file itself if it exists)
# The user said "all documents", assuming .md files based on previous context.
files_to_merge = [
    "research_paper_report.md",
    "research_paper_reportEnglish.md",
    "train_report.md",
    "项目技术文档.md"
]

def merge_files():
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for filename in files_to_merge:
            filepath = os.path.join(source_dir, filename)
            if os.path.exists(filepath):
                # Write the filename as a header
                outfile.write(f"# {filename}\n\n")
                
                with open(filepath, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
                
                # Add some separation
                outfile.write("\n\n---\n\n")
                print(f"Merged {filename}")
            else:
                print(f"Warning: {filename} not found.")

if __name__ == "__main__":
    merge_files()
    print(f"All files merged into {output_file}")
