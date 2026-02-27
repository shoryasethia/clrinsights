import json
import re
from typing import Literal
from clrinsights.agent.state import AgentState
from clrinsights.tools import sql_tool, python_tool
from clrinsights.llm import gemini_client, groq_client, LLMProvider
from clrinsights.data import db_manager
from clrinsights.sandbox.chart_executor import execute_chart_code


def get_llm_client(provider: str = "groq"):
    """Get LLM client based on provider string from state."""
    if provider.lower() == "gemini":
        return gemini_client
    return groq_client


def _parse_llm_json(raw: str) -> dict:
    """
    Robustly parse JSON from LLM output, handling common issues:
    - Markdown code fences
    - Control characters inside strings
    - Trailing commas
    - Unescaped newlines inside JSON string values
    - Python-style triple-quoted strings (\"\"\"...\"\"\")
    - Text before/after the JSON object
    """
    # Strip markdown fences
    cleaned = raw.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()
    
    # Convert Python triple-quoted strings to JSON single-quoted strings
    # """...""" or '''...''' → "..."
    def _fix_triple_quotes(text):
        # Replace triple double-quotes: """content""" → "content"
        result = re.sub(
            r'"""\s*(.*?)\s*"""',
            lambda m: '"' + m.group(1).replace('\n', ' ').replace('\r', ' ').replace('"', '\\"') + '"',
            text,
            flags=re.DOTALL
        )
        # Replace triple single-quotes: '''content''' → "content"
        result = re.sub(
            r"'''\s*(.*?)\s*'''",
            lambda m: '"' + m.group(1).replace('\n', ' ').replace('\r', ' ').replace("'", "\\'") + '"',
            result,
            flags=re.DOTALL
        )
        return result
    
    cleaned = _fix_triple_quotes(cleaned)
    
    # Extract the outermost JSON object
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)
    
    # Try parsing as-is first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Fix common issues and retry
    fixed = cleaned
    # Remove control characters (but preserve escaped ones like \n in strings)
    fixed = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', fixed)
    # Replace actual newlines inside JSON string values with spaces
    fixed = fixed.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    # Remove trailing commas before } or ]
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    # Collapse multiple spaces
    fixed = re.sub(r' {2,}', ' ', fixed)
    
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # Last resort: try to fix unescaped quotes inside string values
    # Replace single quotes used as JSON delimiters with double quotes
    # (only if the whole thing looks single-quoted)
    if "'" in fixed and '"' not in fixed[:5]:
        sq_fixed = fixed.replace("'", '"')
        try:
            return json.loads(sq_fixed)
        except json.JSONDecodeError:
            pass
    
    # Final attempt: extract key fields manually with regex
    try:
        steps = []
        # Match sql_query with single or multi-line string values
        sql_matches = re.findall(r'"sql_query"\s*:\s*"((?:[^"\\]|\\.)*)"', fixed)
        desc_matches = re.findall(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', fixed)
        for i, sql in enumerate(sql_matches):
            desc = desc_matches[i] if i < len(desc_matches) else f"Step {i+1}"
            steps.append({'description': desc, 'sql_query': sql})
        
        reasoning_match = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', fixed)
        reasoning = reasoning_match.group(1) if reasoning_match else ""
        
        if steps:
            return {'steps': steps, 'reasoning': reasoning}
    except Exception:
        pass
    
    # Nothing worked — raise with context
    raise json.JSONDecodeError(
        f"Could not parse LLM response as JSON. Raw (first 300 chars): {raw[:300]}",
        raw, 0
    )


async def analyze_query_node(state: AgentState) -> AgentState:
    """
    Analyze user query and create a multi-step plan.
    A single user question may require multiple SQL queries, 
    multiple visualizations, and multiple computations.
    """
    query = state['query']
    schema_context = state['schema_context']
    trace = state.get('trace', [])
    
    system_prompt = f"""You are a senior data analyst. You write precise SQL queries to answer questions about UPI transaction data.

{schema_context}

Your task: Create a MINIMAL execution plan as JSON. Write SQL that computes the FINAL numbers directly — percentages, rates, rankings, comparisons — so the answer can be read straight from the results.

Return JSON:
{{
    "steps": [
        {{
            "description": "What this step computes",
            "sql_query": "SQL query (must compute final metrics, not raw data)"
        }}
    ],
    "reasoning": "One-line approach summary"
}}

SQL GUIDELINES:
- Compute percentages, rates, averages, ranks DIRECTLY in SQL using ROUND().
- Use CTEs or subqueries for complex calculations.
- ORDER BY the key metric DESC so the top result is first.
- LIMIT results to what's needed (top 5, top 10, etc.).
- Use meaningful column aliases (e.g., failure_rate_pct, total_volume, avg_value).
- For rate calculations: ROUND(COUNT(CASE WHEN ...) * 100.0 / COUNT(*), 2) AS rate_pct

PLAN GUIDELINES:
- Only use columns that exist in the schema. Never hallucinate column names.
- MOST questions need just 1 step with 1 SQL query. Use the fewest steps possible.
- If the user asks for MULTIPLE DIFFERENT analyses (e.g., "hourly trend AND category breakdown"), create SEPARATE steps — one SQL query per distinct analysis. Each step should return a complete independent result set.
- Do NOT combine unrelated data into one SQL query. If "hourly counts" and "category totals" are asked for, those are 2 separate queries.
- A single step = one GROUP BY dimension. Different grouping dimensions = different steps.

CONVERSATIONAL / META QUESTIONS:
- If the user asks about the data itself ("what is this data?", "describe the dataset"), about you ("who are you?"), or any general/conversational question that doesn't need SQL, return: {{"steps": [], "reasoning": "Conversational question — no SQL needed", "conversational_answer": "<your direct answer here>"}}
- For dataset description questions, mention: UPI (Unified Payments Interface) transaction data from India, covering fields like transaction types, amounts, banks, cities, success/failure status, timestamps, etc.
- For "who are you" questions, say you are an AI data analyst assistant that helps explore and analyze UPI transaction data.

EXAMPLES OF CORRECT PLANS:
- "Which transaction type has the highest failure rate?" → 1 step, 1 SQL
- "What is the total transaction volume?" → 1 step, 1 SQL
- "Compare volume AND failure rates by merchant" → 1 step, 1 SQL returning category, volume, failure_rate
- "Show hourly trend AND category breakdown for weekends" → 2 steps (hourly trend query + category breakdown query)
- "What is this data about?" → 0 steps, conversational_answer provided
"""
    
    prompt = f"User question: {query}\n\nCreate analysis plan (JSON):"
    
    try:
        client = get_llm_client(state.get('provider', 'groq'))
        response = await client.generate(prompt, system_prompt)
        
        trace.append({
            'step': 'Query analysis',
            'type': 'analysis',
            'prompt': prompt,
            'response': response
        })
        
        plan = _parse_llm_json(response)
        
        steps = plan.get('steps', [])
        
        # If the LLM provided a conversational answer (no SQL needed), use it directly
        if not steps and plan.get('conversational_answer'):
            return {
                **state,
                'steps': [],
                'current_step': 0,
                'visualizations': [],
                'sql_queries': [],
                'all_query_results': [],
                'answer': plan['conversational_answer'],
                'should_continue': False
            }
        
        # Fallback: if old-style single-step response, wrap it
        if not steps and plan.get('sql_query'):
            steps = [{
                'description': plan.get('reasoning', ''),
                'sql_query': plan.get('sql_query'),
            }]
        
        return {
            **state,
            'steps': steps,
            'current_step': 0,
            'visualizations': [],
            'sql_queries': [],
            'all_query_results': [],
            'messages': state['messages'] + [
                {'role': 'assistant', 'content': f"Plan: {plan.get('reasoning', '')} ({len(steps)} step{'s' if len(steps) != 1 else ''})"}
            ]
        }
    
    except Exception as e:
        trace.append({
            'step': f'Analysis failed: {str(e)}',
            'type': 'error',
            'prompt': None,
            'response': str(e)
        })
        return {
            **state,
            'steps': [],
            'current_step': 0,
            'visualizations': [],
            'sql_queries': [],
            'all_query_results': [],
            'error': f"Query analysis failed: {str(e)}",
            'should_continue': False
        }


async def prepare_step_node(state: AgentState) -> AgentState:
    """
    Prepare data for the current step from the plan.
    Sets sql_query from steps[current_step].
    """
    steps = state.get('steps', [])
    current = state.get('current_step', 0)
    
    if current >= len(steps):
        return {
            **state,
            'sql_query': None,
            'query_results': None,
        }
    
    step = steps[current]
    
    return {
        **state,
        'sql_query': step.get('sql_query'),
        'query_results': None,
    }


async def execute_sql_node(state: AgentState) -> AgentState:
    """Execute SQL query for the current step."""
    if not state.get('sql_query'):
        return state
    
    result = sql_tool(state['sql_query'])
    
    if result['success']:
        # Accumulate SQL queries
        sql_queries = list(state.get('sql_queries', []))
        sql_queries.append(state['sql_query'])
        
        # Accumulate results
        all_results = list(state.get('all_query_results', []))
        all_results.append(result['results'])
        
        return {
            **state,
            'query_results': result['results'],
            'sql_queries': sql_queries,
            'all_query_results': all_results,
            'error': None,
            'messages': state['messages'] + [
                {'role': 'system', 'content': f"Step {state.get('current_step', 0) + 1}: Query returned {result['row_count']} rows"}
            ]
        }
    else:
        # Don't expose error to user — store it for the fix node to handle
        return {
            **state,
            'error': result['error'],
            'retries': state.get('retries', 0) + 1
        }


async def fix_sql_node(state: AgentState) -> AgentState:
    """
    Auto-fix a failed SQL query using the LLM.
    The LLM sees the original query, the error message, and the schema,
    then rewrites the query to fix the issue.
    """
    error = state.get('error', '')
    failed_query = state.get('sql_query', '')
    schema_context = state['schema_context']
    query = state['query']
    
    system_prompt = f"""You are a SQL debugging expert. Fix the SQL query that failed.

{schema_context}

RULES:
- Return ONLY the corrected SQL query, nothing else. No explanation, no markdown.
- Use exact column names from the schema above.
- All column names are lowercase with underscores (e.g., transaction_type, amount_inr, hour_of_day).
- Do NOT use quotes around column names unless absolutely necessary.
- Fix the specific error mentioned.
"""
    
    prompt = f"""Original user question: {query}

Failed SQL query:
{failed_query}

Error message:
{error}

Write the corrected SQL query:"""
    
    try:
        client = get_llm_client(state.get('provider', 'groq'))
        response = await client.generate(prompt, system_prompt)
        
        # Clean the response to get just the SQL
        fixed_sql = response.strip().removeprefix('```sql').removeprefix('```').removesuffix('```').strip()
        
        # Update the step's sql_query too so prepare_step doesn't reuse the bad one
        steps = list(state.get('steps', []))
        current = state.get('current_step', 0)
        if current < len(steps):
            steps[current] = {**steps[current], 'sql_query': fixed_sql}
        
        return {
            **state,
            'sql_query': fixed_sql,
            'error': None,
            'steps': steps,
            'messages': state['messages'] + [
                {'role': 'system', 'content': f'Auto-fixed SQL (attempt {state.get("retries", 1)})'}
            ]
        }
    
    except Exception as e:
        return {
            **state,
            'error': f"SQL fix failed: {str(e)}",
            'should_continue': False
        }


async def generate_visualizations_node(state: AgentState) -> AgentState:
    """
    After ALL SQL steps are done, ask the LLM to write matplotlib code
    to create appropriate visualizations. The LLM decides:
    - How many charts (0, 1, 2, ...)
    - What type each chart should be (bar, line, pie, dual-axis, subplots, etc.)
    - How to lay out and style each chart
    
    The code runs in a sandboxed subprocess.
    """
    query = state['query']
    all_results = state.get('all_query_results', [])
    steps = state.get('steps', [])
    sql_queries = state.get('sql_queries', [])
    trace = state.get('trace', [])
    
    if not all_results:
        trace.append({
            'step': 'Skipped visualization — no query results',
            'type': 'info',
            'prompt': None,
            'response': None
        })
        return state
    
    # Build data summary for the LLM
    data_summary = []
    data_payload = {}
    
    for i, (step_results, step_sql) in enumerate(zip(all_results, sql_queries)):
        step_desc = steps[i].get('description', f'Step {i+1}') if i < len(steps) else f'Step {i+1}'
        var_name = f"step_{i+1}"
        data_payload[var_name] = step_results
        
        data_summary.append(f"\nDATA['{var_name}'] — {step_desc} (pandas DataFrame)")
        data_summary.append(f"  SQL: {step_sql}")
        data_summary.append(f"  Rows: {len(step_results)}")
        if step_results:
            cols = list(step_results[0].keys())
            data_summary.append(f"  Columns: {cols}")
            data_summary.append(f"  Access: DATA['{var_name}']['col_name'] or DATA['{var_name}'].iloc[0]['col_name'] for single row")
            # Show value ranges so the LLM can detect scale mismatches
            for col in cols:
                vals = [r[col] for r in step_results if isinstance(r.get(col), (int, float))]
                if vals:
                    data_summary.append(f"    {col}: min={min(vals)}, max={max(vals)}")
            if len(step_results) <= 5:
                data_summary.append(f"  Data: {json.dumps(step_results, default=str)}")
            else:
                data_summary.append(f"  Sample: {json.dumps(step_results[:3], default=str)}")
    
    system_prompt = """You are a data visualization expert. You write matplotlib code to create clear, informative charts.

WHEN TO VISUALIZE (mandatory — always create a chart for these):
- Categories compared by a metric (e.g., states by failure rate, banks by volume) → Bar chart
- Time-series or trends (hourly, daily, monthly) → Line chart
- Proportions / share / distribution → Pie chart or stacked bar
- Geographic entities (states, cities, regions) with metrics → Bar chart
- Comparisons across 3+ items → Bar chart
- Weekday vs Weekend or before/after comparisons → Grouped bar chart
- Top-N / Bottom-N rankings → Horizontal bar chart
Only skip visualization when the result is a single scalar value (one number, one row with one column). A result with one row but multiple columns (e.g., one transaction type's stats) CAN be visualized as a single-bar or gauge-style chart.

DATA FORMAT (CRITICAL):
- DATA['step_1'], DATA['step_2'], etc. are **pandas DataFrames** (NOT lists or dicts).
- Column access: DATA['step_1']['col_name']  → correct
- Single-row value: DATA['step_1']['col_name'].iloc[0]  → correct
- NEVER use DATA['step_1'][0] — integer indexing is a KeyError on DataFrames. Use .iloc[0] instead.
- Iterate rows: for _, row in DATA['step_1'].iterrows(): ...
- Convert column to list: DATA['step_1']['col_name'].tolist()
- Sort: DATA['step_1'].sort_values('col', ascending=False)

RULES:
1. You receive query results in a `DATA` dict. Access data via DATA['step_1'], DATA['step_2'], etc.
2. Decide how many charts are needed (could be 1, 2, or more). Each distinct analysis dimension should get its own figure.
3. Each chart must be its own `plt.figure()` call. Do NOT use subplots — create SEPARATE figures.
4. Use appropriate chart types: bar for categories, line for trends/time, pie for proportions.
5. Keep charts compact: figsize=(5, 3) for most, (5, 3.5) for pie charts.
6. Style professionally: remove top/right spines, use clean colors, readable font sizes (title=10, labels=8, ticks=7).
7. Add value labels on bars and data points when practical (use f-string formatting: counts with commas, rates with 1 decimal + %).
8. Always include clear titles and axis labels. Rotate x-labels if needed.
9. Sort bars by value (descending) unless the x-axis has a natural/ordinal order.
10. ORDINAL ORDERING (CRITICAL): Categories with a logical progression must ALWAYS be sorted in that order, NOT alphabetically:
    - Amount buckets: Low → Medium → High → Very High (or Micro → Small → Medium → Large)
    - Age groups: 18-25 → 26-35 → 36-45 → 46-55 → 56-65 → 65+
    - Time periods: Morning → Afternoon → Evening → Night
    - Days: Mon → Tue → Wed → Thu → Fri → Sat → Sun
    - Risk levels: Low → Medium → High → Critical
    - Frequency: Rarely → Sometimes → Often → Always
    To enforce this, define the correct order list and use df.set_index('col').reindex(order).reset_index() BEFORE plotting.
11. For grouped comparisons (e.g., weekday vs weekend per state), use grouped bars with a legend — never separate figures for each group.

SCALE RULES (CRITICAL — follow these strictly):
12. NEVER plot two metrics with vastly different magnitudes on the same Y-axis (e.g., counts in thousands + percentages 0-100).
    - If you have two such metrics, use `ax.twinx()` to create a secondary Y-axis. Label both axes clearly.
    - Example: left axis for "Transaction Count", right axis for "Failure Rate (%)".
13. Smart Y-axis limits: if values are close together (e.g., 94%-96%), zoom in with `ax.set_ylim(min_val * 0.98, max_val * 1.02)` so differences are visible.
14. For percentages, always set explicit ylim (e.g., 0-100 or tighter if values are in a narrow range). Never let a 0-5% metric share an axis scaled to 0-20000.
15. When using twinx(), use distinct colors for each axis and match the axis label color to the line color using `ax.tick_params(axis='y', labelcolor=color)`.
16. For bar + line combo: draw bars on the primary axis, line on the secondary (twinx) axis. Add legend combining both via `lines1 + lines2, labels1 + labels2`.

AVAILABLE (already imported — do NOT re-import these):
- matplotlib.pyplot as plt
- matplotlib.ticker as ticker
- numpy as np
- pandas as pd
- scipy.stats as stats
- seaborn as sns
- statsmodels.api as sm
- math, datetime, textwrap
- collections.Counter, collections.defaultdict
- DATA dict with your query results (each value is a pandas DataFrame)

FORBIDDEN:
- NEVER call plt.show() — figures are captured automatically.
- NEVER import matplotlib, numpy, scipy, pandas, seaborn, statsmodels, or any other library — they are pre-imported.
- NEVER index a DataFrame with an integer like df[0] — use df.iloc[0] for row access.

COLOR PALETTE: '#4285F4', '#EA4335', '#FBBC04', '#34A853', '#FF6D01', '#46BDC6', '#7B61FF'

OUTPUT: Write ONLY Python code. No markdown, no explanations, no ```python blocks. Just raw code.
If the result is truly a single scalar value, output exactly: pass"""

    prompt = f"""User question: {query}

Available data:
{chr(10).join(data_summary)}

Write matplotlib code to visualize this data appropriately. Decide how many charts and what types:"""

    try:
        client = get_llm_client(state.get('provider', 'groq'))
        response = await client.generate(prompt, system_prompt)
        
        # Clean the code — strip any markdown fence variant (```python, ```py, ```, etc.)
        code = response.strip()
        code = re.sub(r'^```[\w]*\s*', '', code)   # opening fence
        code = re.sub(r'\s*```$', '', code)         # closing fence
        code = code.strip()
        # Strip plt.show() calls and redundant imports that crash the headless backend
        code = re.sub(r'^\s*plt\.show\(\)\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*import\s+matplotlib.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*import\s+numpy.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*import\s+scipy.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*import\s+pandas.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*import\s+seaborn.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*import\s+statsmodels.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*from\s+matplotlib.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*from\s+scipy.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*from\s+pandas.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*from\s+seaborn.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*from\s+statsmodels.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^\s*from\s+collections.*$', '', code, flags=re.MULTILINE)
        
        trace.append({
            'step': 'Visualization code generation',
            'type': 'viz',
            'prompt': prompt,
            'response': code
        })
        
        # If LLM said no viz needed
        if code.strip() == 'pass' or not code.strip():
            return state
        
        # Execute the chart code in a sandboxed subprocess
        result = execute_chart_code(code, data_payload, timeout=30)
        
        # Auto-fix loop: retry up to 2 times on failure
        fix_attempts = 0
        max_fix_attempts = 2
        current_code = code
        
        while result['error'] and fix_attempts < max_fix_attempts:
            fix_attempts += 1
            trace.append({
                'step': f"Chart error (attempt {fix_attempts}): {result['error']}",
                'type': 'error',
                'prompt': None,
                'response': None
            })
            
            # Build data shape info for the LLM
            # data_payload values are raw lists-of-dicts; be defensive in case they aren't
            data_shape = {}
            for k, v in data_payload.items():
                try:
                    import pandas as _pd
                    if isinstance(v, _pd.DataFrame):
                        cols = list(v.columns)
                        sample = v.head(1).to_dict(orient='records')[0] if not v.empty else {}
                        num_rows = len(v)
                    elif isinstance(v, list) and v and isinstance(v[0], dict):
                        cols = list(v[0].keys())
                        sample = v[0]
                        num_rows = len(v)
                    else:
                        cols, sample, num_rows = [], {}, 0
                    data_shape[k] = {'columns': cols, 'sample_row': sample, 'num_rows': num_rows}
                except Exception:
                    data_shape[k] = {'columns': [], 'sample_row': {}, 'num_rows': 0}
            
            fix_prompt = f"""The following matplotlib code failed with an error. Fix it.

CODE:
{current_code}

ERROR:
{result['error']}

DATA SHAPE:
{json.dumps(data_shape, default=str, indent=2)}

RULES:
- Use exact column names from DATA SHAPE above.
- Do NOT import any libraries — matplotlib, numpy, pandas, scipy, seaborn, statsmodels are already imported.
- Do NOT call plt.show().

Return ONLY the fixed Python code. No markdown, no explanation."""
            
            fixed_response = await client.generate(fix_prompt, system_prompt)
            # Strip fence variants from fixed code too
            fixed_code = fixed_response.strip()
            fixed_code = re.sub(r'^```[\w]*\s*', '', fixed_code)
            fixed_code = re.sub(r'\s*```$', '', fixed_code)
            fixed_code = fixed_code.strip()
            # Strip imports from fix too
            fixed_code = re.sub(r'^\s*import\s+\w.*$', '', fixed_code, flags=re.MULTILINE)
            fixed_code = re.sub(r'^\s*from\s+\w.*$', '', fixed_code, flags=re.MULTILINE)
            fixed_code = re.sub(r'^\s*plt\.show\(\)\s*$', '', fixed_code, flags=re.MULTILINE)
            
            if fixed_code.strip() and fixed_code.strip() != 'pass':
                current_code = fixed_code
                result = execute_chart_code(fixed_code, data_payload, timeout=30)
        
        if result['images']:
            trace.append({
                'step': f"Generated {len(result['images'])} chart(s)" + (f" (after {fix_attempts} fix{'es' if fix_attempts > 1 else ''})" if fix_attempts else ''),
                'type': 'viz',
                'prompt': None,
                'response': None
            })
            return {
                **state,
                'visualizations': list(state.get('visualizations', [])) + result['images']
            }
        
        # All retries exhausted — log final error
        if result['error']:
            trace.append({
                'step': f"Chart generation failed after {fix_attempts} fix attempt(s): {result['error']}",
                'type': 'error',
                'prompt': None,
                'response': None
            })
        
        return state
    
    except Exception as e:
        trace.append({
            'step': f"Viz generation failed: {str(e)}",
            'type': 'error',
            'prompt': None,
            'response': str(e)
        })
        # Visualization failure shouldn't block the answer
        return state


async def advance_step_node(state: AgentState) -> AgentState:
    """Advance to the next step in the plan."""
    return {
        **state,
        'current_step': state.get('current_step', 0) + 1,
        'error': None,
        'retries': 0,
    }


async def generate_answer_node(state: AgentState) -> AgentState:
    """Generate final answer using ALL accumulated results."""
    # If a conversational answer was already provided (no SQL needed), use it
    if state.get('answer') and not state.get('all_query_results') and not state.get('query_results'):
        return {
            **state,
            'should_continue': False,
            'messages': state['messages'] + [
                {'role': 'assistant', 'content': state['answer']}
            ]
        }
    
    query = state['query']
    all_results = state.get('all_query_results', [])
    sql_queries = state.get('sql_queries', [])
    steps = state.get('steps', [])
    schema_context = state['schema_context']
    
    system_prompt = f"""You are a senior data analyst presenting findings to business leadership.

RESPONSE FORMAT — follow this strictly:
- Give the DIRECT ANSWER first with specific numbers and percentages.
- Rank or compare results clearly (highest to lowest, best to worst, etc.).
- Add one brief insight or possible explanation for the pattern observed.
- Keep it to 2-5 sentences. No fluff, no preamble, no "Based on our analysis...".
- Never describe your methodology or mention SQL/queries/datasets.
- Use exact numbers from the data. Format large numbers with commas.
- Use % for rates and proportions.

ANALYTICAL RIGOR (CRITICAL — follow these):
- NEVER say data is "not provided" or "not available". You have ALL the query results — compute any derived metrics yourself (averages, baselines, deltas) by reading the numbers in the results.
- When showing per-category breakdowns (by state, bank, type, etc.), ALWAYS provide the baseline/average for comparison. Example: "Delhi's failure rate of 5.22% is 1.4x the national average of 3.7%."
- If the query results contain an aggregate/national metric alongside breakdowns, use it explicitly as the comparison baseline.
- If the query results only have breakdowns, compute the overall average from the individual rows and use that as baseline. E.g., if you see states with rates [5.2, 4.1, 3.8, 3.5, 3.0], the average is ~3.9%.
- Flag ANOMALIES: If any metric is 100%, 0%, or an extreme outlier, call it out explicitly with a hypothesis. Example: "Failures occur exclusively on 4G networks (100%), suggesting a protocol-level incompatibility rather than random failures."
- QUANTIFY comparisons: Don't just say "higher" — say "2.3x higher" or "1.8 percentage points above average."

EXAMPLE — for "Which transaction type has the highest failure rate?":
"Bill Payments have the highest failure rate at 8.2%, followed by Recharges at 6.7%. P2M transactions have a 4.3% failure rate, while P2P transfers show the lowest at 2.1%. The overall average is 4.5%, making Bill Payments 1.8x worse than average. The higher failure rates in bill payments may be attributed to third-party biller system integrations."

CRITICAL: Use ONLY the actual numbers from the query results provided. Never fabricate data. But DO compute simple math (averages, ratios, deltas) from those numbers.
"""
    
    context_info = []
    
    for i, (step_results, step_sql) in enumerate(zip(all_results, sql_queries)):
        step_desc = steps[i].get('description', f'Step {i+1}') if i < len(steps) else f'Step {i+1}'
        context_info.append(f"\n--- {step_desc} ---")
        context_info.append(f"SQL: {step_sql}")
        context_info.append(f"Returned {len(step_results)} rows")
        if len(step_results) <= 10:
            context_info.append(f"Results: {json.dumps(step_results, indent=2)}")
        else:
            context_info.append(f"Sample (first 5): {json.dumps(step_results[:5], indent=2)}")
    
    # Fallback if no accumulated results but there are current results
    if not context_info and state.get('query_results'):
        results = state['query_results']
        context_info.append(f"Query returned {len(results)} rows")
        if len(results) <= 10:
            context_info.append(f"Results: {json.dumps(results, indent=2)}")
        else:
            context_info.append(f"Sample (first 5): {json.dumps(results[:5], indent=2)}")
    
    if context_info:
        prompt = f"""Question: {query}

Data:
{chr(10).join(context_info)}

Answer with specific numbers from the data above. Be direct — no methodology, no preamble:"""
    else:
        # No data — could be a conversational question or an error case
        prompt = f"""Question: {query}

No query results are available. If this is a conversational question, answer it directly. Otherwise, explain that the query could not be processed."""
    
    try:
        client = get_llm_client(state.get('provider', 'groq'))
        response = await client.generate(prompt, system_prompt)
        
        return {
            **state,
            'answer': response,
            'should_continue': False,
            'messages': state['messages'] + [
                {'role': 'assistant', 'content': response}
            ]
        }
    
    except Exception as e:
        return {
            **state,
            'error': f"Answer generation failed: {str(e)}",
            'should_continue': False
        }


def should_retry(state: AgentState) -> Literal["retry", "end"]:
    """Decide whether to retry or end."""
    if state.get('error') and state.get('retries', 0) < 2:
        return "retry"
    return "end"


def route_after_analysis(state: AgentState) -> Literal["prepare_step", "answer"]:
    """Route after query analysis."""
    # If analyze already provided a conversational answer, go straight to end
    if state.get('answer'):
        return "answer"
    steps = state.get('steps', [])
    if steps and any(s.get('sql_query') for s in steps):
        return "prepare_step"
    return "answer"


def route_after_sql(state: AgentState) -> Literal["advance_step", "fix_sql", "generate_viz"]:
    """After SQL execution, decide next action."""
    error = state.get('error')
    retries = state.get('retries', 0)
    
    if error and retries <= 3:
        return "fix_sql"
    elif error and retries > 3:
        # Too many retries — skip to next step or finish
        pass  # fall through to step check
    
    # Check if there are more steps to execute
    steps = state.get('steps', [])
    current = state.get('current_step', 0)
    
    if current < len(steps) - 1:
        return "advance_step"
    
    # All steps done — generate visualizations
    return "generate_viz"
