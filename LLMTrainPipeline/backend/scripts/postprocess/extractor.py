"""
Code Extraction Module v2.0 - Enhanced Version
Extract clean Python code from LLM raw output

Supported formats:
- Markdown code blocks (```, ~~~)
- XML/HTML tags (<code>, <solution>, <answer>, <artifact>)
- JSON wrapper ({"code": "..."})
- Model-specific formats (DeepSeek, Claude, OpenAI)
- Chinese/English conversation noise
- Line-numbered code
- Thinking/reasoning block removal
- stdin/stdout script style
"""

import html
import re
import json
import unicodedata
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class CodeExtractor:
    """
    Code Extractor v2.0
    
    Processing phases:
    0. Preprocessing (remove thinking blocks, XML comments, etc.)
    1. Text normalization (Unicode, BOM, ANSI)
    2. Structured wrapper extraction (JSON, XML)
    3. Markdown code block extraction
    4. Conversation noise removal
    5. Line number cleanup
    6. Multiple solution handling
    """
    
    # ==================== Code block extraction patterns ====================
    
    # Markdown code block patterns
    MARKDOWN_CODE_PATTERNS = [
        # 4+ backticks (nested)
        r'`{4,}python3?\s*\n(.*?)`{4,}',
        r'`{4,}\s*\n(.*?)`{4,}',
        # Standard 3 backticks
        r'```python3?\s*\n(.*?)```',
        r'```Python\s*\n(.*?)```',
        r'```py\s*\n(.*?)```',
        r'```\s*\n(.*?)```',
        # Tilde
        r'~~~python3?\s*\n(.*?)~~~',
        r'~~~py\s*\n(.*?)~~~',
        r'~~~\s*\n(.*?)~~~',
    ]
    
    # XML/HTML tag patterns
    XML_CODE_PATTERNS = [
        # Generic tags
        r'<solution[^>]*>(.*?)</solution>',
        r'<answer[^>]*>(.*?)</answer>',
        r'<code[^>]*>(.*?)</code>',
        r'<python[^>]*>(.*?)</python>',
        r'<script[^>]*type=["\']?python["\']?[^>]*>(.*?)</script>',
        r'<pre[^>]*>(.*?)</pre>',
        # Claude/Anthropic format
        r'<artifact[^>]*>(.*?)</artifact>',
        r'<antArtifact[^>]*>(.*?)</antArtifact>',
        r'<ant_artifact[^>]*>(.*?)</ant_artifact>',
        # Output/result
        r'<output[^>]*>(.*?)</output>',
        r'<result[^>]*>(.*?)</result>',
        r'<response[^>]*>(.*?)</response>',
    ]
    
    # Model-specific formats
    MODEL_SPECIFIC_PATTERNS = [
        # OpenAI format
        r'<\|python_start\|>(.*?)<\|python_end\|>',
        r'<\|code_start\|>(.*?)<\|code_end\|>',
        r'<\|im_start\|>assistant\s*(.*?)<\|im_end\|>',
        # DeepSeek format
        r'<\|code\|>(.*?)<\|/code\|>',
        r'【代码】(.*?)【/代码】',
        r'【Python】(.*?)【/Python】',
        r'【程序】(.*?)【/程序】',
        # Llama/Mistral format
        r'\[PYTHON\](.*?)\[/PYTHON\]',
        r'\[CODE\](.*?)\[/CODE\]',
        r'\[SOLUTION\](.*?)\[/SOLUTION\]',
        r'\[INST\].*?\[/INST\](.*?)(?=\[INST\]|$)',
        # Qwen format
        r'<\|code_start\|>(.*?)<\|code_end\|>',
        r'<\|assistant\|>(.*?)(?=<\||$)',
        # Yi format
        r'<\|yi\|>(.*?)<\|/yi\|>',
        # Baichuan format
        r'<reserved_\d+>(.*?)</reserved_\d+>',
        # ChatGLM format
        r'\[gMASK\].*?\[sMASK\](.*?)(?=\[gMASK\]|$)',
        r'<\|user\|>.*?<\|assistant\|>(.*?)(?=<\||$)',
        # InternLM format
        r'<\|action_start\|>(.*?)<\|action_end\|>',
        # Cohere Command R format
        r'<\|START_OF_TURN_TOKEN\|><\|CHATBOT_TOKEN\|>(.*?)<\|END_OF_TURN_TOKEN\|>',
        # Gemma format
        r'<start_of_turn>model\s*(.*?)<end_of_turn>',
        # Phi format
        r'<\|assistant\|>\s*(.*?)(?=<\||$)',
        # Generic delimiter format
        r'---\s*code\s*---\s*(.*?)\s*---\s*end\s*---',
        r'===\s*code\s*===\s*(.*?)\s*===\s*end\s*===',
    ]
    
    # Thinking/reasoning blocks (to be removed)
    THINKING_BLOCK_PATTERNS = [
        r'<thinking>.*?</thinking>',
        r'<scratchpad>.*?</scratchpad>',
        r'<reasoning>.*?</reasoning>',
        r'<thought>.*?</thought>',
        r'<internal>.*?</internal>',
        r'<reflection>.*?</reflection>',
        r'<analysis>.*?</analysis>',
        r'<chain_of_thought>.*?</chain_of_thought>',
        r'<cot>.*?</cot>',
        r'<think>.*?</think>',
        r'<plan>.*?</plan>',
        r'<step_by_step>.*?</step_by_step>',
        # DeepSeek R1 format
        r'<\|begin_of_thought\|>.*?<\|end_of_thought\|>',
        # Claude format
        r'<antThinking>.*?</antThinking>',
        r'<internal_response>.*?</internal_response>',
        # Generic reasoning format
        r'<reasoning_step>.*?</reasoning_step>',
        r'<inner_monologue>.*?</inner_monologue>',
        r'<work>.*?</work>',
        r'<draft>.*?</draft>',
        # Qwen format
        r'<\|think\|>.*?<\|/think\|>',
        # Chinese thinking blocks
        r'【思考】.*?【/思考】',
        r'【分析】.*?【/分析】',
        r'【推理】.*?【/推理】',
    ]
    
    # ==================== Conversation noise patterns ====================
    
    # English conversation noise
    ENGLISH_NOISE_PATTERNS = [
        # Introductory statements
        r'^here\s+is.*$', r'^here\'s.*$',
        r'^this\s+is.*$', r'^this\s+code.*$',
        r'^this\s+function.*$', r'^this\s+solution.*$',
        r'^below\s+is.*$', r'^above\s+is.*$',
        r'^following\s+is.*$', r'^the\s+following.*$',
        r'^see\s+below.*$', r'^see\s+the.*$',
        # Politeness phrases
        r'^sure[,!].*$', r'^certainly[,!].*$',
        r'^of\s+course[,!].*$', r'^absolutely[,!].*$',
        r'^i\s+hope.*$', r'^i\s+will.*$', r'^i\'ll.*$',
        r'^let\s+me.*$', r'^i\s+have.*$',
        r'^please\s+find.*$', r'^here\s+you\s+go.*$',
        r'^as\s+requested.*$',
        # Labels
        r'^solution:.*$', r'^answer:.*$', r'^code:.*$',
        r'^python:.*$', r'^output:.*$', r'^result:.*$',
        r'^implementation:.*$', r'^explanation:.*$',
        r'^example:.*$', r'^note:.*$', r'^note\s+that.*$',
        # Analysis statements
        r'^the\s+function.*$', r'^the\s+code.*$', r'^the\s+solution.*$',
        r'^the\s+answer.*$', r'^my\s+solution.*$',
        # Complexity analysis
        r'^approach:.*$', r'^logic:.*$', r'^algorithm:.*$',
        r'^complexity:.*$', r'^time\s+complexity.*$', r'^space\s+complexity.*$',
        r'^o\(.*\).*$',
        # Test/constraints
        r'^test\s+case.*$', r'^input:.*$', r'^inputs?:.*$',
        r'^constraints?:.*$', r'^assumptions?:.*$',
        r'^edge\s+cases?.*$', r'^corner\s+cases?.*$',
        # Thinking process
        r'^let\'s\s+break.*$', r'^let\'s\s+analyze.*$',
        r'^let\'s\s+think.*$', r'^let\'s\s+solve.*$',
        r'^we\s+can\s+see.*$', r'^we\s+need\s+to.*$',
        r'^we\s+should.*$', r'^we\s+have.*$',
        r'^to\s+solve\s+this.*$',
        # Summary
        r'^summary:.*$', r'^conclusion:.*$',
        r'^key\s+points?.*$', r'^important:.*$',
        r'^alternatively.*$', r'^returns?:.*$',
        r'^expected.*output.*$', r'^explanation.*$', r'^reasoning.*$',
    ]
    
    # Chinese conversation noise
    CHINESE_NOISE_PATTERNS = [
        # Introductory statements
        r'^这是.*$', r'^以下是.*$', r'^下面是.*$',
        r'^如下.*$', r'^请看.*$', r'^这里是.*$',
        r'^代码如下.*$', r'^程序如下.*$',
        # Labels
        r'^解决方案[：:].*$', r'^答案[：:].*$',
        r'^代码[：:].*$', r'^程序[：:].*$',
        r'^输出[：:].*$', r'^结果[：:].*$',
        r'^实现[：:].*$', r'^解释[：:].*$',
        r'^说明[：:].*$', r'^注意[：:].*$',
        r'^示例[：:].*$', r'^例子[：:].*$',
        # Thinking process
        r'^让我.*$', r'^我来.*$', r'^我们.*$',
        r'^首先.*$', r'^然后.*$', r'^最后.*$',
        r'^接下来.*$', r'^下一步.*$',
        # Analysis
        r'^复杂度.*$', r'^时间复杂度.*$', r'^空间复杂度.*$',
        r'^算法.*$', r'^思路.*$', r'^分析.*$',
        # Summary
        r'^综上.*$', r'^总结.*$', r'^结论.*$',
    ]
    
    # Markdown format noise
    MARKDOWN_NOISE_PATTERNS = [
        r'^\*\*.*\*\*$',  # **bold**
        r'^#+\s+.*$',      # # Header
        r'^---+$',         # ---
        r'^===+$',         # ===
        r'^\*\*\*+$',      # ***
        r'^>\s+.*$',       # > quote (be careful, might be valid code)
    ]
    
    # List format noise
    LIST_NOISE_PATTERNS = [
        r'^\d+\.\s+[A-Z].*$',  # "1. Explanation..."
        r'^-\s+[A-Z].*$',       # "- Note that..."
        r'^\*\s+[A-Z].*$',      # "* The function..."
        r'^•\s+.*$',            # Bullet point
        r'^→\s+.*$',            # Arrow
        r'^✓\s+.*$', r'^✔\s+.*$', r'^✗\s+.*$',
        r'^❌\s+.*$', r'^✅\s+.*$',
        r'^Step\s+\d+.*$',      # Step 1: ...
    ]
    
    # AI model prefixes
    AI_PREFIX_PATTERNS = [
        r'^(assistant|claude|gpt|gemini|llama|deepseek|qwen|mistral)[:\s].*$',
        r'^(ai|bot|model|system)[:\s].*$',
        r'^<\|assistant\|>.*$',
        r'^A:\s*$',  # Q: A: format
    ]
    
    def __init__(self):
        """Initialize extractor"""
        # Compile all noise patterns
        all_noise_patterns = (
            self.ENGLISH_NOISE_PATTERNS +
            self.CHINESE_NOISE_PATTERNS +
            self.MARKDOWN_NOISE_PATTERNS +
            self.LIST_NOISE_PATTERNS +
            self.AI_PREFIX_PATTERNS
        )
        self._noise_patterns = [
            re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for pattern in all_noise_patterns
        ]
        
        # Compile thinking block patterns
        self._thinking_patterns = [
            re.compile(pattern, re.DOTALL | re.IGNORECASE)
            for pattern in self.THINKING_BLOCK_PATTERNS
        ]
    
    def extract(self, raw_output: str) -> str:
        """
        Extract code from LLM output
        
        Args:
            raw_output: LLM's raw output
            
        Returns:
            Extracted and cleaned code
        """
        if not raw_output:
            return ""
        
        code = raw_output
        
        # Phase 0: Preprocessing - Remove thinking blocks
        code = self._remove_thinking_blocks(code)
        
        # Phase 1: Text normalization
        code = self._normalize_text(code)
        
        # Phase 2: Try extracting from JSON
        json_code = self._extract_json_code(code)
        if json_code:
            code = json_code
        else:
            # Phase 3: Markdown/XML code block extraction
            code = self._extract_code_block(code)
        
        # Phase 4: Remove conversation noise
        code = self._remove_conversational_noise(code)
        
        # Phase 5: Remove line numbers
        code = self._remove_line_numbers(code)
        
        # Phase 6: Multiple solution handling
        code = self._extract_last_solution(code)
        
        # Phase 7: Final cleanup
        code = self._final_cleanup(code)
        
        return code.strip()
    
    def _remove_thinking_blocks(self, code: str) -> str:
        """Phase 0: Remove LLM thinking/reasoning blocks"""
        for pattern in self._thinking_patterns:
            code = pattern.sub('', code)
        return code
    
    def _normalize_text(self, code: str) -> str:
        """
        Phase 1: Text normalization
        - Unicode NFKC normalization
        - BOM removal
        - HTML entity decoding
        - ANSI escape code removal
        - Zero-width character removal
        - Line ending normalization
        """
        # Unicode normalization
        code = unicodedata.normalize('NFKC', code)
        
        # BOM removal
        code = code.lstrip('\ufeff')
        
        # HTML entity decoding
        code = html.unescape(code)
        
        # ANSI escape code removal
        code = re.sub(r'\x1b\[[0-9;]*m', '', code)
        code = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', code)
        
        # Zero-width character removal
        zero_width = '\u200b\u200c\u200d\u2060\ufeff\u00a0'
        for char in zero_width:
            code = code.replace(char, '' if char != '\u00a0' else ' ')
        
        # Line ending normalization
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove XML comments
        code = re.sub(r'<!--.*?-->', '', code, flags=re.DOTALL)
        
        return code
    
    def _extract_json_code(self, code: str) -> Optional[str]:
        """Phase 2a: Extract code from JSON structure"""
        # Try complete JSON parsing
        try:
            # Find JSON object
            json_match = re.search(r'\{[^{}]*"(?:code|solution|answer|python|program)"[^{}]*\}', code, re.DOTALL)
            if json_match:
                obj = json.loads(json_match.group())
                for key in ['code', 'solution', 'answer', 'python', 'program']:
                    if key in obj and isinstance(obj[key], str):
                        # Handle escaped newlines
                        extracted = obj[key].replace('\\n', '\n').replace('\\t', '\t')
                        if self._looks_like_code(extracted):
                            return extracted
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Regex extraction (handle incomplete JSON)
        json_patterns = [
            r'"code"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"solution"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"python"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"program"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r"'code'\s*:\s*'((?:[^'\\]|\\.)*)'",
            r"'solution'\s*:\s*'((?:[^'\\]|\\.)*)'",
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, code, re.DOTALL)
            if match:
                extracted = match.group(1)
                # Handle escapes
                extracted = extracted.replace('\\n', '\n').replace('\\t', '\t')
                extracted = extracted.replace('\\"', '"').replace("\\'", "'")
                extracted = extracted.replace('\\\\', '\\')
                if self._looks_like_code(extracted):
                    return extracted
        
        return None
    
    def _extract_code_block(self, code: str) -> str:
        """Phase 2b/3: Extract code blocks (Markdown, XML, model-specific formats)"""
        all_matches: List[Tuple[int, str]] = []
        
        # 1. Try model-specific formats
        for pattern in self.MODEL_SPECIFIC_PATTERNS:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    all_matches.append((match.start(), extracted))
        
        # 2. Try XML tags
        for pattern in self.XML_CODE_PATTERNS:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    all_matches.append((match.start(), extracted))
        
        # 3. Try Markdown code blocks
        for pattern in self.MARKDOWN_CODE_PATTERNS:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    all_matches.append((match.start(), extracted))
        
        # If matches found, take the last one (usually the final version)
        if all_matches:
            all_matches.sort(key=lambda x: x[0])
            return all_matches[-1][1]
        
        # 4. No code block found, clean up remaining markers
        code = self._cleanup_remaining_markers(code)
        
        return code
    
    def _cleanup_remaining_markers(self, code: str) -> str:
        """Clean up remaining code block markers"""
        # Markdown code block markers
        code = re.sub(r'^```\w*\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^```\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^~~~\w*\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^~~~\s*$', '', code, flags=re.MULTILINE)
        
        # Backticks at line beginning/end
        code = re.sub(r'^`+\w*\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^`+(?!`)(.)', r'\1', code, flags=re.MULTILINE)
        code = re.sub(r'`+$', '', code, flags=re.MULTILINE)
        
        # Inline code backticks
        code = re.sub(r'`([^`\n]+)`', r'\1', code)
        
        # Bold/italic (be careful not to break Python's *args, **kwargs)
        code = re.sub(r'(?<!\*)\*\*([^*\n]+)\*\*(?!\*)', r'\1', code)
        code = re.sub(r'(?<!_)__([^_\n]+)__(?!_)', r'\1', code)
        
        # Remaining XML tags
        code = re.sub(r'</?(?:solution|answer|code|python|output|result)[^>]*>', '', code, flags=re.IGNORECASE)
        
        return code
    
    def _remove_conversational_noise(self, code: str) -> str:
        """Phase 4: Remove conversation noise"""
        lines = code.split('\n')
        cleaned_lines = []
        skip_until_code = False
        in_code_section = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip leading empty lines
            if not cleaned_lines and not stripped:
                continue
            
            # Detect if entering code region
            if self._is_code_line(line):
                in_code_section = True
                skip_until_code = False
            
            # Detect Output/Example and other non-code sections
            if re.match(r'^(output|example|sample|test|result|expected|input)s?\s*[:=]', stripped, re.IGNORECASE):
                skip_until_code = True
                in_code_section = False
                continue
            
            # If in skip region, check if new code encountered
            if skip_until_code:
                if self._is_code_line(line):
                    skip_until_code = False
                    in_code_section = True
                else:
                    continue
            
            # For non-code lines, check if it's noise
            if not in_code_section or not self._is_code_line(line):
                is_noise = False
                for pattern in self._noise_patterns:
                    if pattern.match(stripped):
                        is_noise = True
                        break
                
                if is_noise:
                    continue
            
            cleaned_lines.append(line)
        
        # Trim trailing noise lines
        while cleaned_lines and not self._is_code_line(cleaned_lines[-1]):
            last_line = cleaned_lines[-1].strip()
            # Keep empty lines and possible valid code
            if not last_line:
                cleaned_lines.pop()
            elif self._is_noise_line(last_line):
                cleaned_lines.pop()
            else:
                break
        
        return '\n'.join(cleaned_lines)
    
    def _remove_line_numbers(self, code: str) -> str:
        """Phase 5: Remove code line numbers"""
        lines = code.split('\n')
        cleaned_lines = []
        
        # Detect if line number format exists
        line_number_patterns = [
            (r'^\s*(\d+)[:\.\|]\s*', 'colon'),      # "1: ", "01. ", "1| "
            (r'^\s*(\d+)\s{2,}', 'spaces'),          # "1   code"
            (r'^\s*\[(\d+)\]\s*', 'brackets'),       # "[1] code"
            (r'^\s*Line\s+(\d+):\s*', 'line_word'),  # "Line 1: code"
        ]
        
        # Detect main format
        detected_format = None
        line_count = 0
        for line in lines[:20]:  # Check first 20 lines
            for pattern, fmt in line_number_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    detected_format = fmt
                    line_count += 1
                    break
        
        # If significant line number format detected (at least 3 lines match)
        if detected_format and line_count >= 3:
            for line in lines:
                for pattern, fmt in line_number_patterns:
                    if fmt == detected_format:
                        line = re.sub(pattern, '', line, flags=re.IGNORECASE)
                        break
                cleaned_lines.append(line)
            return '\n'.join(cleaned_lines)
        
        return code
    
    def _extract_last_solution(self, code: str, function_name: str = "solve") -> str:
        """Phase 6: If there are multiple def solve, extract the last complete one"""
        pattern = rf'^def\s+{function_name}\s*\('
        matches = list(re.finditer(pattern, code, re.MULTILINE))
        
        if len(matches) <= 1:
            return code
        
        # Take the last one
        last_match = matches[-1]
        code = code[last_match.start():]
        
        logger.debug(f"Extracted last {function_name} function (total {len(matches)})")
        
        return code
    
    def _final_cleanup(self, code: str) -> str:
        """Phase 7: Final cleanup"""
        # Remove excess blank lines (keep at most 2 consecutive)
        code = re.sub(r'\n{4,}', '\n\n\n', code)
        
        # Remove trailing whitespace
        lines = [line.rstrip() for line in code.split('\n')]
        
        # Remove leading empty lines
        while lines and not lines[0]:
            lines.pop(0)
        
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        
        return '\n'.join(lines)
    
    def _looks_like_code(self, text: str) -> bool:
        """Detect if text looks like code"""
        if not text or len(text.strip()) < 5:
            return False
        
        # Python code characteristics
        code_indicators = [
            r'\bdef\s+\w+\s*\(',
            r'\bclass\s+\w+',
            r'\bimport\s+\w+',
            r'\bfrom\s+\w+\s+import',
            r'\breturn\s+',
            r'\bfor\s+\w+\s+in\s+',
            r'\bwhile\s+',
            r'\bif\s+.*:',
            r'\bprint\s*\(',
            r'\binput\s*\(',
            r'^\s*[a-z_][a-z0-9_]*\s*=',
            r'^\s*#\s*\w+',
        ]
        
        for pattern in code_indicators:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                return True
        
        return False
    
    def _is_code_line(self, line: str) -> bool:
        """Detect if single line is a code line"""
        stripped = line.strip()
        if not stripped:
            return False
        
        # Code line characteristics
        code_starts = [
            'def ', 'class ', 'import ', 'from ', 'return ',
            'if ', 'elif ', 'else:', 'for ', 'while ', 'try:',
            'except', 'finally:', 'with ', 'raise ', 'assert ',
            'yield ', 'pass', 'break', 'continue', 'lambda ',
            'global ', 'nonlocal ', 'async ', 'await ',
            '@',  # decorator
        ]
        
        for start in code_starts:
            if stripped.startswith(start):
                return True
        
        # Indented lines (function body)
        if line.startswith('    ') or line.startswith('\t'):
            return True
        
        # Assignment statements
        if re.match(r'^[a-z_][a-z0-9_]*\s*[+\-*/%]?=', stripped, re.IGNORECASE):
            return True
        
        # Function calls
        if re.match(r'^[a-z_][a-z0-9_.]*\s*\(', stripped, re.IGNORECASE):
            return True
        
        # Comments
        if stripped.startswith('#'):
            return True
        
        return False
    
    def _is_noise_line(self, line: str) -> bool:
        """Detect if line is a noise line"""
        for pattern in self._noise_patterns:
            if pattern.match(line):
                return True
        return False
    
    # ==================== Helper methods ====================
    
    def extract_all_code_blocks(self, raw_output: str) -> List[str]:
        """
        Extract all code blocks (for analysis or comparison)
        
        Args:
            raw_output: LLM raw output
            
        Returns:
            List of all code blocks
        """
        code = self._normalize_text(raw_output)
        code = self._remove_thinking_blocks(code)
        
        blocks = []
        all_patterns = (
            self.MARKDOWN_CODE_PATTERNS + 
            self.XML_CODE_PATTERNS + 
            self.MODEL_SPECIFIC_PATTERNS
        )
        
        for pattern in all_patterns:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    blocks.append(extracted)
        
        return blocks
    
    def detect_code_style(self, code: str) -> str:
        """
        Detect code style
        
        Returns:
            'function': Function definition style (def solve(...))
            'stdin_stdout': Script style (input/print)
            'mixed': Mixed style
            'unknown': Cannot determine
        """
        has_function = bool(re.search(r'\bdef\s+\w+\s*\(', code))
        has_input = bool(re.search(r'\binput\s*\(', code))
        has_print = bool(re.search(r'\bprint\s*\(', code))
        
        if has_function and not (has_input and has_print):
            return 'function'
        elif (has_input or has_print) and not has_function:
            return 'stdin_stdout'
        elif has_function and (has_input or has_print):
            return 'mixed'
        else:
            return 'unknown'
