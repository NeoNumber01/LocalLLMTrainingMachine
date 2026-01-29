#!/usr/bin/env python3
"""
Dataset Format Registry - 可扩展的数据集格式检测与转换系统

支持 20+ 种常见 LLM 训练数据格式，自动检测并转换为标准 messages 格式。

Usage:
    from format_registry import DatasetFormatRegistry
    registry = DatasetFormatRegistry()
    
    # 自动检测并转换
    format_name = registry.detect_format(sample)
    messages = registry.convert_to_messages(sample, format_name)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("FormatRegistry")


# =============================================================================
# 数据结构定义
# =============================================================================
@dataclass
class FormatInfo:
    """格式信息"""
    name: str
    priority: int  # 检测优先级 (越小越优先)
    description: str
    required_fields: list[str]
    optional_fields: list[str]
    detector: Callable[[dict], bool]
    converter: Callable[[dict, Optional[str]], list[dict]]


# =============================================================================
# 格式转换器基类
# =============================================================================
class BaseFormatConverter(ABC):
    """格式转换器基类"""
    
    @abstractmethod
    def detect(self, sample: dict) -> bool:
        """检测样本是否匹配此格式"""
        pass
    
    @abstractmethod
    def convert(self, sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
        """将样本转换为标准 messages 格式"""
        pass


# =============================================================================
# 默认 System Prompt
# =============================================================================
DEFAULT_SYSTEM_PROMPTS = {
    "code": "You are an expert Python programmer. Write clean, efficient, and correct code.",
    "general": "You are a helpful AI assistant.",
    "qa": "You are a knowledgeable assistant that provides accurate and helpful answers.",
    "translation": "You are a professional translator.",
    "math": "You are a mathematical expert. Show your work step by step.",
}


def get_system_prompt(category: str = "general", custom: Optional[str] = None) -> str:
    """获取 system prompt"""
    if custom:
        return custom
    return DEFAULT_SYSTEM_PROMPTS.get(category, DEFAULT_SYSTEM_PROMPTS["general"])


# =============================================================================
# 辅助函数
# =============================================================================
def safe_str(value: Any) -> str:
    """安全地将值转换为字符串"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        import json
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def has_fields(sample: dict, required: list[str]) -> bool:
    """检查样本是否包含所有必需字段"""
    return all(field in sample and sample[field] is not None for field in required)


def has_any_field(sample: dict, fields: list[str]) -> bool:
    """检查样本是否包含任意一个字段"""
    return any(field in sample and sample[field] is not None for field in fields)


def get_first_field(sample: dict, fields: list[str], default: str = "") -> str:
    """获取第一个存在的字段值"""
    for field in fields:
        if field in sample and sample[field] is not None:
            return safe_str(sample[field])
    return default


# =============================================================================
# P0 格式：对话类
# =============================================================================

def detect_messages(sample: dict) -> bool:
    """检测标准 messages 格式"""
    if "messages" not in sample:
        return False
    messages = sample["messages"]
    if not isinstance(messages, list) or len(messages) == 0:
        return False
    # 检查是否是有效的 messages 格式
    return all(isinstance(m, dict) and "role" in m and "content" in m for m in messages)


def convert_messages(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换标准 messages 格式"""
    return sample["messages"]


def detect_sharegpt(sample: dict) -> bool:
    """检测 ShareGPT 格式 (conversations 数组)"""
    if "conversations" not in sample:
        return False
    convs = sample["conversations"]
    if not isinstance(convs, list) or len(convs) == 0:
        return False
    # ShareGPT 使用 "from" 和 "value" 字段
    return all(isinstance(c, dict) and ("from" in c or "role" in c) and ("value" in c or "content" in c) for c in convs)


def convert_sharegpt(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 ShareGPT 格式"""
    messages = []
    convs = sample["conversations"]
    
    # ShareGPT 角色映射
    role_map = {
        "human": "user",
        "user": "user",
        "gpt": "assistant",
        "assistant": "assistant",
        "system": "system",
        "chatgpt": "assistant",
        "bing": "assistant",
        "bard": "assistant",
    }
    
    for conv in convs:
        role_raw = conv.get("from") or conv.get("role", "user")
        role = role_map.get(role_raw.lower(), "user")
        content = conv.get("value") or conv.get("content", "")
        messages.append({"role": role, "content": safe_str(content)})
    
    return messages


def detect_openai_chatml(sample: dict) -> bool:
    """检测 OpenAI ChatML 格式 (独立的 system/user/assistant 字段)"""
    # 必须有 user 和 assistant，system 可选
    return has_fields(sample, ["user", "assistant"])


def convert_openai_chatml(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 OpenAI ChatML 格式"""
    messages = []
    
    # System prompt
    if "system" in sample and sample["system"]:
        messages.append({"role": "system", "content": safe_str(sample["system"])})
    elif system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # User message
    messages.append({"role": "user", "content": safe_str(sample["user"])})
    
    # Assistant response
    messages.append({"role": "assistant", "content": safe_str(sample["assistant"])})
    
    return messages


def detect_dialog_turns(sample: dict) -> bool:
    """检测多轮对话格式 (dialog/turns 数组)"""
    for field in ["dialog", "turns", "dialogue", "conversation"]:
        if field in sample and isinstance(sample[field], list) and len(sample[field]) > 0:
            turns = sample[field]
            # 检查是否是交替的用户/助手对话
            if isinstance(turns[0], str):
                return True  # 纯字符串数组，交替 user/assistant
            if isinstance(turns[0], dict):
                return True  # 结构化对话
    return False


def convert_dialog_turns(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换多轮对话格式"""
    messages = []
    
    # 找到对话字段
    turns = None
    for field in ["dialog", "turns", "dialogue", "conversation"]:
        if field in sample and isinstance(sample[field], list):
            turns = sample[field]
            break
    
    if not turns:
        return messages
    
    # 添加 system prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # 处理对话
    if isinstance(turns[0], str):
        # 纯字符串数组：交替 user/assistant
        for i, turn in enumerate(turns):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append({"role": role, "content": safe_str(turn)})
    else:
        # 结构化对话
        for turn in turns:
            role = turn.get("role") or turn.get("speaker") or ("user" if len(messages) % 2 == 0 else "assistant")
            content = turn.get("content") or turn.get("text") or turn.get("utterance") or ""
            if role.lower() in ["user", "human", "customer"]:
                role = "user"
            elif role.lower() in ["assistant", "agent", "system", "bot"]:
                role = "assistant"
            messages.append({"role": role, "content": safe_str(content)})
    
    return messages


def detect_history_response(sample: dict) -> bool:
    """检测历史+回复格式 (history + response)"""
    return has_fields(sample, ["history", "response"]) or has_fields(sample, ["history", "reply"])


def convert_history_response(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换历史+回复格式"""
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # 处理 history
    history = sample.get("history", [])
    if isinstance(history, list):
        for i, item in enumerate(history):
            if isinstance(item, str):
                role = "user" if i % 2 == 0 else "assistant"
                messages.append({"role": role, "content": safe_str(item)})
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                # [user_msg, assistant_msg] 格式
                messages.append({"role": "user", "content": safe_str(item[0])})
                messages.append({"role": "assistant", "content": safe_str(item[1])})
            elif isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content") or item.get("text", "")
                messages.append({"role": role, "content": safe_str(content)})
    
    # 添加当前查询 (如果存在)
    if "query" in sample or "input" in sample:
        query = sample.get("query") or sample.get("input", "")
        messages.append({"role": "user", "content": safe_str(query)})
    
    # 添加回复
    response = sample.get("response") or sample.get("reply", "")
    messages.append({"role": "assistant", "content": safe_str(response)})
    
    return messages


# =============================================================================
# P0 格式：指令类
# =============================================================================

def detect_alpaca(sample: dict) -> bool:
    """检测 Alpaca 格式 (instruction + input + output)"""
    # Alpaca 必须有 instruction 和 output，input 可以为空字符串
    # 扩展支持 reference 字段（常见于代码训练数据）
    return has_fields(sample, ["instruction"]) and has_any_field(sample, ["output", "response", "reference"])


def convert_alpaca(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 Alpaca 格式"""
    messages = []
    
    # System prompt - 自动检测是否是代码训练场景
    is_code_sample = "signature" in sample or "reference" in sample or "tests" in sample
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    elif is_code_sample:
        # 代码训练场景使用代码专用的 system prompt
        messages.append({"role": "system", "content": get_system_prompt("code")})
    
    # 构建 user 消息
    instruction = safe_str(sample.get("instruction", ""))
    input_text = safe_str(sample.get("input", ""))
    signature = safe_str(sample.get("signature", ""))
    
    # 代码场景：如果有 signature，添加到指令中
    if signature:
        if input_text:
            user_content = f"{instruction}\n\nFunction signature:\n{signature}\n\nInput:\n{input_text}"
        else:
            user_content = f"{instruction}\n\nFunction signature:\n{signature}"
    elif input_text:
        user_content = f"{instruction}\n\nInput:\n{input_text}"
    else:
        user_content = instruction
    
    messages.append({"role": "user", "content": user_content})
    
    # Assistant 响应
    output = get_first_field(sample, ["output", "response", "answer", "reference"])
    messages.append({"role": "assistant", "content": output})
    
    return messages


def detect_dolly(sample: dict) -> bool:
    """检测 Dolly 格式 (context + instruction + response)"""
    return has_fields(sample, ["context", "instruction", "response"])


def convert_dolly(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 Dolly 格式"""
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # 构建 user 消息
    instruction = safe_str(sample.get("instruction", ""))
    context = safe_str(sample.get("context", ""))
    
    if context:
        user_content = f"Context:\n{context}\n\nInstruction:\n{instruction}"
    else:
        user_content = instruction
    
    messages.append({"role": "user", "content": user_content})
    messages.append({"role": "assistant", "content": safe_str(sample.get("response", ""))})
    
    return messages


def detect_wizardlm(sample: dict) -> bool:
    """检测 WizardLM 格式 (instruction + response + complexity)"""
    # WizardLM 特征：有 complexity 或 evol_* 字段
    if not has_fields(sample, ["instruction"]):
        return False
    return "complexity" in sample or any(k.startswith("evol_") for k in sample.keys())


def convert_wizardlm(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 WizardLM 格式"""
    # 基本上和 Alpaca 一样处理
    return convert_alpaca(sample, system_prompt)


# =============================================================================
# P0 格式：代码生成类
# =============================================================================

def detect_humaneval(sample: dict) -> bool:
    """检测 HumanEval 格式"""
    return has_fields(sample, ["task_id", "prompt"]) and has_any_field(sample, ["canonical_solution", "solution"])


def convert_humaneval(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 HumanEval 格式"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("code")})
    messages.append({"role": "user", "content": safe_str(sample.get("prompt", ""))})
    
    solution = get_first_field(sample, ["canonical_solution", "solution", "code"])
    messages.append({"role": "assistant", "content": solution})
    
    return messages


def detect_mbpp(sample: dict) -> bool:
    """检测 MBPP 格式 (task_id + text + code)"""
    return has_fields(sample, ["text", "code"]) or (has_fields(sample, ["task_id"]) and has_any_field(sample, ["text", "prompt"]))


def convert_mbpp(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 MBPP 格式"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("code")})
    
    # 用户消息
    prompt = get_first_field(sample, ["text", "prompt", "description"])
    messages.append({"role": "user", "content": prompt})
    
    # 代码
    code = get_first_field(sample, ["code", "solution", "canonical_solution"])
    messages.append({"role": "assistant", "content": code})
    
    return messages


def detect_taco(sample: dict) -> bool:
    """检测 TACO/CodeContests 格式 (prompt + reference/solution + starter_code)"""
    if not has_fields(sample, ["prompt"]):
        return False
    return has_any_field(sample, ["reference", "solution", "solutions", "code"]) or "starter_code" in sample


def convert_taco(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 TACO/CodeContests 格式"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("code")})
    
    # 构建用户消息
    prompt = safe_str(sample.get("prompt", ""))
    starter_code = safe_str(sample.get("starter_code", ""))
    
    if starter_code:
        user_content = f"{prompt}\n\nStarter code:\n```python\n{starter_code}\n```"
    else:
        user_content = prompt
    
    messages.append({"role": "user", "content": user_content})
    
    # 代码解决方案
    solution = get_first_field(sample, ["reference", "solution", "code", "canonical_solution"])
    
    # 如果 solutions 是数组，取第一个
    if not solution and "solutions" in sample:
        solutions = sample["solutions"]
        if isinstance(solutions, list) and len(solutions) > 0:
            solution = safe_str(solutions[0])
    
    messages.append({"role": "assistant", "content": solution})
    
    return messages


def detect_code_completion(sample: dict) -> bool:
    """检测代码补全格式 (prefix + suffix + middle)"""
    return has_fields(sample, ["prefix", "middle"]) or has_fields(sample, ["prefix", "suffix", "middle"])


def convert_code_completion(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换代码补全格式 (FIM - Fill in the Middle)"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("code")})
    
    prefix = safe_str(sample.get("prefix", ""))
    suffix = safe_str(sample.get("suffix", ""))
    middle = safe_str(sample.get("middle", ""))
    
    if suffix:
        user_content = f"Complete the code between <FILL> markers:\n\n{prefix}<FILL>{suffix}"
    else:
        user_content = f"Complete the following code:\n\n{prefix}"
    
    messages.append({"role": "user", "content": user_content})
    messages.append({"role": "assistant", "content": middle})
    
    return messages


def detect_code_instruct(sample: dict) -> bool:
    """检测代码指令格式 (prompt + code)"""
    return has_fields(sample, ["prompt", "code"])


def convert_code_instruct(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换代码指令格式"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("code")})
    messages.append({"role": "user", "content": safe_str(sample.get("prompt", ""))})
    messages.append({"role": "assistant", "content": safe_str(sample.get("code", ""))})
    
    return messages


# =============================================================================
# P1 格式：问答类
# =============================================================================

def detect_qa_basic(sample: dict) -> bool:
    """检测基础问答格式"""
    return has_fields(sample, ["question"]) and has_any_field(sample, ["answer", "answers", "response"])


def convert_qa_basic(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换基础问答格式"""
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    messages.append({"role": "user", "content": safe_str(sample.get("question", ""))})
    
    # 答案可能是字符串或列表
    answer = sample.get("answer") or sample.get("response") or ""
    if "answers" in sample and isinstance(sample["answers"], list):
        # 取第一个答案
        answer = sample["answers"][0] if sample["answers"] else ""
        if isinstance(answer, dict):
            answer = answer.get("text", "")
    
    messages.append({"role": "assistant", "content": safe_str(answer)})
    
    return messages


def detect_qa_with_context(sample: dict) -> bool:
    """检测带上下文的问答格式 (RAG 格式)"""
    return has_fields(sample, ["question"]) and has_any_field(sample, ["context", "passage", "document"]) and has_any_field(sample, ["answer", "response"])


def convert_qa_with_context(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换带上下文的问答格式"""
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    context = get_first_field(sample, ["context", "passage", "document", "article"])
    question = safe_str(sample.get("question", ""))
    
    user_content = f"Context:\n{context}\n\nQuestion:\n{question}"
    messages.append({"role": "user", "content": user_content})
    
    answer = get_first_field(sample, ["answer", "response", "output"])
    messages.append({"role": "assistant", "content": answer})
    
    return messages


def detect_qa_choices(sample: dict) -> bool:
    """检测多选题格式"""
    return has_fields(sample, ["question", "choices"]) or has_fields(sample, ["question", "options"])


def convert_qa_choices(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换多选题格式"""
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    question = safe_str(sample.get("question", ""))
    choices = sample.get("choices") or sample.get("options", [])
    
    # 构建选项文本
    choice_texts = []
    for i, choice in enumerate(choices):
        label = chr(65 + i)  # A, B, C, D...
        if isinstance(choice, dict):
            text = choice.get("text") or choice.get("content", "")
        else:
            text = str(choice)
        choice_texts.append(f"{label}. {text}")
    
    user_content = f"{question}\n\n" + "\n".join(choice_texts)
    messages.append({"role": "user", "content": user_content})
    
    # 答案
    answer = sample.get("answer", "")
    if isinstance(answer, int) and 0 <= answer < len(choices):
        answer = chr(65 + answer)  # 转换为字母
    messages.append({"role": "assistant", "content": safe_str(answer)})
    
    return messages


# =============================================================================
# P1 格式：生成类
# =============================================================================

def detect_summarization(sample: dict) -> bool:
    """检测摘要格式"""
    return has_any_field(sample, ["document", "article", "text"]) and has_any_field(sample, ["summary", "highlights", "abstract"])


def convert_summarization(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换摘要格式"""
    messages = []
    
    sys_prompt = system_prompt or "You are an expert summarizer. Provide concise and accurate summaries."
    messages.append({"role": "system", "content": sys_prompt})
    
    document = get_first_field(sample, ["document", "article", "text", "content"])
    messages.append({"role": "user", "content": f"Summarize the following text:\n\n{document}"})
    
    summary = get_first_field(sample, ["summary", "highlights", "abstract"])
    messages.append({"role": "assistant", "content": summary})
    
    return messages


def detect_translation(sample: dict) -> bool:
    """检测翻译格式"""
    # 检查 source/target 或语言对 (如 en, zh, de 等)
    if has_fields(sample, ["source", "target"]):
        return True
    # 检查语言代码字段
    lang_codes = ["en", "zh", "de", "fr", "es", "ja", "ko", "ru", "ar", "pt", "it"]
    return sum(1 for lang in lang_codes if lang in sample) >= 2


def convert_translation(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换翻译格式"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("translation")})
    
    # 尝试获取源语言和目标语言
    source = sample.get("source", "")
    target = sample.get("target", "")
    
    # 如果没有 source/target，尝试语言代码字段
    if not source:
        for lang in ["en", "zh", "de", "fr", "es", "ja", "ko"]:
            if lang in sample and sample[lang]:
                if not source:
                    source = sample[lang]
                elif not target:
                    target = sample[lang]
                    break
    
    messages.append({"role": "user", "content": f"Translate:\n{safe_str(source)}"})
    messages.append({"role": "assistant", "content": safe_str(target)})
    
    return messages


def detect_rewriting(sample: dict) -> bool:
    """检测改写格式"""
    return has_fields(sample, ["original", "rewritten"]) or has_fields(sample, ["input", "paraphrase"])


def convert_rewriting(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换改写格式"""
    messages = []
    
    sys_prompt = system_prompt or "You are an expert at paraphrasing text while preserving meaning."
    messages.append({"role": "system", "content": sys_prompt})
    
    original = get_first_field(sample, ["original", "input", "source"])
    messages.append({"role": "user", "content": f"Rewrite the following:\n{original}"})
    
    rewritten = get_first_field(sample, ["rewritten", "paraphrase", "output", "target"])
    messages.append({"role": "assistant", "content": rewritten})
    
    return messages


# =============================================================================
# P2 格式：特殊类
# =============================================================================

def detect_chain_of_thought(sample: dict) -> bool:
    """检测思维链格式"""
    return has_fields(sample, ["question"]) and has_any_field(sample, ["chain_of_thought", "cot", "reasoning", "thought"])


def convert_chain_of_thought(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换思维链格式"""
    messages = []
    
    sys_prompt = system_prompt or "You are an expert problem solver. Think step by step and show your reasoning."
    messages.append({"role": "system", "content": sys_prompt})
    
    question = safe_str(sample.get("question", ""))
    messages.append({"role": "user", "content": question})
    
    # 构建思维链 + 答案
    cot = get_first_field(sample, ["chain_of_thought", "cot", "reasoning", "thought"])
    answer = get_first_field(sample, ["answer", "final_answer", "result"])
    
    if cot and answer:
        response = f"{cot}\n\nTherefore, the answer is: {answer}"
    elif cot:
        response = cot
    else:
        response = answer
    
    messages.append({"role": "assistant", "content": response})
    
    return messages


def detect_sql_generation(sample: dict) -> bool:
    """检测 SQL 生成格式"""
    return has_fields(sample, ["question"]) and has_any_field(sample, ["query", "sql"]) and has_any_field(sample, ["schema", "table", "db_id"])


def convert_sql_generation(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换 SQL 生成格式"""
    messages = []
    
    sys_prompt = system_prompt or "You are an expert SQL developer. Write correct and efficient SQL queries."
    messages.append({"role": "system", "content": sys_prompt})
    
    # 构建用户消息
    question = safe_str(sample.get("question", ""))
    schema = get_first_field(sample, ["schema", "table_info", "create_table"])
    db_id = sample.get("db_id", "")
    
    if schema:
        user_content = f"Database Schema:\n{schema}\n\nQuestion: {question}"
    elif db_id:
        user_content = f"Database: {db_id}\n\nQuestion: {question}"
    else:
        user_content = question
    
    messages.append({"role": "user", "content": user_content})
    
    sql = get_first_field(sample, ["query", "sql", "answer"])
    messages.append({"role": "assistant", "content": sql})
    
    return messages


def detect_math_solving(sample: dict) -> bool:
    """检测数学求解格式"""
    return has_any_field(sample, ["problem", "question"]) and has_any_field(sample, ["solution", "answer"]) and \
           ("answer" in sample or any(k in sample for k in ["final_answer", "numeric_answer"]))


def convert_math_solving(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换数学求解格式"""
    messages = []
    
    messages.append({"role": "system", "content": system_prompt or get_system_prompt("math")})
    
    problem = get_first_field(sample, ["problem", "question"])
    messages.append({"role": "user", "content": problem})
    
    # 构建解答
    solution = get_first_field(sample, ["solution", "explanation", "reasoning"])
    answer = get_first_field(sample, ["answer", "final_answer", "numeric_answer"])
    
    if solution and answer:
        response = f"{solution}\n\nFinal Answer: {answer}"
    elif solution:
        response = solution
    else:
        response = answer
    
    messages.append({"role": "assistant", "content": response})
    
    return messages


def detect_code_review(sample: dict) -> bool:
    """检测代码评审格式"""
    return has_fields(sample, ["code_before"]) and has_any_field(sample, ["review", "code_after", "feedback"])


def convert_code_review(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换代码评审格式"""
    messages = []
    
    sys_prompt = system_prompt or "You are a senior code reviewer. Provide constructive feedback and improvements."
    messages.append({"role": "system", "content": sys_prompt})
    
    code_before = safe_str(sample.get("code_before", ""))
    messages.append({"role": "user", "content": f"Review and improve this code:\n\n```\n{code_before}\n```"})
    
    # 构建响应
    review = safe_str(sample.get("review") or sample.get("feedback", ""))
    code_after = safe_str(sample.get("code_after", ""))
    
    if review and code_after:
        response = f"{review}\n\nImproved code:\n```\n{code_after}\n```"
    elif code_after:
        response = f"```\n{code_after}\n```"
    else:
        response = review
    
    messages.append({"role": "assistant", "content": response})
    
    return messages


def detect_text_only(sample: dict) -> bool:
    """检测纯文本格式 (最低优先级)"""
    return "text" in sample or "content" in sample


def convert_text_only(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换纯文本格式"""
    text = get_first_field(sample, ["text", "content"])
    return [
        {"role": "user", "content": "Complete the following:"},
        {"role": "assistant", "content": text}
    ]


# =============================================================================
# 格式注册表
# =============================================================================

class DatasetFormatRegistry:
    """
    可扩展的数据集格式注册表
    
    特性:
    - 自动格式检测
    - 插件式解析器架构
    - 优先级排序
    - 详细日志记录
    """
    
    def __init__(self, default_system_prompt: Optional[str] = None):
        self.default_system_prompt = default_system_prompt
        self._formats: list[FormatInfo] = []
        self._register_builtin_formats()
    
    def _register_builtin_formats(self):
        """注册所有内置格式"""
        
        # P0 - 对话类
        self.register("messages", 10, "Standard OpenAI messages format",
                     ["messages"], [], detect_messages, convert_messages)
        
        self.register("sharegpt", 11, "ShareGPT conversations format",
                     ["conversations"], [], detect_sharegpt, convert_sharegpt)
        
        self.register("openai_chatml", 12, "OpenAI ChatML format (user+assistant fields)",
                     ["user", "assistant"], ["system"], detect_openai_chatml, convert_openai_chatml)
        
        self.register("dialog_turns", 13, "Multi-turn dialog format",
                     [], ["dialog", "turns", "dialogue", "conversation"], detect_dialog_turns, convert_dialog_turns)
        
        self.register("history_response", 14, "History + response format",
                     ["history"], ["response", "reply", "query"], detect_history_response, convert_history_response)
        
        # P0 - 指令类
        self.register("alpaca", 20, "Alpaca format (instruction+input+output)",
                     ["instruction"], ["input", "output", "response"], detect_alpaca, convert_alpaca)
        
        self.register("dolly", 21, "Dolly format (context+instruction+response)",
                     ["context", "instruction", "response"], [], detect_dolly, convert_dolly)
        
        self.register("wizardlm", 22, "WizardLM format (with complexity)",
                     ["instruction"], ["complexity"], detect_wizardlm, convert_wizardlm)
        
        # P0 - 代码生成
        self.register("humaneval", 30, "HumanEval format",
                     ["task_id", "prompt"], ["canonical_solution", "solution"], detect_humaneval, convert_humaneval)
        
        self.register("mbpp", 31, "MBPP format",
                     ["text", "code"], ["task_id"], detect_mbpp, convert_mbpp)
        
        self.register("taco", 32, "TACO/CodeContests format",
                     ["prompt"], ["reference", "solution", "starter_code"], detect_taco, convert_taco)
        
        self.register("code_completion", 33, "Code completion/FIM format",
                     ["prefix", "middle"], ["suffix"], detect_code_completion, convert_code_completion)
        
        self.register("code_instruct", 34, "Code instruction format (prompt+code)",
                     ["prompt", "code"], [], detect_code_instruct, convert_code_instruct)
        
        # P1 - 问答类
        self.register("qa_with_context", 40, "QA with context (RAG)",
                     ["question"], ["context", "passage", "document", "answer"], detect_qa_with_context, convert_qa_with_context)
        
        self.register("qa_choices", 41, "Multiple choice QA",
                     ["question"], ["choices", "options"], detect_qa_choices, convert_qa_choices)
        
        self.register("qa_basic", 42, "Basic QA format",
                     ["question"], ["answer", "answers"], detect_qa_basic, convert_qa_basic)
        
        # P1 - 生成类
        self.register("summarization", 50, "Summarization format",
                     [], ["document", "article", "summary", "highlights"], detect_summarization, convert_summarization)
        
        self.register("translation", 51, "Translation format",
                     [], ["source", "target"], detect_translation, convert_translation)
        
        self.register("rewriting", 52, "Rewriting/paraphrase format",
                     [], ["original", "rewritten", "paraphrase"], detect_rewriting, convert_rewriting)
        
        # P2 - 特殊类
        self.register("chain_of_thought", 60, "Chain of thought format",
                     ["question"], ["chain_of_thought", "cot", "reasoning"], detect_chain_of_thought, convert_chain_of_thought)
        
        self.register("sql_generation", 61, "SQL generation format",
                     ["question"], ["query", "sql", "schema"], detect_sql_generation, convert_sql_generation)
        
        self.register("math_solving", 62, "Math problem solving format",
                     [], ["problem", "solution", "answer"], detect_math_solving, convert_math_solving)
        
        self.register("code_review", 63, "Code review format",
                     ["code_before"], ["review", "code_after", "feedback"], detect_code_review, convert_code_review)
        
        # 兜底 - 纯文本
        self.register("text_only", 100, "Plain text format (fallback)",
                     [], ["text", "content"], detect_text_only, convert_text_only)
    
    def register(
        self,
        name: str,
        priority: int,
        description: str,
        required_fields: list[str],
        optional_fields: list[str],
        detector: Callable[[dict], bool],
        converter: Callable[[dict, Optional[str]], list[dict]]
    ):
        """注册新格式"""
        format_info = FormatInfo(
            name=name,
            priority=priority,
            description=description,
            required_fields=required_fields,
            optional_fields=optional_fields,
            detector=detector,
            converter=converter
        )
        self._formats.append(format_info)
        # 按优先级排序
        self._formats.sort(key=lambda x: x.priority)
    
    def detect_format(self, sample: dict) -> str:
        """自动检测样本格式"""
        for fmt in self._formats:
            try:
                if fmt.detector(sample):
                    return fmt.name
            except Exception as e:
                logger.warning(f"Format detection error for {fmt.name}: {e}")
                continue
        return "unknown"
    
    def convert_to_messages(
        self, 
        sample: dict, 
        format_name: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> list[dict]:
        """将样本转换为标准 messages 格式"""
        
        # 自动检测格式
        if format_name is None or format_name == "unknown":
            format_name = self.detect_format(sample)
        
        if format_name == "unknown":
            logger.warning(f"Unknown format for sample with keys: {list(sample.keys())}")
            return []
        
        # 查找转换器
        for fmt in self._formats:
            if fmt.name == format_name:
                try:
                    sys_prompt = system_prompt or self.default_system_prompt
                    return fmt.converter(sample, sys_prompt)
                except Exception as e:
                    logger.error(f"Conversion error for format {format_name}: {e}")
                    return []
        
        return []
    
    def get_format_info(self, name: str) -> Optional[FormatInfo]:
        """获取格式信息"""
        for fmt in self._formats:
            if fmt.name == name:
                return fmt
        return None
    
    def list_formats(self) -> list[str]:
        """列出所有支持的格式"""
        return [fmt.name for fmt in self._formats]
    
    def get_format_stats(self, samples: list[dict]) -> dict[str, int]:
        """统计样本集中各格式的数量"""
        stats: dict[str, int] = {}
        for sample in samples:
            fmt = self.detect_format(sample)
            stats[fmt] = stats.get(fmt, 0) + 1
        return stats


# =============================================================================
# 便捷函数
# =============================================================================

_default_registry: Optional[DatasetFormatRegistry] = None

def get_registry() -> DatasetFormatRegistry:
    """获取默认注册表实例（单例）"""
    global _default_registry
    if _default_registry is None:
        _default_registry = DatasetFormatRegistry()
    return _default_registry


def detect_format(sample: dict) -> str:
    """检测样本格式（便捷函数）"""
    return get_registry().detect_format(sample)


def convert_sample(sample: dict, system_prompt: Optional[str] = None) -> list[dict]:
    """转换样本为 messages 格式（便捷函数）"""
    return get_registry().convert_to_messages(sample, system_prompt=system_prompt)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    # 快速测试
    registry = DatasetFormatRegistry()
    
    print("=" * 60)
    print("Supported Formats:")
    print("=" * 60)
    for fmt in registry._formats:
        print(f"  [{fmt.priority:3d}] {fmt.name:20s} - {fmt.description}")
    
    print("\n" + "=" * 60)
    print("Test Cases:")
    print("=" * 60)
    
    test_samples = [
        {"messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]},
        {"conversations": [{"from": "human", "value": "Hi"}, {"from": "gpt", "value": "Hello!"}]},
        {"instruction": "Write hello world", "input": "", "output": "print('Hello, World!')"},
        {"prompt": "def add(a, b):", "code": "    return a + b"},
        {"question": "What is 2+2?", "answer": "4"},
        {"text": "This is a plain text sample."},
        {"prompt": "Solve the problem", "reference": "solution here", "starter_code": "def solve():"},
        {"task_id": "HumanEval/0", "prompt": "def is_prime(n):", "canonical_solution": "    ..."},
    ]
    
    for sample in test_samples:
        fmt = registry.detect_format(sample)
        messages = registry.convert_to_messages(sample)
        print(f"\nSample keys: {list(sample.keys())}")
        print(f"  Detected: {fmt}")
        print(f"  Messages: {len(messages)} turns")
