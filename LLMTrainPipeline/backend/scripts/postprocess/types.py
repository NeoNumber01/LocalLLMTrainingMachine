"""
Data Types Definition Module
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class ErrorType(Enum):
    """Error type classification"""
    NONE = "none"
    SYNTAX_ERROR = "syntax_error"
    INDENTATION_ERROR = "indentation_error"
    IMPORT_ERROR = "import_error"
    NAME_ERROR = "name_error"
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    INDEX_ERROR = "index_error"
    KEY_ERROR = "key_error"
    ATTRIBUTE_ERROR = "attribute_error"
    RUNTIME_ERROR = "runtime_error"
    RECURSION_ERROR = "recursion_error"
    MEMORY_ERROR = "memory_error"
    TIMEOUT = "timeout"
    ASSERTION_ERROR = "assertion_error"
    INVALID_OUTPUT = "invalid_output"
    INTERFACE_ERROR = "interface_error"
    DANGEROUS_CODE = "dangerous_code"


@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    # Fix loop control
    max_rule_fix_attempts: int = 2
    max_patch_attempts: int = 3
    
    # Execution config
    execution_timeout: int = 10
    
    # Feature toggles
    enable_extract: bool = True
    enable_normalize: bool = True
    enable_validate: bool = True
    enable_rule_fix: bool = True
    enable_patch_loop: bool = False  # Requires LLM support
    
    # Test config
    enable_fuzzing: bool = False
    fuzz_runs: int = 50
    
    # Interface config
    default_signature: str = "def solve(nums: list[int]) -> int:"
    function_name: str = "solve"
    
    # Security config
    block_dangerous_code: bool = True
    dangerous_patterns: List[str] = field(default_factory=lambda: [
        r'\beval\s*\(',
        r'\bexec\s*\(',
        r'\bcompile\s*\(',
        r'\bopen\s*\(',
        r'\bos\.system\s*\(',
        r'\bsubprocess\.',
        r'\b__import__\s*\(',
        r'\bimportlib\.',
    ])


@dataclass
class ExecutionResult:
    """Code execution result"""
    passed: bool
    error_type: ErrorType = ErrorType.NONE
    error_message: str = ""
    execution_time_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    tests_passed: int = 0
    tests_total: int = 0


@dataclass
class PhaseResult:
    """Result of a single processing phase"""
    phase_name: str
    success: bool
    code: str
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    modifications: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Complete pipeline processing result"""
    success: bool
    final_code: str
    original_code: str
    
    # Error info
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    
    # Processing progress
    phases_completed: List[str] = field(default_factory=list)
    phase_results: List[PhaseResult] = field(default_factory=list)
    
    # Fix statistics
    rule_fix_attempts: int = 0
    patch_attempts: int = 0
    fixes_applied: List[str] = field(default_factory=list)
    
    # Performance
    total_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    
    # Logs
    logs: List[str] = field(default_factory=list)
    
    def add_log(self, message: str):
        """Add log entry"""
        self.logs.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "final_code": self.final_code,
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
            "phases_completed": self.phases_completed,
            "rule_fix_attempts": self.rule_fix_attempts,
            "patch_attempts": self.patch_attempts,
            "fixes_applied": self.fixes_applied,
            "total_time_ms": self.total_time_ms,
            "execution_time_ms": self.execution_time_ms,
        }
