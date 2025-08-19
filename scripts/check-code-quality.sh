#!/bin/bash

# =============================================================================
# Dev Agents - Code Quality Checker
# =============================================================================
# This script runs comprehensive code quality checks including linting, 
# formatting, type checking, security scanning, and more.
# Usage: ./scripts/check-code-quality.sh [--fix] [--fast] [--help]

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Flags
FIX_ISSUES=false
FAST_MODE=false
VERBOSE=false
STOP_ON_FIRST_FAILURE=false

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_subheader() {
    echo -e "\n${PURPLE}--- $1 ---${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED_CHECKS++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED_CHECKS++))
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${NC}  $1${NC}"
    fi
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

run_check() {
    local check_name="$1"
    local command="$2"
    local fix_command="${3:-}"
    local is_critical="${4:-true}"
    
    ((TOTAL_CHECKS++))
    
    print_subheader "$check_name"
    
    if eval "$command" > /tmp/check_output 2>&1; then
        print_success "$check_name passed"
        if [ "$VERBOSE" = true ]; then
            cat /tmp/check_output | head -20
        fi
    else
        local exit_code=$?
        if [ "$FIX_ISSUES" = true ] && [ -n "$fix_command" ]; then
            print_warning "$check_name failed, attempting to fix..."
            if eval "$fix_command" > /tmp/fix_output 2>&1; then
                print_info "Auto-fix completed, re-running check..."
                if eval "$command" > /tmp/check_output_retry 2>&1; then
                    print_success "$check_name passed after fix"
                    return 0
                else
                    print_error "$check_name still failing after auto-fix"
                fi
            else
                print_error "Auto-fix failed for $check_name"
            fi
        else
            print_error "$check_name failed"
        fi
        
        # Show output
        echo -e "${RED}Output:${NC}"
        cat /tmp/check_output | head -20
        
        if [ "$is_critical" = true ] && [ "$STOP_ON_FIRST_FAILURE" = true ]; then
            print_error "Stopping on first failure (critical check failed)"
            exit $exit_code
        fi
        
        return $exit_code
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --fix)
                FIX_ISSUES=true
                shift
                ;;
            --fast)
                FAST_MODE=true
                shift
                ;;
            --stop-on-fail)
                STOP_ON_FIRST_FAILURE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Dev Agents - Code Quality Checker

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --fix              Attempt to auto-fix issues where possible
    --fast             Run only fast checks (skip slow ones like mypy)
    --stop-on-fail     Stop on first critical failure
    -v, --verbose      Enable verbose output
    -h, --help         Show this help message

DESCRIPTION:
    This script runs comprehensive code quality checks:
    - Code formatting (Black, isort)
    - Linting (Ruff)
    - Type checking (mypy)
    - Security scanning (Bandit)
    - Documentation style (pydocstyle)
    - Import sorting
    - YAML/JSON validation
    - Test syntax validation

EXAMPLES:
    $0                 # Run all checks
    $0 --fix          # Run checks and auto-fix issues
    $0 --fast         # Skip slow checks like mypy
    $0 --fix --verbose # Fix issues with detailed output

EXIT CODES:
    0  All checks passed
    1  Some checks failed
    2  Critical error (missing dependencies, etc.)

EOF
}

# =============================================================================
# Check Functions
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local missing_tools=()
    
    # Check for required tools
    local tools=("python3" "black" "isort" "ruff" "mypy" "bandit")
    
    for tool in "${tools[@]}"; do
        if check_command "$tool"; then
            print_verbose "$tool found"
        else
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_info "Install them with: pip install -e .[dev]"
        exit 2
    fi
    
    print_success "All prerequisites available"
}

run_formatting_checks() {
    print_header "Code Formatting Checks"
    
    # Black formatting
    run_check "Black (Code Formatting)" \
        "black --check --config pyproject.toml src/ tests/" \
        "black --config pyproject.toml src/ tests/"
    
    # isort import sorting
    run_check "isort (Import Sorting)" \
        "isort --check-only --settings-path pyproject.toml src/ tests/" \
        "isort --settings-path pyproject.toml src/ tests/"
}

run_linting_checks() {
    print_header "Linting Checks"
    
    # Ruff linting
    run_check "Ruff (Fast Python Linter)" \
        "ruff check src/ tests/" \
        "ruff check --fix src/ tests/"
    
    # Ruff formatting (alternative to Black)
    run_check "Ruff Format" \
        "ruff format --check src/ tests/" \
        "ruff format src/ tests/"
}

run_type_checking() {
    if [ "$FAST_MODE" = true ]; then
        print_warning "Skipping type checking in fast mode"
        return
    fi
    
    print_header "Type Checking"
    
    # mypy type checking
    run_check "mypy (Static Type Checking)" \
        "mypy --config-file pyproject.toml src/" \
        "" \
        true
}

run_security_checks() {
    print_header "Security Checks"
    
    # Bandit security linting
    run_check "Bandit (Security Linting)" \
        "bandit -c pyproject.toml -r src/" \
        "" \
        true
    
    # Safety dependency checking (if available)
    if check_command safety; then
        run_check "Safety (Dependency Vulnerability Check)" \
            "safety check" \
            "" \
            false  # Non-critical as it may fail due to API limits
    fi
}

run_documentation_checks() {
    print_header "Documentation Checks"
    
    # pydocstyle docstring checking
    if check_command pydocstyle; then
        run_check "pydocstyle (Docstring Style)" \
            "pydocstyle --convention=google --add-ignore=D100,D101,D102,D103,D104,D105,D106,D107 src/" \
            "" \
            false  # Non-critical
    fi
}

run_file_checks() {
    print_header "File Format Checks"
    
    # YAML validation
    run_check "YAML Validation" \
        "python -c '
import yaml
import sys
files = [\"config/config.yaml\", \"config/prompts.yaml\", \".pre-commit-config.yaml\"]
for f in files:
    try:
        with open(f) as file:
            yaml.safe_load(file)
        print(f\"✓ {f}\")
    except Exception as e:
        print(f\"✗ {f}: {e}\", file=sys.stderr)
        sys.exit(1)
'" \
        "" \
        false
    
    # JSON validation (if any JSON files exist)
    if find . -name "*.json" -not -path "./venv/*" -not -path "./.git/*" | head -1 | grep -q .; then
        run_check "JSON Validation" \
            "find . -name '*.json' -not -path './venv/*' -not -path './.git/*' -exec python -m json.tool {} \; > /dev/null" \
            "" \
            false
    fi
    
    # Check for common issues
    run_check "Trailing Whitespace Check" \
        "! find src/ tests/ -name '*.py' -exec grep -l '[[:space:]]$' {} \;" \
        "find src/ tests/ -name '*.py' -exec sed -i 's/[[:space:]]*$//' {} \;"
    
    run_check "Mixed Line Endings Check" \
        "! find src/ tests/ -name '*.py' -exec file {} \; | grep -v 'ASCII text'" \
        "" \
        false
}

run_import_checks() {
    print_header "Import and Syntax Checks"
    
    # Check for syntax errors
    run_check "Python Syntax Check" \
        "python -m py_compile $(find src/ -name '*.py')" \
        "" \
        true
    
    # Check imports
    run_check "Import Check" \
        "python -c '
import sys
sys.path.insert(0, \"src\")
try:
    import src.core.config
    import src.core.prompts
    import src.core.log
    print(\"Core imports successful\")
except ImportError as e:
    print(f\"Import error: {e}\", file=sys.stderr)
    sys.exit(1)
'" \
        "" \
        true
}

run_test_validation() {
    if [ "$FAST_MODE" = true ]; then
        print_warning "Skipping test validation in fast mode"
        return
    fi
    
    print_header "Test Validation"
    
    # Check test syntax
    if [ -d "tests/" ]; then
        run_check "Test Syntax Validation" \
            "python -m pytest tests/ --collect-only -q" \
            "" \
            false
    fi
}

# =============================================================================
# Main Execution
# =============================================================================

print_summary() {
    print_header "Code Quality Summary"
    
    echo -e "\n${BLUE}Results:${NC}"
    echo -e "  Total Checks: $TOTAL_CHECKS"
    echo -e "  ${GREEN}Passed: $PASSED_CHECKS${NC}"
    echo -e "  ${RED}Failed: $FAILED_CHECKS${NC}"
    
    local percentage=0
    if [ $TOTAL_CHECKS -gt 0 ]; then
        percentage=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    fi
    
    echo -e "  Success Rate: $percentage%"
    
    if [ $FAILED_CHECKS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All code quality checks passed!${NC}"
        echo -e "Your code is ready for commit and review."
    else
        echo -e "\n${YELLOW}⚠ Some checks failed.${NC}"
        if [ "$FIX_ISSUES" = true ]; then
            echo -e "Auto-fix was enabled. Some issues may have been resolved."
            echo -e "Please review the changes and re-run the checks."
        else
            echo -e "Run with --fix to automatically fix some issues:"
            echo -e "  $0 --fix"
        fi
    fi
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    if [ $FAILED_CHECKS -gt 0 ]; then
        echo -e "1. Fix the failing checks listed above"
        echo -e "2. Re-run this script to verify fixes"
        echo -e "3. Commit your changes when all checks pass"
    else
        echo -e "1. Review any warnings above"
        echo -e "2. Run tests: ./scripts/run-tests.sh"
        echo -e "3. Create your commit!"
    fi
}

main() {
    echo -e "${BLUE}"
    cat << "EOF"
 ____            _       ___          _ _ _         
/ ___|___   __ _| | ___ / _ \ _   _  __ _| (_) |_ _   _ 
| |   / _ \ / _` | |/ _ \ | | | | | |/ _` | | | __| | | |
| |__| (_) | (_| |   __/ |_| | |_| | (_| | | | |_| |_| |
\____\___/ \__,_|_|\___|\__\_\\__,_|\__,_|_|_|\__|\__, |
                                                  |___/ 
    Code Quality Checker
EOF
    echo -e "${NC}"
    
    parse_args "$@"
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Initialize temp file cleanup
    trap 'rm -f /tmp/check_output /tmp/fix_output /tmp/check_output_retry' EXIT
    
    # Run all checks
    check_prerequisites
    
    # Core code quality checks
    run_formatting_checks
    run_linting_checks
    run_type_checking
    run_import_checks
    
    # Security and best practices
    run_security_checks
    run_documentation_checks
    
    # File and format validation
    run_file_checks
    run_test_validation
    
    # Print summary
    print_summary
    
    # Exit with appropriate code
    if [ $FAILED_CHECKS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function with all arguments
main "$@"