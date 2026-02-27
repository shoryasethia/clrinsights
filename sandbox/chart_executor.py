"""
Sandboxed matplotlib code executor for LLM-generated visualization code.
Runs code in a subprocess with a timeout, captures base64 PNG images.
"""
import io
import os
import sys
import json
import base64
import tempfile
import subprocess
from pathlib import Path
from typing import Any


# Template that wraps LLM-generated code with image capture
_RUNNER_TEMPLATE = r'''
import io
import sys
import json
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import scipy.stats as stats
import seaborn as sns
import statsmodels.api as sm
import math
import datetime
import textwrap
from collections import Counter, defaultdict

# --- Data injected by the executor ---
_RAW_DATA = {data_json}
# Auto-convert list-of-dicts entries to DataFrames so LLM code can use column-name indexing
DATA = {
    k: pd.DataFrame(v) if isinstance(v, list) and v and isinstance(v[0], dict) else v
    for k, v in _RAW_DATA.items()
}

# Styling defaults
plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.labelsize': 8,
    'axes.titlesize': 10,
    'axes.titleweight': 'bold',
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'figure.dpi': 120,
})

# --- LLM-generated code starts here ---
{user_code}
# --- LLM-generated code ends here ---

# Capture all open figures as base64 PNGs
_images = []
for _fig_num in plt.get_fignums():
    _fig = plt.figure(_fig_num)
    _fig.tight_layout()
    _buf = io.BytesIO()
    _fig.savefig(_buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    _buf.seek(0)
    _images.append(base64.b64encode(_buf.read()).decode())
    _buf.close()
    plt.close(_fig)

# Output as JSON to stdout
print("__CHART_OUTPUT__" + json.dumps({"images": _images}))
'''


def _sanitize_error(stderr: str) -> str:
    """
    Extract a clean, user-friendly error message from Python traceback stderr.
    Strips temp file paths and line numbers, returns just the error type + message.
    """
    import re as _re
    lines = stderr.strip().splitlines()
    if not lines:
        return "Unknown chart error"
    
    # Find the last line that looks like an exception (e.g., "KeyError: 'sender'")
    for line in reversed(lines):
        stripped = line.strip()
        # Match common Python exception patterns: ErrorType: message
        if _re.match(r'^[A-Z]\w*(Error|Exception|Warning)', stripped):
            return stripped[:300]
    
    # If no exception line found, return the last non-empty line (cleaned)
    last = lines[-1].strip()
    # Strip file path references
    last = _re.sub(r'File "[^"]*"', 'File "<chart>"', last)
    return last[:300] if last else "Chart generation failed"


def execute_chart_code(
    code: str,
    data: dict[str, Any],
    timeout: int = 30
) -> dict[str, Any]:
    """
    Execute LLM-generated matplotlib code in a subprocess.
    
    Args:
        code: Python code that creates matplotlib figures
        data: Dict of data variables to inject (key → value)
        timeout: Max execution time in seconds
        
    Returns:
        dict with 'images' (list of base64 strings), 'error' (str or None)
    """
    # Build the full script
    data_json = json.dumps(data, default=str)
    script = _RUNNER_TEMPLATE.replace('{data_json}', data_json).replace('{user_code}', code)
    
    # Write to temp file
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    try:
        tmp.write(script)
        tmp.close()
        
        # Find the Python executable (same one running this process)
        python_exe = sys.executable
        
        # Run in subprocess
        result = subprocess.run(
            [python_exe, tmp.name],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            env={**os.environ, 'MPLBACKEND': 'Agg'}
        )
        
        # Parse output
        stdout = result.stdout
        stderr = result.stderr
        
        if result.returncode != 0:
            return {
                'images': [],
                'error': f"Chart code failed: {_sanitize_error(stderr)}"
            }
        
        # Extract chart output
        marker = "__CHART_OUTPUT__"
        if marker in stdout:
            json_str = stdout.split(marker, 1)[1].strip()
            output = json.loads(json_str)
            return {
                'images': output.get('images', []),
                'error': None
            }
        else:
            return {
                'images': [],
                'error': f"No chart output produced. {_sanitize_error(stderr)}"
            }
    
    except subprocess.TimeoutExpired:
        return {
            'images': [],
            'error': f"Chart generation timed out after {timeout}s"
        }
    except Exception as e:
        return {
            'images': [],
            'error': f"Chart executor error: {str(e)}"
        }
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
