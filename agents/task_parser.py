"""
Task Parser - Convert natural language to structured task.
"""

from typing import Dict, Any, Optional
import re


def parse_task(text: str) -> Dict[str, Any]:
    """
    Parse natural language task description into structured format.
    
    Examples:
        "用 S6A 和 JA3 做星间交叉" 
        -> {"primary_sat": "S6A", "aux_data_type": "JA3", "method": "star_cross"}
    """
    
    result = {
        "primary_sat": None,
        "aux_data_type": None,
        "method": None,
        "filters": {},
        "start_date": None,
        "end_date": None
    }
    
    text_lower = text.lower()
    
    # Detect method
    if any(kw in text for kw in ["自交叉", "self"]):
        result["method"] = "self_cross"
    elif any(kw in text for kw in ["交叉", "cross"]):
        result["method"] = "star_cross"
    elif any(kw in text for kw in ["验潮", "tide", "anchor"]):
        result["method"] = "tide_ext"
        result["aux_data_type"] = "YCZ"
    
    # Extract satellite IDs - enhanced patterns
    # Patterns: S6A, JA3, HY-1D, Sentinel-6, CryoSat-2, Jason-3, etc.
    sat_patterns = [
        r"(S6[A-Z])",              # Sentinel-6 variants
        r"(JA[0-9])",              # Jason variants
        r"(HY-\d+[A-Z]?)",         # HY series
        r"(Sentinel[-]?[36])",     # Sentinel-3/6
        r"(Cryosat[-]?\d?)",       # CryoSat
        r"(Jason[-]?\d)?",         # Jason series
        r"([A-Z]{2,3}-\d[A-Z]?)",  # Generic pattern
    ]
    
    satellites = []
    for pattern in sat_patterns:
        matches = re.findall(pattern, text, re.I)
        satellites.extend([m for m in matches if m and m not in satellites])
    
    # Also try simple 3-letter codes
    if not satellites:
        simple_matches = re.findall(r'\b([A-Z]{2,4})\b', text)
        satellites = [m for m in simple_matches if m not in satellites]
    
    if satellites:
        result["primary_sat"] = satellites[0]
        if len(satellites) > 1:
            result["aux_data_type"] = satellites[1]
        elif result["method"] == "self_cross":
            result["aux_data_type"] = satellites[0]  # Self-cross uses same sat
    
    # Extract dates (YYYYMMDD or YYYY-MM-DD or YYYY 年 MM 月)
    # Chinese format: 2023 年 5 月 / 2023年5月
    cn_date = re.search(r"(\d{4})\s*年\s*(?:(\d{1,2})\s*月)?(?:\s*(\d{1,2})\s*日?)?", text)
    if cn_date:
        year = cn_date.group(1)
        month = cn_date.group(2) or "01"
        day = cn_date.group(3) or "01"
        result["filters"]["year"] = int(year)
        result["filters"]["month"] = int(month)
        result["start_date"] = f"{year}{month.zfill(2)}{day.zfill(2)}"
        # If only month given, set end to last day of month
        if not cn_date.group(3):
            import calendar
            last_day = calendar.monthrange(int(year), int(month))[1]
            result["end_date"] = f"{year}{month.zfill(2)}{last_day:02d}"
        else:
            result["end_date"] = result["start_date"]
    else:
        # ISO format: 2023-05-01 or 20230501
        iso_date = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", text)
        if iso_date:
            result["start_date"] = f"{iso_date.group(1)}{iso_date.group(2)}{iso_date.group(3)}"
            result["end_date"] = result["start_date"]
    
    return result
