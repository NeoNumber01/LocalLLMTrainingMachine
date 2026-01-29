"""
代码抽取模块 v2.0 - 增强版
从 LLM 原始输出中提取干净的 Python 代码

支持格式：
- Markdown 代码块 (```, ~~~)
- XML/HTML 标签 (<code>, <solution>, <answer>, <artifact>)
- JSON 包装 ({"code": "..."})
- 模型特定格式 (DeepSeek, Claude, OpenAI)
- 中英文对话噪音
- 行号代码
- 思考/推理块移除
- stdin/stdout 脚本风格
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
    代码抽取器 v2.0
    
    处理阶段：
    0. 预处理（移除思考块、XML注释等）
    1. 文本规范化（Unicode、BOM、ANSI）
    2. 结构化包装提取（JSON、XML）
    3. Markdown 代码块提取
    4. 对话噪音移除
    5. 行号清理
    6. 多解方案处理
    """
    
    # ==================== 代码块提取模式 ====================
    
    # Markdown 代码块模式
    MARKDOWN_CODE_PATTERNS = [
        # 4+ 反引号（嵌套）
        r'`{4,}python3?\s*\n(.*?)`{4,}',
        r'`{4,}\s*\n(.*?)`{4,}',
        # 标准 3 反引号
        r'```python3?\s*\n(.*?)```',
        r'```Python\s*\n(.*?)```',
        r'```py\s*\n(.*?)```',
        r'```\s*\n(.*?)```',
        # 波浪线
        r'~~~python3?\s*\n(.*?)~~~',
        r'~~~py\s*\n(.*?)~~~',
        r'~~~\s*\n(.*?)~~~',
    ]
    
    # XML/HTML 标签模式
    XML_CODE_PATTERNS = [
        # 通用标签
        r'<solution[^>]*>(.*?)</solution>',
        r'<answer[^>]*>(.*?)</answer>',
        r'<code[^>]*>(.*?)</code>',
        r'<python[^>]*>(.*?)</python>',
        r'<script[^>]*type=["\']?python["\']?[^>]*>(.*?)</script>',
        r'<pre[^>]*>(.*?)</pre>',
        # Claude/Anthropic 格式
        r'<artifact[^>]*>(.*?)</artifact>',
        r'<antArtifact[^>]*>(.*?)</antArtifact>',
        r'<ant_artifact[^>]*>(.*?)</ant_artifact>',
        # 输出/结果
        r'<output[^>]*>(.*?)</output>',
        r'<result[^>]*>(.*?)</result>',
        r'<response[^>]*>(.*?)</response>',
    ]
    
    # 模型特定格式
    MODEL_SPECIFIC_PATTERNS = [
        # OpenAI 格式
        r'<\|python_start\|>(.*?)<\|python_end\|>',
        r'<\|code_start\|>(.*?)<\|code_end\|>',
        r'<\|im_start\|>assistant\s*(.*?)<\|im_end\|>',
        # DeepSeek 格式
        r'<\|code\|>(.*?)<\|/code\|>',
        r'【代码】(.*?)【/代码】',
        r'【Python】(.*?)【/Python】',
        r'【程序】(.*?)【/程序】',
        # Llama/Mistral 格式
        r'\[PYTHON\](.*?)\[/PYTHON\]',
        r'\[CODE\](.*?)\[/CODE\]',
        r'\[SOLUTION\](.*?)\[/SOLUTION\]',
        r'\[INST\].*?\[/INST\](.*?)(?=\[INST\]|$)',
        # Qwen 格式
        r'<\|code_start\|>(.*?)<\|code_end\|>',
        r'<\|assistant\|>(.*?)(?=<\||$)',
        # Yi 格式
        r'<\|yi\|>(.*?)<\|/yi\|>',
        # Baichuan 格式
        r'<reserved_\d+>(.*?)</reserved_\d+>',
        # ChatGLM 格式
        r'\[gMASK\].*?\[sMASK\](.*?)(?=\[gMASK\]|$)',
        r'<\|user\|>.*?<\|assistant\|>(.*?)(?=<\||$)',
        # InternLM 格式
        r'<\|action_start\|>(.*?)<\|action_end\|>',
        # Cohere Command R 格式
        r'<\|START_OF_TURN_TOKEN\|><\|CHATBOT_TOKEN\|>(.*?)<\|END_OF_TURN_TOKEN\|>',
        # Gemma 格式
        r'<start_of_turn>model\s*(.*?)<end_of_turn>',
        # Phi 格式
        r'<\|assistant\|>\s*(.*?)(?=<\||$)',
        # 通用分隔符格式
        r'---\s*code\s*---\s*(.*?)\s*---\s*end\s*---',
        r'===\s*code\s*===\s*(.*?)\s*===\s*end\s*===',
    ]
    
    # 思考/推理块（需移除）
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
        # DeepSeek R1 格式
        r'<\|begin_of_thought\|>.*?<\|end_of_thought\|>',
        # Claude 格式
        r'<antThinking>.*?</antThinking>',
        r'<internal_response>.*?</internal_response>',
        # 通用推理格式
        r'<reasoning_step>.*?</reasoning_step>',
        r'<inner_monologue>.*?</inner_monologue>',
        r'<work>.*?</work>',
        r'<draft>.*?</draft>',
        # Qwen 格式
        r'<\|think\|>.*?<\|/think\|>',
        # 中文思考块
        r'【思考】.*?【/思考】',
        r'【分析】.*?【/分析】',
        r'【推理】.*?【/推理】',
    ]
    
    # ==================== 对话噪音模式 ====================
    
    # 英文对话噪音
    ENGLISH_NOISE_PATTERNS = [
        # 介绍性语句
        r'^here\s+is.*$', r'^here\'s.*$',
        r'^this\s+is.*$', r'^this\s+code.*$',
        r'^this\s+function.*$', r'^this\s+solution.*$',
        r'^below\s+is.*$', r'^above\s+is.*$',
        r'^following\s+is.*$', r'^the\s+following.*$',
        r'^see\s+below.*$', r'^see\s+the.*$',
        # 礼貌用语
        r'^sure[,!].*$', r'^certainly[,!].*$',
        r'^of\s+course[,!].*$', r'^absolutely[,!].*$',
        r'^i\s+hope.*$', r'^i\s+will.*$', r'^i\'ll.*$',
        r'^let\s+me.*$', r'^i\s+have.*$',
        r'^please\s+find.*$', r'^here\s+you\s+go.*$',
        r'^as\s+requested.*$',
        # 标签
        r'^solution:.*$', r'^answer:.*$', r'^code:.*$',
        r'^python:.*$', r'^output:.*$', r'^result:.*$',
        r'^implementation:.*$', r'^explanation:.*$',
        r'^example:.*$', r'^note:.*$', r'^note\s+that.*$',
        # 分析语句
        r'^the\s+function.*$', r'^the\s+code.*$', r'^the\s+solution.*$',
        r'^the\s+answer.*$', r'^my\s+solution.*$',
        # 复杂度分析
        r'^approach:.*$', r'^logic:.*$', r'^algorithm:.*$',
        r'^complexity:.*$', r'^time\s+complexity.*$', r'^space\s+complexity.*$',
        r'^o\(.*\).*$',
        # 测试/约束
        r'^test\s+case.*$', r'^input:.*$', r'^inputs?:.*$',
        r'^constraints?:.*$', r'^assumptions?:.*$',
        r'^edge\s+cases?.*$', r'^corner\s+cases?.*$',
        # 思考过程
        r'^let\'s\s+break.*$', r'^let\'s\s+analyze.*$',
        r'^let\'s\s+think.*$', r'^let\'s\s+solve.*$',
        r'^we\s+can\s+see.*$', r'^we\s+need\s+to.*$',
        r'^we\s+should.*$', r'^we\s+have.*$',
        r'^to\s+solve\s+this.*$',
        # 总结
        r'^summary:.*$', r'^conclusion:.*$',
        r'^key\s+points?.*$', r'^important:.*$',
        r'^alternatively.*$', r'^returns?:.*$',
        r'^expected.*output.*$', r'^explanation.*$', r'^reasoning.*$',
    ]
    
    # 中文对话噪音
    CHINESE_NOISE_PATTERNS = [
        # 介绍性语句
        r'^这是.*$', r'^以下是.*$', r'^下面是.*$',
        r'^如下.*$', r'^请看.*$', r'^这里是.*$',
        r'^代码如下.*$', r'^程序如下.*$',
        # 标签
        r'^解决方案[：:].*$', r'^答案[：:].*$',
        r'^代码[：:].*$', r'^程序[：:].*$',
        r'^输出[：:].*$', r'^结果[：:].*$',
        r'^实现[：:].*$', r'^解释[：:].*$',
        r'^说明[：:].*$', r'^注意[：:].*$',
        r'^示例[：:].*$', r'^例子[：:].*$',
        # 思考过程
        r'^让我.*$', r'^我来.*$', r'^我们.*$',
        r'^首先.*$', r'^然后.*$', r'^最后.*$',
        r'^接下来.*$', r'^下一步.*$',
        # 分析
        r'^复杂度.*$', r'^时间复杂度.*$', r'^空间复杂度.*$',
        r'^算法.*$', r'^思路.*$', r'^分析.*$',
        # 总结
        r'^综上.*$', r'^总结.*$', r'^结论.*$',
    ]
    
    # Markdown 格式噪音
    MARKDOWN_NOISE_PATTERNS = [
        r'^\*\*.*\*\*$',  # **bold**
        r'^#+\s+.*$',      # # Header
        r'^---+$',         # ---
        r'^===+$',         # ===
        r'^\*\*\*+$',      # ***
        r'^>\s+.*$',       # > quote (be careful, might be valid code)
    ]
    
    # 列表格式噪音
    LIST_NOISE_PATTERNS = [
        r'^\d+\.\s+[A-Z].*$',  # "1. Explanation..."
        r'^-\s+[A-Z].*$',       # "- Note that..."
        r'^\*\s+[A-Z].*$',      # "* The function..."
        r'^•\s+.*$',            # 圆点
        r'^→\s+.*$',            # 箭头
        r'^✓\s+.*$', r'^✔\s+.*$', r'^✗\s+.*$',
        r'^❌\s+.*$', r'^✅\s+.*$',
        r'^Step\s+\d+.*$',      # Step 1: ...
    ]
    
    # AI 模型前缀
    AI_PREFIX_PATTERNS = [
        r'^(assistant|claude|gpt|gemini|llama|deepseek|qwen|mistral)[:\s].*$',
        r'^(ai|bot|model|system)[:\s].*$',
        r'^<\|assistant\|>.*$',
        r'^A:\s*$',  # Q: A: 格式
    ]
    
    def __init__(self):
        """初始化抽取器"""
        # 编译所有噪音模式
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
        
        # 编译思考块模式
        self._thinking_patterns = [
            re.compile(pattern, re.DOTALL | re.IGNORECASE)
            for pattern in self.THINKING_BLOCK_PATTERNS
        ]
    
    def extract(self, raw_output: str) -> str:
        """
        从 LLM 输出中提取代码
        
        Args:
            raw_output: LLM 的原始输出
            
        Returns:
            提取并清理后的代码
        """
        if not raw_output:
            return ""
        
        code = raw_output
        
        # Phase 0: 预处理 - 移除思考块
        code = self._remove_thinking_blocks(code)
        
        # Phase 1: 文本规范化
        code = self._normalize_text(code)
        
        # Phase 2: 尝试从 JSON 提取
        json_code = self._extract_json_code(code)
        if json_code:
            code = json_code
        else:
            # Phase 3: Markdown/XML 代码块提取
            code = self._extract_code_block(code)
        
        # Phase 4: 移除对话噪音
        code = self._remove_conversational_noise(code)
        
        # Phase 5: 移除行号
        code = self._remove_line_numbers(code)
        
        # Phase 6: 多解方案处理
        code = self._extract_last_solution(code)
        
        # Phase 7: 最终清理
        code = self._final_cleanup(code)
        
        return code.strip()
    
    def _remove_thinking_blocks(self, code: str) -> str:
        """Phase 0: 移除 LLM 思考/推理块"""
        for pattern in self._thinking_patterns:
            code = pattern.sub('', code)
        return code
    
    def _normalize_text(self, code: str) -> str:
        """
        Phase 1: 文本规范化
        - Unicode NFKC 规范化
        - BOM 移除
        - HTML 实体解码
        - ANSI 转义码移除
        - 零宽字符移除
        - 行尾规范化
        """
        # Unicode 规范化
        code = unicodedata.normalize('NFKC', code)
        
        # BOM 移除
        code = code.lstrip('\ufeff')
        
        # HTML 实体解码
        code = html.unescape(code)
        
        # ANSI 转义码移除
        code = re.sub(r'\x1b\[[0-9;]*m', '', code)
        code = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', code)
        
        # 零宽字符移除
        zero_width = '\u200b\u200c\u200d\u2060\ufeff\u00a0'
        for char in zero_width:
            code = code.replace(char, '' if char != '\u00a0' else ' ')
        
        # 行尾规范化
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        
        # 移除 XML 注释
        code = re.sub(r'<!--.*?-->', '', code, flags=re.DOTALL)
        
        return code
    
    def _extract_json_code(self, code: str) -> Optional[str]:
        """Phase 2a: 从 JSON 结构中提取代码"""
        # 尝试完整 JSON 解析
        try:
            # 查找 JSON 对象
            json_match = re.search(r'\{[^{}]*"(?:code|solution|answer|python|program)"[^{}]*\}', code, re.DOTALL)
            if json_match:
                obj = json.loads(json_match.group())
                for key in ['code', 'solution', 'answer', 'python', 'program']:
                    if key in obj and isinstance(obj[key], str):
                        # 处理转义的换行符
                        extracted = obj[key].replace('\\n', '\n').replace('\\t', '\t')
                        if self._looks_like_code(extracted):
                            return extracted
        except (json.JSONDecodeError, ValueError):
            pass
        
        # 正则提取（处理不完整的 JSON）
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
                # 处理转义
                extracted = extracted.replace('\\n', '\n').replace('\\t', '\t')
                extracted = extracted.replace('\\"', '"').replace("\\'", "'")
                extracted = extracted.replace('\\\\', '\\')
                if self._looks_like_code(extracted):
                    return extracted
        
        return None
    
    def _extract_code_block(self, code: str) -> str:
        """Phase 2b/3: 提取代码块（Markdown, XML, 模型特定格式）"""
        all_matches: List[Tuple[int, str]] = []
        
        # 1. 尝试模型特定格式
        for pattern in self.MODEL_SPECIFIC_PATTERNS:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    all_matches.append((match.start(), extracted))
        
        # 2. 尝试 XML 标签
        for pattern in self.XML_CODE_PATTERNS:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    all_matches.append((match.start(), extracted))
        
        # 3. 尝试 Markdown 代码块
        for pattern in self.MARKDOWN_CODE_PATTERNS:
            for match in re.finditer(pattern, code, re.DOTALL | re.IGNORECASE):
                extracted = match.group(1).strip()
                if extracted and self._looks_like_code(extracted):
                    all_matches.append((match.start(), extracted))
        
        # 如果有匹配，取最后一个（通常是最终版本）
        if all_matches:
            all_matches.sort(key=lambda x: x[0])
            return all_matches[-1][1]
        
        # 4. 没有找到代码块，清理残留标记
        code = self._cleanup_remaining_markers(code)
        
        return code
    
    def _cleanup_remaining_markers(self, code: str) -> str:
        """清理残留的代码块标记"""
        # Markdown 代码块标记
        code = re.sub(r'^```\w*\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^```\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^~~~\w*\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^~~~\s*$', '', code, flags=re.MULTILINE)
        
        # 行开头/结尾反引号
        code = re.sub(r'^`+\w*\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^`+(?!`)(.)', r'\1', code, flags=re.MULTILINE)
        code = re.sub(r'`+$', '', code, flags=re.MULTILINE)
        
        # 行内代码反引号
        code = re.sub(r'`([^`\n]+)`', r'\1', code)
        
        # 加粗/斜体（小心不要破坏 Python 的 *args, **kwargs）
        code = re.sub(r'(?<!\*)\*\*([^*\n]+)\*\*(?!\*)', r'\1', code)
        code = re.sub(r'(?<!_)__([^_\n]+)__(?!_)', r'\1', code)
        
        # XML 残留标签
        code = re.sub(r'</?(?:solution|answer|code|python|output|result)[^>]*>', '', code, flags=re.IGNORECASE)
        
        return code
    
    def _remove_conversational_noise(self, code: str) -> str:
        """Phase 4: 移除对话噪音"""
        lines = code.split('\n')
        cleaned_lines = []
        skip_until_code = False
        in_code_section = False
        
        for line in lines:
            stripped = line.strip()
            
            # 跳过开头的空行
            if not cleaned_lines and not stripped:
                continue
            
            # 检测是否进入代码区域
            if self._is_code_line(line):
                in_code_section = True
                skip_until_code = False
            
            # 检测 Output/Example 等非代码部分
            if re.match(r'^(output|example|sample|test|result|expected|input)s?\s*[:=]', stripped, re.IGNORECASE):
                skip_until_code = True
                in_code_section = False
                continue
            
            # 如果在跳过区域，检查是否遇到新代码
            if skip_until_code:
                if self._is_code_line(line):
                    skip_until_code = False
                    in_code_section = True
                else:
                    continue
            
            # 对于非代码行，检查是否是噪音
            if not in_code_section or not self._is_code_line(line):
                is_noise = False
                for pattern in self._noise_patterns:
                    if pattern.match(stripped):
                        is_noise = True
                        break
                
                if is_noise:
                    continue
            
            cleaned_lines.append(line)
        
        # 修剪尾部噪音行
        while cleaned_lines and not self._is_code_line(cleaned_lines[-1]):
            last_line = cleaned_lines[-1].strip()
            # 保留空行和可能的有效代码
            if not last_line:
                cleaned_lines.pop()
            elif self._is_noise_line(last_line):
                cleaned_lines.pop()
            else:
                break
        
        return '\n'.join(cleaned_lines)
    
    def _remove_line_numbers(self, code: str) -> str:
        """Phase 5: 移除代码行号"""
        lines = code.split('\n')
        cleaned_lines = []
        
        # 检测是否有行号格式
        line_number_patterns = [
            (r'^\s*(\d+)[:\.\|]\s*', 'colon'),      # "1: ", "01. ", "1| "
            (r'^\s*(\d+)\s{2,}', 'spaces'),          # "1   code"
            (r'^\s*\[(\d+)\]\s*', 'brackets'),       # "[1] code"
            (r'^\s*Line\s+(\d+):\s*', 'line_word'),  # "Line 1: code"
        ]
        
        # 检测主要格式
        detected_format = None
        line_count = 0
        for line in lines[:20]:  # 检查前20行
            for pattern, fmt in line_number_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    detected_format = fmt
                    line_count += 1
                    break
        
        # 如果检测到显著的行号格式（至少3行匹配）
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
        """Phase 6: 如果有多个 def solve，提取最后一个完整的"""
        pattern = rf'^def\s+{function_name}\s*\('
        matches = list(re.finditer(pattern, code, re.MULTILINE))
        
        if len(matches) <= 1:
            return code
        
        # 取最后一个
        last_match = matches[-1]
        code = code[last_match.start():]
        
        logger.debug(f"提取最后一个 {function_name} 函数（共 {len(matches)} 个）")
        
        return code
    
    def _final_cleanup(self, code: str) -> str:
        """Phase 7: 最终清理"""
        # 移除多余空行（保留最多2个连续空行）
        code = re.sub(r'\n{4,}', '\n\n\n', code)
        
        # 移除尾部空白
        lines = [line.rstrip() for line in code.split('\n')]
        
        # 移除开头的空行
        while lines and not lines[0]:
            lines.pop(0)
        
        # 移除结尾的空行
        while lines and not lines[-1]:
            lines.pop()
        
        return '\n'.join(lines)
    
    def _looks_like_code(self, text: str) -> bool:
        """检测文本是否看起来像代码"""
        if not text or len(text.strip()) < 5:
            return False
        
        # Python 代码特征
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
        """检测单行是否是代码行"""
        stripped = line.strip()
        if not stripped:
            return False
        
        # 代码行特征
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
        
        # 缩进行（函数体）
        if line.startswith('    ') or line.startswith('\t'):
            return True
        
        # 赋值语句
        if re.match(r'^[a-z_][a-z0-9_]*\s*[+\-*/%]?=', stripped, re.IGNORECASE):
            return True
        
        # 函数调用
        if re.match(r'^[a-z_][a-z0-9_.]*\s*\(', stripped, re.IGNORECASE):
            return True
        
        # 注释
        if stripped.startswith('#'):
            return True
        
        return False
    
    def _is_noise_line(self, line: str) -> bool:
        """检测是否是噪音行"""
        for pattern in self._noise_patterns:
            if pattern.match(line):
                return True
        return False
    
    # ==================== 辅助方法 ====================
    
    def extract_all_code_blocks(self, raw_output: str) -> List[str]:
        """
        提取所有代码块（用于分析或比较）
        
        Args:
            raw_output: LLM 原始输出
            
        Returns:
            所有代码块的列表
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
        检测代码风格
        
        Returns:
            'function': 函数定义风格 (def solve(...))
            'stdin_stdout': 脚本风格 (input/print)
            'mixed': 混合风格
            'unknown': 无法确定
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
