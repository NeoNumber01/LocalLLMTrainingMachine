#!/usr/bin/env python3
"""
Evaluation Report Generator - 生成标准化评测报告

格式支持:
- Markdown: 适合论文/课程报告
- HTML: 适合工程仪表盘
- JSON: 机器可读

报告结构遵循 P0/P1 标准:
① Overview - 模型/数据集/参数
② Core Metrics - Pass@k, Compile Rate, Runtime
③ Error Analysis - 错误分布
④ Code Quality - 接口合规/代码结构
⑤ Segment Analysis - 按难度/类型分析
⑥ Failure Cases - 失败案例
⑦ Evaluation Protocol - 评测方法论
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


@dataclass
class EvalReportData:
    """评测报告数据结构"""
    # Overview
    model_name: str
    dataset_name: str
    total_problems: int
    num_samples: int
    temperature: float
    seed: int
    eval_date: str
    eval_run_id: str
    
    # Core Metrics
    pass_at_1: float
    pass_at_5: float
    pass_at_10: float
    compile_rate: float
    mean_runtime_ms: float
    p50_runtime_ms: float
    p95_runtime_ms: float
    max_runtime_ms: float
    
    # Error Analysis
    syntax_error_rate: float
    runtime_error_rate: float
    timeout_rate: float
    assertion_error_rate: float
    import_error_rate: float
    memory_error_rate: float
    
    # Code Quality
    interface_compliance_rate: float
    extra_io_rate: float
    avg_code_length: float
    avg_line_count: float
    
    # Segment Analysis (optional)
    by_difficulty: Optional[Dict[str, Dict[str, float]]] = None
    by_category: Optional[Dict[str, Dict[str, float]]] = None
    
    # P1: Per-problem pass distribution
    per_problem_stats: Optional[Dict[str, float]] = None  # min, max, median, mean, std
    
    # Failure Cases
    failure_examples: Optional[List[Dict[str, Any]]] = None
    
    # P0: Failure examples by error type
    failure_examples_by_type: Optional[Dict[str, List[Dict[str, Any]]]] = None
    
    # Metadata
    generation_settings: Optional[Dict[str, Any]] = None
    judge_settings: Optional[Dict[str, Any]] = None
    environment_info: Optional[Dict[str, Any]] = None


class EvalReportGenerator:
    """评测报告生成器"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def from_eval_summary(summary_path: str) -> 'EvalReportData':
        """从 eval_summary.json 加载数据"""
        with open(summary_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return EvalReportData(
            model_name=data.get('base_model_name', 'Unknown'),
            dataset_name=data.get('dataset_info', {}).get('dataset_name', 'Unknown'),
            total_problems=data.get('dataset_info', {}).get('total_problems', 0),
            num_samples=data.get('generation_settings', {}).get('k', 10),
            temperature=data.get('generation_settings', {}).get('temperature', 0.2),
            seed=data.get('seed', 42),
            eval_date=data.get('eval_time', datetime.now().isoformat()),
            eval_run_id=data.get('eval_run_id', ''),
            
            pass_at_1=data.get('metrics_overall', {}).get('pass_at_1', 0.0),
            pass_at_5=data.get('metrics_overall', {}).get('pass_at_5', 0.0),
            pass_at_10=data.get('metrics_overall', {}).get('pass_at_10', 0.0),
            compile_rate=data.get('metrics_overall', {}).get('compile_rate', 0.0),
            mean_runtime_ms=data.get('time_stats', {}).get('mean_runtime_ms', 0.0),
            p50_runtime_ms=data.get('time_stats', {}).get('p50_runtime_ms', 0.0),
            p95_runtime_ms=data.get('time_stats', {}).get('p95_runtime_ms', 0.0),
            max_runtime_ms=data.get('time_stats', {}).get('max_runtime_ms', 0.0),
            
            syntax_error_rate=data.get('error_distribution', {}).get('syntax_error_rate', 0.0),
            runtime_error_rate=data.get('error_distribution', {}).get('runtime_error_rate', 0.0),
            timeout_rate=data.get('error_distribution', {}).get('timeout_rate', 0.0),
            assertion_error_rate=data.get('error_distribution', {}).get('assertion_error_rate', 0.0),
            import_error_rate=data.get('error_distribution', {}).get('import_error_rate', 0.0),
            memory_error_rate=data.get('error_distribution', {}).get('memory_error_rate', 0.0),
            
            # P0-FIX: 从 code_quality 字段读取真实数据
            interface_compliance_rate=data.get('code_quality', {}).get('interface_compliance_rate', 0.0),
            extra_io_rate=data.get('code_quality', {}).get('extra_io_rate', 0.0),
            avg_code_length=data.get('code_quality', {}).get('avg_code_length', 0.0),
            avg_line_count=data.get('code_quality', {}).get('avg_line_count', 0.0),
            
            by_difficulty=data.get('segment_breakdown', {}).get('by_difficulty'),
            by_category=data.get('segment_breakdown', {}).get('by_category'),
            
            # P1: Per-problem pass distribution
            per_problem_stats=data.get('per_problem_stats'),
            
            failure_examples=data.get('sample_results', [])[:10],  # 最多10个失败案例
            
            # P0: Failure examples by error type
            failure_examples_by_type=data.get('failure_examples_by_type'),
            
            generation_settings=data.get('generation_settings'),
            judge_settings=data.get('judge_settings'),
            environment_info=data.get('environment_info'),
        )
    
    def generate_markdown(self, data: EvalReportData) -> str:
        """生成 Markdown 格式报告"""
        report = []
        
        # Title
        report.append(f"# Evaluation Report\n")
        report.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        
        # ① Overview
        report.append("## ① Overview\n")
        report.append("| Field | Value |")
        report.append("|-------|-------|")
        report.append(f"| Model | {data.model_name if data.model_name != 'Unknown' else 'Unknown (check checkpoint_path)'} |")
        # P0-FIX: 0 problems 显示为 N/A
        problems_str = f"{data.total_problems} problems" if data.total_problems > 0 else "N/A (not logged in report)"
        report.append(f"| Dataset | {data.dataset_name} ({problems_str}) |")
        report.append(f"| num_samples | {data.num_samples} |")
        report.append(f"| temperature | {data.temperature} |")
        # P1-FIX: None seed 提示需要设置
        seed_str = str(data.seed) if data.seed is not None else "None (⚠️ consider setting for reproducibility)"
        report.append(f"| seed | {seed_str} |")
        report.append(f"| Eval Run ID | `{data.eval_run_id}` |")
        report.append(f"| Date | {data.eval_date[:10] if data.eval_date else 'N/A'} |\n")
        
        # ② Core Metrics
        report.append("## ② Core Metrics\n")
        report.append("| Metric | Value |")
        report.append("|--------|-------|")
        report.append(f"| **Pass@1** | {data.pass_at_1:.2f}% |")
        report.append(f"| Pass@5 | {data.pass_at_5:.2f}% |")
        report.append(f"| Pass@10 | {data.pass_at_10:.2f}% |")
        report.append(f"| Compile Rate | {data.compile_rate:.2f}% |")
        report.append(f"| Avg Runtime | {data.mean_runtime_ms:.1f}ms |")
        report.append(f"| P50 Runtime | {data.p50_runtime_ms:.1f}ms |")
        report.append(f"| P95 Runtime | {data.p95_runtime_ms:.1f}ms |")
        report.append(f"| Max Runtime | {data.max_runtime_ms:.1f}ms |\n")
        
        # ③ Error Analysis
        report.append("## ③ Error Analysis\n")
        report.append("| Error Type | Rate |")
        report.append("|------------|------|")
        report.append(f"| SyntaxError | {data.syntax_error_rate:.2f}% |")
        report.append(f"| RuntimeError | {data.runtime_error_rate:.2f}% |")
        report.append(f"| Timeout | {data.timeout_rate:.2f}% |")
        report.append(f"| AssertionError (WA) | {data.assertion_error_rate:.2f}% |")
        report.append(f"| ImportError | {data.import_error_rate:.2f}% |")
        report.append(f"| MemoryError | {data.memory_error_rate:.2f}% |\n")
        
        # ④ Code Quality
        report.append("## ④ Code Quality\n")
        report.append("| Metric | Value |")
        report.append("|--------|-------|")
        # P0-FIX: 值为 0 时显示 N/A 而不是 0，避免误导
        ic_val = f"{data.interface_compliance_rate:.1f}%" if data.interface_compliance_rate > 0 else "N/A (not logged)"
        eio_val = f"{data.extra_io_rate:.1f}%" if data.extra_io_rate > 0 else "N/A"
        acl_val = f"{data.avg_code_length:.0f} chars" if data.avg_code_length > 0 else "N/A (not logged)"
        aln_val = f"{data.avg_line_count:.1f}" if data.avg_line_count > 0 else "N/A (not logged)"
        report.append(f"| Interface Compliance | {ic_val} |")
        report.append(f"| Extra I/O Rate | {eio_val} |")
        report.append(f"| Avg Code Length | {acl_val} |")
        report.append(f"| Avg Lines | {aln_val} |\n")
        
        # Extra I/O 详细解释
        if data.extra_io_rate > 0:
            report.append("> **📌 About Extra I/O Rate**")
            report.append("> ")
            report.append("> - `print()` statements: **Do not affect test results** (tests check return values, not stdout)")
            report.append("> - `input()` statements: **Cause Timeout (TLE)** (code blocks waiting for stdin)")
            report.append("> - **High Extra I/O Rate** indicates the model's training data is biased towards competitive programming I/O style.")
            report.append("> - **Recommendation**: Consider prompt engineering or data cleaning to reduce I/O patterns.\n")
        
        # ⑤ Segment Analysis
        if data.by_difficulty:
            report.append("## ⑤ Segment Analysis\n")
            report.append("### By Difficulty\n")
            report.append("| Difficulty | Pass@1 | Compile Rate |")
            report.append("|------------|--------|--------------|")
            for diff, stats in data.by_difficulty.items():
                p1 = stats.get('pass_at_1', 0)
                cr = stats.get('compile_rate', 0)
                report.append(f"| {diff} | {p1:.1f}% | {cr:.1f}% |")
            report.append("")
        
        # P1: Per-Problem Pass Distribution
        if data.per_problem_stats:
            report.append("### Per-Problem Pass Rate Distribution\n")
            report.append("> Measures variance across problems - high std indicates uneven difficulty handling\n")
            report.append("| Statistic | Value |")
            report.append("|-----------|-------|")
            report.append(f"| Min | {data.per_problem_stats.get('min_pass_rate', 0):.1f}% |")
            report.append(f"| Median | {data.per_problem_stats.get('median_pass_rate', 0):.1f}% |")
            report.append(f"| Mean | {data.per_problem_stats.get('mean_pass_rate', 0):.1f}% |")
            report.append(f"| Max | {data.per_problem_stats.get('max_pass_rate', 0):.1f}% |")
            report.append(f"| Std Dev | {data.per_problem_stats.get('std_pass_rate', 0):.1f}% |")
            report.append(f"| Total Problems | {data.per_problem_stats.get('total_problems', 0)} |")
            report.append("")
        
        # P0: Failure Examples by Error Type (新实现 - 多样化采样)
        if data.failure_examples_by_type:
            report.append("## ⑥ Failure Case Examples (by Error Type)\n")
            report.append("> Diverse sampling: different tasks selected to show variety of failures\n")
            
            error_type_labels = {
                'syntax_error': '🔴 SyntaxError',
                'runtime_error': '🟠 RuntimeError',
                'assertion_error': '🟡 AssertionError (WA)',
                'timeout': '⏱️ Timeout',
                'import_error': '📦 ImportError',
                'wrong_answer': '❌ Wrong Answer',
                'other': '⚪ Other',
            }
            
            has_any_examples = False
            for error_type, label in error_type_labels.items():
                examples = data.failure_examples_by_type.get(error_type, [])
                if examples:
                    has_any_examples = True
                    report.append(f"### {label}\n")
                    for i, ex in enumerate(examples[:3], 1):
                        task_id = ex.get('task_id', 'N/A')
                        difficulty = ex.get('difficulty', 'N/A')
                        report.append(f"**Example {i}**: Task `{task_id}` (Difficulty: {difficulty})")
                        
                        # 显示完整 Prompt（使用 > 引用块格式，更安全）
                        prompt = ex.get('prompt_preview', '')
                        if prompt:
                            report.append(f"- **Prompt**:")
                            # 使用引用块格式，每行前加 > 
                            quoted_prompt = '\n'.join(f"> {line}" for line in prompt.split('\n'))
                            report.append(quoted_prompt)
                        
                        # 显示完整 Traceback（使用 4 个反引号避免内部反引号冲突）
                        traceback = ex.get('traceback_preview', '')
                        if traceback:
                            report.append("- **Error**:")
                            report.append(f"````\n{traceback}\n````")
                        
                        # 显示完整生成的代码（使用 4 个反引号避免 LLM 输出中的反引号破坏格式）
                        output = ex.get('output_preview', '')
                        if output:
                            report.append("- **Generated Output** (LLM raw response):")
                            report.append(f"````\n{output}\n````")
                        report.append("")
            
            if not has_any_examples:
                report.append("_No failure cases recorded in this evaluation run._\n")
        
        # Fallback: 旧版失败案例显示（如果新版数据不存在）
        elif data.failure_examples:
            report.append("## ⑥ Failure Case Examples\n")
            report.append("> Showing up to 5 failure examples for error analysis\n")
            shown_count = 0
            for i, case in enumerate(data.failure_examples[:10]):  # 遍历前10个找5个失败
                if case.get('verdict') not in ['AC', 'passed'] and shown_count < 5:
                    shown_count += 1
                    error_type = case.get('error_type') or case.get('errorType') or 'Unknown'
                    task_id = case.get('task_id') or case.get('taskId') or 'N/A'
                    verdict = case.get('verdict', 'N/A')
                    difficulty = case.get('difficulty', 'N/A')
                    
                    report.append(f"### Case {shown_count}: {error_type}")
                    report.append(f"- **Task ID**: `{task_id}`")
                    report.append(f"- **Difficulty**: {difficulty}")
                    report.append(f"- **Verdict**: {verdict}")
                    
                    # 展示错误信息（使用 4 个反引号避免冲突）
                    traceback = case.get('traceback', '')
                    if traceback:
                        report.append("- **Error**:")
                        report.append(f"````\n{traceback}\n````")
                    
                    # 展示生成的代码（使用 4 个反引号避免 LLM 输出中的反引号破坏格式）
                    code = case.get('post_process_output') or case.get('raw_output') or case.get('code', '')
                    if code:
                        report.append("- **Generated Output**:")
                        report.append(f"````\n{code}\n````")
                    report.append("")
            
            if shown_count == 0:
                report.append("_No failure cases available in the sample results._\n")
        else:
            report.append("## ⑥ Failure Case Examples\n")
            report.append("_No sample results logged. Enable `saveFailureCases` in eval config to capture failure details._\n")
        
        # ⑦ Evaluation Protocol (增强版 - P2 改进)
        report.append("## ⑦ Evaluation Protocol\n")
        report.append("### Generation Settings")
        report.append(f"- **Samples per task**: {data.num_samples}")
        report.append(f"- **Temperature**: {data.temperature}")
        report.append(f"- **Selection**: First k samples in generation order (not best-of-k)")
        report.append("")
        report.append("### Pass@k Definition")
        report.append("- A task passes at k if **at least one** of the first k samples passes **all** test cases")
        report.append("- Using unbiased estimator: `pass@k = 1 - C(n-c,k)/C(n,k)` where n=samples, c=correct")
        report.append("")
        report.append("### Judge Settings")
        report.append(f"- **Timeout**: {data.judge_settings.get('timeout_seconds', 10) if data.judge_settings else 10}s per test case")
        report.append("- **Sandbox**: subprocess isolation, no network/file access")
        report.append("- **Compile Rate**: Percentage of samples that run without SyntaxError\n")
        
        return "\n".join(report)
    
    def generate_html(self, data: EvalReportData) -> str:
        """生成 HTML 格式报告（增强版）"""
        
        # 生成分段统计 HTML
        segment_html = self._generate_segment_html(data)
        
        # 生成代码质量 HTML
        code_quality_html = self._generate_code_quality_html(data)
        
        # 生成失败案例 HTML
        failure_cases_html = self._generate_failure_cases_html(data)
        
        # 获取判题超时设置
        timeout_seconds = data.judge_settings.get('timeout_seconds', 10) if data.judge_settings else 10
        memory_limit = data.judge_settings.get('memory_limit_mb') if data.judge_settings else None
        memory_limit_str = f"{memory_limit}MB" if memory_limit else "No Limit"
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluation Report - {data.model_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 1000px; margin: 0 auto; padding: 2rem; background: #f5f5f5; }}
        .container {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #4f46e5; padding-bottom: 0.5rem; }}
        h2 {{ color: #374151; margin-top: 2rem; border-left: 4px solid #4f46e5; padding-left: 0.75rem; }}
        h3 {{ color: #4b5563; margin-top: 1.5rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f9fafb; font-weight: 600; }}
        .metric-highlight {{ font-size: 1.5rem; font-weight: bold; color: #4f46e5; }}
        .metric-card {{ display: inline-block; padding: 1rem; background: #f0f9ff; 
                       border-radius: 8px; margin: 0.5rem; text-align: center; min-width: 120px; }}
        .metric-label {{ font-size: 0.875rem; color: #6b7280; }}
        code {{ background: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.9rem; }}
        pre {{ background: #1f2937; color: #f9fafb; padding: 1rem; border-radius: 4px; overflow-x: auto; 
               font-size: 0.85rem; max-height: 300px; overflow-y: auto; }}
        .error-card {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; 
                      padding: 1rem; margin: 1rem 0; }}
        .error-type {{ color: #dc2626; font-weight: 600; }}
        .success-badge {{ background: #10b981; color: white; padding: 0.25rem 0.5rem; 
                         border-radius: 4px; font-size: 0.75rem; }}
        .warning-badge {{ background: #f59e0b; color: white; padding: 0.25rem 0.5rem; 
                         border-radius: 4px; font-size: 0.75rem; }}
        .info-box {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; 
                    padding: 1rem; margin: 1rem 0; }}
        .grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }}
        .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; }}
        @media (max-width: 768px) {{
            .grid-2, .grid-4 {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Evaluation Report</h1>
        <p><em>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        <p><code>Run ID: {data.eval_run_id}</code></p>
        
        <h2>① Overview</h2>
        <table>
            <tr><th>Field</th><th>Value</th></tr>
            <tr><td>Model</td><td>{data.model_name}</td></tr>
            <tr><td>Dataset</td><td>{data.dataset_name} ({data.total_problems} problems)</td></tr>
            <tr><td>num_samples (N)</td><td>{data.num_samples}</td></tr>
            <tr><td>temperature</td><td>{data.temperature}</td></tr>
            <tr><td>seed</td><td>{data.seed}</td></tr>
            <tr><td>Eval Date</td><td>{data.eval_date[:10] if data.eval_date else 'N/A'}</td></tr>
        </table>
        
        <h2>② Core Metrics</h2>
        <div style="text-align: center; margin: 1.5rem 0;">
            <div class="metric-card">
                <div class="metric-highlight">{data.pass_at_1:.1f}%</div>
                <div class="metric-label">Pass@1</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{data.pass_at_5:.1f}%</div>
                <div class="metric-label">Pass@5</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{data.pass_at_10:.1f}%</div>
                <div class="metric-label">Pass@10</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{data.compile_rate:.1f}%</div>
                <div class="metric-label">Compile Rate</div>
            </div>
        </div>
        
        <h3>Runtime Statistics</h3>
        <div class="grid-4">
            <div class="metric-card">
                <div class="metric-highlight">{data.mean_runtime_ms:.1f}ms</div>
                <div class="metric-label">Mean</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{data.p50_runtime_ms:.1f}ms</div>
                <div class="metric-label">P50</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{data.p95_runtime_ms:.1f}ms</div>
                <div class="metric-label">P95</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{data.max_runtime_ms:.1f}ms</div>
                <div class="metric-label">Max</div>
            </div>
        </div>
        
        <h2>③ Error Distribution</h2>
        <table>
            <tr><th>Error Type</th><th>Rate</th><th>Description</th></tr>
            <tr><td>SyntaxError</td><td>{data.syntax_error_rate:.2f}%</td><td>Code has syntax issues</td></tr>
            <tr><td>RuntimeError</td><td>{data.runtime_error_rate:.2f}%</td><td>Execution crashes</td></tr>
            <tr><td>Timeout (TLE)</td><td>{data.timeout_rate:.2f}%</td><td>Exceeded {timeout_seconds}s limit</td></tr>
            <tr><td>AssertionError (WA)</td><td>{data.assertion_error_rate:.2f}%</td><td>Wrong answer</td></tr>
            <tr><td>ImportError</td><td>{data.import_error_rate:.2f}%</td><td>Missing imports</td></tr>
            <tr><td>MemoryError (MLE)</td><td>{data.memory_error_rate:.2f}%</td><td>Exceeded memory limit</td></tr>
        </table>
        
        {code_quality_html}
        
        {segment_html}
        
        {failure_cases_html}
        
        <h2>⑦ Evaluation Protocol</h2>
        <div class="info-box">
            <h3 style="margin-top: 0;">Pass@k Definition</h3>
            <p>Task passes if <strong>≥1 of the first k samples</strong> passes all tests.</p>
            <p><strong>Unbiased Estimator</strong>: <code>pass@k = 1 - C(n-c, k) / C(n, k)</code></p>
            <p>where <code>n = num_samples ({data.num_samples})</code>, <code>c = number of correct samples</code></p>
            
            <h3>Judge Configuration</h3>
            <ul>
                <li><strong>Timeout</strong>: {timeout_seconds} seconds per test case</li>
                <li><strong>Memory Limit</strong>: {memory_limit_str}</li>
                <li><strong>Sandbox</strong>: subprocess isolation, no network/file access</li>
                <li><strong>Compile Rate</strong>: Percentage of samples without SyntaxError</li>
            </ul>
        </div>
    </div>
</body>
</html>'''
        return html
    
    def _generate_segment_html(self, data: EvalReportData) -> str:
        """生成分段统计 HTML"""
        if not data.by_difficulty and not data.by_category and not data.per_problem_stats:
            return ""
        
        html_parts = ['<h2>⑤ Segment Analysis</h2>']
        
        if data.by_difficulty:
            html_parts.append('<h3>By Difficulty</h3>')
            html_parts.append('<table>')
            html_parts.append('<tr><th>Difficulty</th><th>Count</th><th>Pass@1</th><th>Compile Rate</th></tr>')
            for diff, stats in data.by_difficulty.items():
                count = stats.get('count', 0)
                p1 = stats.get('pass_at_1', 0)
                cr = stats.get('compile_rate', 0)
                html_parts.append(f'<tr><td>{diff}</td><td>{count}</td><td>{p1:.1f}%</td><td>{cr:.1f}%</td></tr>')
            html_parts.append('</table>')
        
        if data.by_category:
            html_parts.append('<h3>By Category</h3>')
            html_parts.append('<table>')
            html_parts.append('<tr><th>Category</th><th>Count</th><th>Pass@1</th><th>Compile Rate</th></tr>')
            for cat, stats in data.by_category.items():
                count = stats.get('count', 0)
                p1 = stats.get('pass_at_1', 0)
                cr = stats.get('compile_rate', 0)
                html_parts.append(f'<tr><td>{cat}</td><td>{count}</td><td>{p1:.1f}%</td><td>{cr:.1f}%</td></tr>')
            html_parts.append('</table>')
        
        # P1: Per-Problem Pass Rate Distribution
        if data.per_problem_stats:
            html_parts.append('<h3>Per-Problem Pass Rate Distribution</h3>')
            html_parts.append('<div class="info-box">')
            html_parts.append('<p><em>Measures variance across problems - high std indicates uneven difficulty handling</em></p>')
            html_parts.append('</div>')
            html_parts.append('<div class="grid-4">')
            
            min_val = data.per_problem_stats.get('min_pass_rate', 0)
            max_val = data.per_problem_stats.get('max_pass_rate', 0)
            median_val = data.per_problem_stats.get('median_pass_rate', 0)
            mean_val = data.per_problem_stats.get('mean_pass_rate', 0)
            std_val = data.per_problem_stats.get('std_pass_rate', 0)
            total = data.per_problem_stats.get('total_problems', 0)
            
            html_parts.append(f'''
            <div class="metric-card">
                <div class="metric-highlight">{min_val:.1f}%</div>
                <div class="metric-label">Min</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{median_val:.1f}%</div>
                <div class="metric-label">Median</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">{max_val:.1f}%</div>
                <div class="metric-label">Max</div>
            </div>
            <div class="metric-card">
                <div class="metric-highlight">±{std_val:.1f}%</div>
                <div class="metric-label">Std Dev</div>
            </div>''')
            html_parts.append('</div>')
            html_parts.append(f'<p><small>Based on {total} problems, mean = {mean_val:.1f}%</small></p>')
        
        return '\n        '.join(html_parts)
    
    def _generate_code_quality_html(self, data: EvalReportData) -> str:
        """生成代码质量 HTML"""
        # P0-FIX: Extra I/O 详细解释
        extra_io_note = ''
        if data.extra_io_rate > 0:
            extra_io_note = f'''
        <div class="info-box" style="margin-top: 1rem;">
            <h4 style="margin-top: 0;">📌 About Extra I/O Rate ({data.extra_io_rate:.1f}%)</h4>
            <ul style="margin-bottom: 0;">
                <li><code>print()</code> statements: <strong>Do not affect test results</strong> (tests check return values, not stdout)</li>
                <li><code>input()</code> statements: <strong>Cause Timeout (TLE)</strong> (code blocks waiting for stdin)</li>
                <li><strong>High Extra I/O Rate</strong> indicates the model's training data is biased towards competitive programming I/O style.</li>
                <li><strong>Recommendation</strong>: Consider prompt engineering or data cleaning to reduce I/O patterns.</li>
            </ul>
        </div>'''
        
        return f'''
        <h2>④ Code Quality</h2>
        <table>
            <tr><th>Metric</th><th>Value</th><th>Description</th></tr>
            <tr><td>Interface Compliance</td><td>{data.interface_compliance_rate:.1f}%</td><td>Contains function definition</td></tr>
            <tr><td>Extra I/O Rate</td><td>{data.extra_io_rate:.1f}%</td><td>Contains print/input statements</td></tr>
            <tr><td>Avg Code Length</td><td>{data.avg_code_length:.0f} chars</td><td>Average generated code length</td></tr>
            <tr><td>Avg Lines</td><td>{data.avg_line_count:.1f}</td><td>Average lines of code</td></tr>
        </table>
        {extra_io_note}'''
    
    def _generate_failure_cases_html(self, data: EvalReportData) -> str:
        """生成失败案例 HTML - 支持 P0 按错误类型分组"""
        
        # P0: 优先使用按错误类型分组的数据
        if data.failure_examples_by_type:
            error_type_labels = {
                'syntax_error': ('🔴 SyntaxError', '#fef2f2', '#fecaca'),
                'runtime_error': ('🟠 RuntimeError', '#fff7ed', '#fed7aa'),
                'assertion_error': ('🟡 AssertionError (WA)', '#fefce8', '#fef08a'),
                'timeout': ('⏱️ Timeout', '#f0f9ff', '#bae6fd'),
                'import_error': ('📦 ImportError', '#faf5ff', '#e9d5ff'),
                'wrong_answer': ('❌ Wrong Answer', '#fef2f2', '#fca5a5'),
                'other': ('⚪ Other', '#f9fafb', '#e5e7eb'),
            }
            
            html_parts = ['<h2>⑥ Failure Case Examples (by Error Type)</h2>']
            html_parts.append('<p><em>Diverse sampling: different tasks selected to show variety of failures</em></p>')
            
            has_any = False
            for error_type, (label, bg_color, border_color) in error_type_labels.items():
                examples = data.failure_examples_by_type.get(error_type, [])
                if not examples:
                    continue
                has_any = True
                html_parts.append(f'<h3>{label}</h3>')
                
                for i, ex in enumerate(examples[:3], 1):
                    task_id = ex.get('task_id', 'N/A')
                    difficulty = ex.get('difficulty', 'N/A')
                    prompt_preview = ex.get('prompt_preview', '')  # 完整显示
                    output_preview = ex.get('output_preview', '')  # 完整显示
                    traceback = ex.get('traceback_preview', '')  # 完整显示
                    
                    html_parts.append(f'''
        <div class="error-card" style="background: {bg_color}; border-color: {border_color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>Example {i}: {task_id}</strong>
                <span style="color: #6b7280; font-size: 0.875rem;">Difficulty: {difficulty}</span>
            </div>''')
                    
                    if prompt_preview:
                        html_parts.append(f'''
            <h4>Prompt</h4>
            <pre style="background: #f3f4f6; color: #1f2937; max-height: 200px; overflow-y: auto;">{self._escape_html(prompt_preview)}</pre>''')
                    
                    if output_preview:
                        html_parts.append(f'''
            <h4>Generated Code</h4>
            <pre style="max-height: 300px; overflow-y: auto;">{self._escape_html(output_preview)}</pre>''')
                    
                    if traceback:
                        html_parts.append(f'''
            <h4>Error Traceback</h4>
            <pre style="background: #1f2937; color: #f87171; max-height: 200px; overflow-y: auto;">{self._escape_html(traceback)}</pre>''')
                    
                    html_parts.append('        </div>')
            
            if not has_any:
                html_parts.append('<p><em>No failure cases recorded in this evaluation run.</em></p>')
            
            return '\n'.join(html_parts)
        
        # Fallback: 旧版失败案例显示
        if not data.failure_examples:
            return ""
        
        # 只显示非 AC 的案例
        failed_cases = [c for c in data.failure_examples if c.get('verdict') != 'AC'][:5]
        
        if not failed_cases:
            return ""
        
        html_parts = ['<h2>⑥ Failure Case Examples</h2>']
        
        for i, case in enumerate(failed_cases):
            task_id = case.get('task_id', 'N/A')
            verdict = case.get('verdict', 'Unknown')
            error_type = case.get('error_type', 'Unknown')
            traceback = case.get('traceback', '') or ''
            raw_output = case.get('raw_output', '') or ''
            
            html_parts.append(f'''
        <div class="error-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>Case {i+1}: {task_id}</strong>
                <span class="warning-badge">{verdict} - {error_type}</span>
            </div>''')
            
            if raw_output:
                html_parts.append(f'''
            <h4>Generated Code</h4>
            <pre style="max-height: 300px; overflow-y: auto;">{self._escape_html(raw_output)}</pre>''')
            
            if traceback:
                html_parts.append(f'''
            <h4>Error Traceback</h4>
            <pre style="max-height: 200px; overflow-y: auto;">{self._escape_html(traceback)}</pre>''')            
            html_parts.append('        </div>')
        
        return '\n'.join(html_parts)
    
    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符"""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    def generate_json(self, data: EvalReportData) -> str:
        """生成 JSON 格式报告"""
        return json.dumps(asdict(data), indent=2, ensure_ascii=False)
    
    def save_reports(self, data: EvalReportData, prefix: str = "eval_report"):
        """保存所有格式的报告"""
        # Markdown
        md_path = self.output_dir / f"{prefix}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_markdown(data))
        
        # HTML
        html_path = self.output_dir / f"{prefix}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_html(data))
        
        # JSON
        json_path = self.output_dir / f"{prefix}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_json(data))
        
        return {
            "markdown": str(md_path),
            "html": str(html_path),
            "json": str(json_path),
        }


def generate_report_from_summary(summary_path: str, output_dir: str = None) -> Dict[str, str]:
    """
    从 eval_summary.json 生成评测报告
    
    Args:
        summary_path: eval_summary.json 路径
        output_dir: 输出目录，默认为 summary_path 同目录
    
    Returns:
        生成的报告文件路径 dict
    """
    if output_dir is None:
        output_dir = os.path.dirname(summary_path)
    
    generator = EvalReportGenerator(output_dir)
    data = generator.from_eval_summary(summary_path)
    return generator.save_reports(data)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python eval_report_generator.py <eval_summary.json>")
        sys.exit(1)
    
    summary_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    paths = generate_report_from_summary(summary_path, output_dir)
    print(f"Reports generated:")
    for fmt, path in paths.items():
        print(f"  {fmt}: {path}")
