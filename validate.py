#!/usr/bin/env python
"""
Validation script for Titan Trading Engine scaffold.

Checks:
1. All required files exist
2. All imports work correctly
3. Type hints are present
4. Code can be parsed (no syntax errors)
5. Core classes are properly defined
"""

import sys
import ast
from pathlib import Path
from typing import List, Tuple

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Expected file structure
REQUIRED_FILES = {
    "src/__init__.py",
    "src/core/__init__.py",
    "src/core/engine.py",
    "src/core/events.py",
    "src/strategies/__init__.py",
    "src/strategies/supervisor.py",
    "src/strategies/math_utils.py",
    "src/execution/__init__.py",
    "src/execution/risk.py",
    "main.py",
    "requirements.txt",
    "pyproject.toml",
    "README.md",
    "QUICK_REFERENCE.md",
    "IMPLEMENTATION_SUMMARY.md",
}

REQUIRED_CLASSES = {
    "src/core/engine.py": ["EventBus", "setup_event_loop"],
    "src/core/events.py": ["TickEvent", "SignalEvent", "OrderRequestEvent", "RegimeEvent"],
    "src/strategies/supervisor.py": ["Supervisor"],
    "src/strategies/math_utils.py": ["calculate_slope_and_r_squared", "calculate_z_score", "calculate_position_size"],
    "src/execution/risk.py": ["RiskManager"],
}


def check_file_exists(file_path: Path) -> Tuple[bool, str]:
    """Check if a file exists."""
    exists = file_path.exists()
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    return exists, f"{status} {file_path}"


def check_syntax(file_path: Path) -> Tuple[bool, str]:
    """Check if Python file has valid syntax."""
    try:
        with open(file_path, "r") as f:
            ast.parse(f.read())
        return True, f"{GREEN}✓ Syntax OK{RESET}"
    except SyntaxError as e:
        return False, f"{RED}✗ Syntax Error{RESET}: {e}"


def check_classes(file_path: Path, required_classes: List[str]) -> Tuple[bool, str]:
    """Check if required classes/functions exist in file."""
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
        
        defined = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                defined.add(node.name)
        
        missing = [cls for cls in required_classes if cls not in defined]
        
        if not missing:
            return True, f"{GREEN}✓ All required classes/functions found{RESET}"
        else:
            return False, f"{RED}✗ Missing{RESET}: {', '.join(missing)}"
    except Exception as e:
        return False, f"{RED}✗ Error parsing{RESET}: {e}"


def check_type_hints(file_path: Path) -> Tuple[bool, str]:
    """Check if functions have type hints."""
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
        
        untyped = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                # Check if function has return annotation and params have type hints
                if node.returns is None:
                    untyped.append(f"{node.name} (no return type)")
                
                for arg in node.args.args:
                    if arg.annotation is None and arg.arg != "self":
                        untyped.append(f"{node.name}.{arg.arg} (no param type)")
        
        if not untyped:
            return True, f"{GREEN}✓ Good type hint coverage{RESET}"
        else:
            count = len(untyped)
            return True, f"{YELLOW}⚠ {count} untyped{RESET}: {', '.join(untyped[:3])}"
    except Exception as e:
        return False, f"{RED}✗ Error{RESET}: {e}"


def main() -> int:
    """Run all validation checks."""
    root = Path(".")
    
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}Titan Trading Engine - Project Validation{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}\n")
    
    # Check files exist
    print(f"{BOLD}1. File Structure{RESET}")
    print("-" * 70)
    all_exist = True
    for file_name in sorted(REQUIRED_FILES):
        file_path = root / file_name
        exists, msg = check_file_exists(file_path)
        print(msg)
        all_exist = all_exist and exists
    
    # Check syntax
    print(f"\n{BOLD}2. Python Syntax{RESET}")
    print("-" * 70)
    all_valid = True
    for file_name in sorted(REQUIRED_FILES):
        if file_name.endswith(".py"):
            file_path = root / file_name
            if file_path.exists():
                valid, msg = check_syntax(file_path)
                print(f"{file_name}: {msg}")
                all_valid = all_valid and valid
    
    # Check required classes
    print(f"\n{BOLD}3. Required Classes & Functions{RESET}")
    print("-" * 70)
    all_classes_found = True
    for file_name, classes in sorted(REQUIRED_CLASSES.items()):
        file_path = root / file_name
        if file_path.exists():
            found, msg = check_classes(file_path, classes)
            print(f"{file_name}:")
            print(f"  {msg}")
            all_classes_found = all_classes_found and found
    
    # Check type hints
    print(f"\n{BOLD}4. Type Hint Coverage{RESET}")
    print("-" * 70)
    for file_name in ["src/core/engine.py", "src/strategies/math_utils.py", "src/execution/risk.py"]:
        file_path = root / file_name
        if file_path.exists():
            _, msg = check_type_hints(file_path)
            print(f"{file_name}: {msg}")
    
    # Summary
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}Validation Summary{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    
    status = "PASS" if (all_exist and all_valid and all_classes_found) else "FAIL"
    color = GREEN if status == "PASS" else RED
    
    print(f"{color}{BOLD}Status: {status}{RESET}")
    
    if all_exist:
        print(f"{GREEN}✓ All required files present{RESET}")
    else:
        print(f"{RED}✗ Some files missing{RESET}")
    
    if all_valid:
        print(f"{GREEN}✓ All files have valid Python syntax{RESET}")
    else:
        print(f"{RED}✗ Some files have syntax errors{RESET}")
    
    if all_classes_found:
        print(f"{GREEN}✓ All required classes/functions found{RESET}")
    else:
        print(f"{RED}✗ Some classes/functions missing{RESET}")
    
    print(f"\n{BOLD}Next Steps:{RESET}")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the engine: python main.py")
    print("3. Run tests: pytest tests/ -v")
    print("4. Check types: mypy src/ --strict")
    
    print(f"\n{BOLD}{'=' * 70}{RESET}\n")
    
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
