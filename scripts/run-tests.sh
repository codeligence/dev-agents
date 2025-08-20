#!/bin/bash

# =============================================================================
# Dev Agents - Comprehensive Test Runner
# =============================================================================
# This script runs the full test suite with coverage reporting, 
# performance monitoring, and detailed analysis.
# Usage: ./scripts/run-tests.sh [OPTIONS]

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

# Configuration flags
RUN_UNIT_TESTS=true
RUN_INTEGRATION_TESTS=true
RUN_SLOW_TESTS=false
GENERATE_COVERAGE=true
GENERATE_HTML_REPORT=false
FAIL_FAST=false
VERBOSE=false
PARALLEL=false
CLEAN_CACHE=false

# Test result tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

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
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit-only)
                RUN_INTEGRATION_TESTS=false
                shift
                ;;
            --integration-only)
                RUN_UNIT_TESTS=false
                shift
                ;;
            --include-slow)
                RUN_SLOW_TESTS=true
                shift
                ;;
            --no-coverage)
                GENERATE_COVERAGE=false
                shift
                ;;
            --html-report)
                GENERATE_HTML_REPORT=true
                shift
                ;;
            --fail-fast)
                FAIL_FAST=true
                shift
                ;;
            --parallel)
                PARALLEL=true
                shift
                ;;
            --clean-cache)
                CLEAN_CACHE=true
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
Dev Agents - Comprehensive Test Runner

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --unit-only         Run only unit tests
    --integration-only  Run only integration tests
    --include-slow      Include slow/long-running tests
    --no-coverage       Skip coverage reporting
    --html-report       Generate HTML coverage report
    --fail-fast         Stop on first test failure
    --parallel          Run tests in parallel (if supported)
    --clean-cache       Clean pytest cache before running
    -v, --verbose       Enable verbose output
    -h, --help          Show this help message

DESCRIPTION:
    This script runs the complete test suite including:
    - Unit tests with mocking
    - Integration tests with real services
    - Coverage analysis and reporting
    - Performance monitoring
    - Test result analysis

TEST CATEGORIES:
    unit        Fast tests with mocked dependencies
    integration Tests with real external services
    slow        Long-running or resource-intensive tests

EXAMPLES:
    $0                      # Run all tests with coverage
    $0 --unit-only         # Run only unit tests
    $0 --include-slow      # Include slow tests
    $0 --html-report       # Generate HTML coverage report
    $0 --fail-fast -v      # Stop on first failure, verbose output

EXIT CODES:
    0  All tests passed
    1  Some tests failed
    2  Critical error (missing dependencies, setup issues)

EOF
}

# =============================================================================
# Setup Functions
# =============================================================================

check_prerequisites() {
    print_header "Checking Test Prerequisites"
    
    local missing_deps=()
    
    # Check pytest
    if check_command pytest; then
        print_info "pytest found: $(pytest --version | head -1)"
    else
        missing_deps+=("pytest")
    fi
    
    # Check pytest plugins
    local plugins=("pytest-asyncio" "pytest-cov")
    for plugin in "${plugins[@]}"; do
        if python -c "import $plugin" 2>/dev/null; then
            print_info "$plugin available"
        else
            print_warning "$plugin not found (some features may be limited)"
        fi
    done
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        print_info "Install with: pip install -e .[dev]"
        exit 2
    fi
    
    print_success "Prerequisites check complete"
}

setup_test_environment() {
    print_header "Setting up Test Environment"
    
    cd "$PROJECT_ROOT"
    
    # Activate virtual environment if available
    if [ -d "venv" ]; then
        source venv/bin/activate
        print_info "Virtual environment activated"
    fi
    
    # Set test environment variables
    export ENV=testing
    export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"
    
    # Create test directories if they don't exist
    mkdir -p logs tests/fixtures tests/tmp
    
    # Clean pytest cache if requested
    if [ "$CLEAN_CACHE" = true ]; then
        print_info "Cleaning pytest cache..."
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
        rm -rf .coverage htmlcov/ .mypy_cache/
        print_success "Cache cleaned"
    fi
    
    print_success "Test environment ready"
}

# =============================================================================
# Test Execution Functions
# =============================================================================

build_pytest_args() {
    local args=()
    
    # Basic configuration
    args+=(--tb=short)  # Shorter traceback format
    args+=(--strict-markers --strict-config)
    
    # Verbosity
    if [ "$VERBOSE" = true ]; then
        args+=(-v)
    else
        args+=(-q)
    fi
    
    # Fail fast
    if [ "$FAIL_FAST" = true ]; then
        args+=(-x)
    fi
    
    # Parallel execution
    if [ "$PARALLEL" = true ] && python -c "import pytest_xdist" 2>/dev/null; then
        args+=(-n auto)
    fi
    
    # Coverage
    if [ "$GENERATE_COVERAGE" = true ]; then
        args+=(--cov=src --cov-report=term-missing)
        if [ "$GENERATE_HTML_REPORT" = true ]; then
            args+=(--cov-report=html:htmlcov)
        fi
        args+=(--cov-report=xml:coverage.xml)
    fi
    
    # Test selection based on markers
    local markers=()
    
    if [ "$RUN_UNIT_TESTS" = true ] && [ "$RUN_INTEGRATION_TESTS" = true ]; then
        # Run both unit and integration tests
        if [ "$RUN_SLOW_TESTS" = false ]; then
            markers+=("not slow")
        fi
    elif [ "$RUN_UNIT_TESTS" = true ]; then
        markers+=("unit")
        if [ "$RUN_SLOW_TESTS" = false ]; then
            markers+=("not slow")
        fi
    elif [ "$RUN_INTEGRATION_TESTS" = true ]; then
        markers+=("integration")
        if [ "$RUN_SLOW_TESTS" = false ]; then
            markers+=("not slow")
        fi
    fi
    
    # Combine markers
    if [ ${#markers[@]} -gt 0 ]; then
        local marker_expr=$(IFS=" and "; echo "${markers[*]}")
        args+=(-m "$marker_expr")
    fi
    
    echo "${args[@]}"
}

run_unit_tests() {
    if [ "$RUN_UNIT_TESTS" = false ]; then
        return 0
    fi
    
    print_subheader "Running Unit Tests"
    
    local args=($(build_pytest_args))
    args+=(-m "unit")
    
    print_info "Command: pytest ${args[*]} tests/"
    
    if pytest "${args[@]}" tests/ 2>&1 | tee /tmp/unit_test_output; then
        print_success "Unit tests passed"
        return 0
    else
        print_error "Unit tests failed"
        return 1
    fi
}

run_integration_tests() {
    if [ "$RUN_INTEGRATION_TESTS" = false ]; then
        return 0
    fi
    
    print_subheader "Running Integration Tests"
    
    # Check if integration tests require special setup
    if [ -f "tests/integration/setup.sh" ]; then
        print_info "Running integration test setup..."
        bash tests/integration/setup.sh
    fi
    
    local args=($(build_pytest_args))
    args+=(-m "integration")
    
    print_info "Command: pytest ${args[*]} tests/"
    
    if pytest "${args[@]}" tests/ 2>&1 | tee /tmp/integration_test_output; then
        print_success "Integration tests passed"
        return 0
    else
        print_error "Integration tests failed"
        return 1
    fi
}

run_all_tests() {
    print_subheader "Running All Tests"
    
    local args=($(build_pytest_args))
    
    print_info "Command: pytest ${args[*]} tests/"
    
    # Run tests and capture detailed output
    if pytest "${args[@]}" tests/ --json-report --json-report-file=test_results.json 2>&1 | tee /tmp/test_output; then
        print_success "All tests passed"
        return 0
    else
        print_error "Some tests failed"
        return 1
    fi
}

# =============================================================================
# Analysis and Reporting Functions
# =============================================================================

analyze_test_results() {
    print_header "Test Results Analysis"
    
    # Parse pytest output for statistics
    if [ -f "/tmp/test_output" ]; then
        local output=$(cat /tmp/test_output)
        
        # Extract test counts using grep
        if echo "$output" | grep -q "passed"; then
            TESTS_PASSED=$(echo "$output" | grep -o '[0-9]\+ passed' | head -1 | grep -o '[0-9]\+' || echo "0")
        fi
        
        if echo "$output" | grep -q "failed"; then
            TESTS_FAILED=$(echo "$output" | grep -o '[0-9]\+ failed' | head -1 | grep -o '[0-9]\+' || echo "0")
        fi
        
        if echo "$output" | grep -q "skipped"; then
            TESTS_SKIPPED=$(echo "$output" | grep -o '[0-9]\+ skipped' | head -1 | grep -o '[0-9]\+' || echo "0")
        fi
        
        TESTS_RUN=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
    fi
    
    # Display results
    echo -e "${BLUE}Test Execution Summary:${NC}"
    echo -e "  Total Tests: $TESTS_RUN"
    echo -e "  ${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "  ${RED}Failed: $TESTS_FAILED${NC}"
    echo -e "  ${YELLOW}Skipped: $TESTS_SKIPPED${NC}"
    
    if [ $TESTS_RUN -gt 0 ]; then
        local pass_rate=$((TESTS_PASSED * 100 / TESTS_RUN))
        echo -e "  Success Rate: $pass_rate%"
    fi
}

analyze_coverage() {
    if [ "$GENERATE_COVERAGE" = false ]; then
        return 0
    fi
    
    print_subheader "Coverage Analysis"
    
    if [ -f ".coverage" ]; then
        # Generate coverage report
        coverage report --show-missing
        
        # Extract coverage percentage
        local coverage_pct=$(coverage report | tail -1 | awk '{print $NF}' | tr -d '%')
        
        echo -e "\n${BLUE}Coverage Summary:${NC}"
        if (( $(echo "$coverage_pct >= 80" | bc -l) )); then
            echo -e "  ${GREEN}Coverage: $coverage_pct%${NC} (Good)"
        elif (( $(echo "$coverage_pct >= 60" | bc -l) )); then
            echo -e "  ${YELLOW}Coverage: $coverage_pct%${NC} (Fair)"
        else
            echo -e "  ${RED}Coverage: $coverage_pct%${NC} (Needs Improvement)"
        fi
        
        if [ "$GENERATE_HTML_REPORT" = true ]; then
            print_info "HTML coverage report generated: htmlcov/index.html"
        fi
    else
        print_warning "No coverage data found"
    fi
}

check_test_performance() {
    print_subheader "Performance Analysis"
    
    if [ -f "/tmp/test_output" ]; then
        # Look for slow tests in output
        local slow_tests=$(grep -E "SLOW|slow|[0-9]+\.[0-9]+s" /tmp/test_output | head -5)
        
        if [ -n "$slow_tests" ]; then
            print_warning "Slow tests detected:"
            echo "$slow_tests" | while read -r line; do
                echo "    $line"
            done
            print_info "Consider optimizing slow tests or marking them with @pytest.mark.slow"
        fi
        
        # Check for memory issues or warnings
        local warnings=$(grep -c "warning\|WARNING" /tmp/test_output || echo "0")
        if [ "$warnings" -gt 0 ]; then
            print_warning "$warnings warning(s) found in test output"
            print_info "Review test output for details: /tmp/test_output"
        fi
    fi
}

generate_test_report() {
    print_header "Generating Test Report"
    
    local report_file="test_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
Dev Agents - Test Report
Generated: $(date)
=================================================

CONFIGURATION:
- Unit Tests: $RUN_UNIT_TESTS
- Integration Tests: $RUN_INTEGRATION_TESTS  
- Slow Tests: $RUN_SLOW_TESTS
- Coverage: $GENERATE_COVERAGE
- Parallel: $PARALLEL

RESULTS:
- Total Tests: $TESTS_RUN
- Passed: $TESTS_PASSED
- Failed: $TESTS_FAILED
- Skipped: $TESTS_SKIPPED

EOF
    
    if [ -f ".coverage" ]; then
        echo "COVERAGE:" >> "$report_file"
        coverage report >> "$report_file" 2>/dev/null || true
        echo "" >> "$report_file"
    fi
    
    if [ -f "/tmp/test_output" ]; then
        echo "DETAILED OUTPUT:" >> "$report_file"
        echo "================" >> "$report_file"
        cat /tmp/test_output >> "$report_file"
    fi
    
    print_info "Detailed test report saved: $report_file"
}

# =============================================================================
# Main Execution
# =============================================================================

print_summary() {
    print_header "Test Run Summary"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All tests passed successfully!${NC}"
        echo -e "Your code is ready for deployment."
    else
        echo -e "\n${RED}❌ Some tests failed.${NC}"
        echo -e "Please review the failures and fix the issues."
    fi
    
    echo -e "\n${BLUE}Files Generated:${NC}"
    
    if [ "$GENERATE_COVERAGE" = true ]; then
        echo -e "  📊 Coverage XML: coverage.xml"
        if [ "$GENERATE_HTML_REPORT" = true ]; then
            echo -e "  📊 Coverage HTML: htmlcov/index.html"
        fi
    fi
    
    if [ -f "test_results.json" ]; then
        echo -e "  📄 Test Results: test_results.json"
    fi
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "1. Review failed tests above"
        echo -e "2. Fix the issues"
        echo -e "3. Re-run tests: $0"
        echo -e "4. Check code quality: ./scripts/check-code-quality.sh"
    else
        echo -e "1. Review coverage report (if enabled)"
        echo -e "2. Run code quality checks: ./scripts/check-code-quality.sh"
        echo -e "3. Ready to commit!"
    fi
}

main() {
    echo -e "${BLUE}"
    cat << "EOF"
 _____         _     ____                             
|_   _|__  ___| |_  |  _ \ _   _ _ __  _ __   ___ _ __ 
  | |/ _ \/ __| __| | |_) | | | | '_ \| '_ \ / _ \ '__|
  | |  __/\__ \ |_  |  _ <| |_| | | | | | | |  __/ |   
  |_|\___||___/\__| |_| \_\\__,_|_| |_|_| |_|\___|_|   
  
    Comprehensive Test Suite
EOF
    echo -e "${NC}"
    
    parse_args "$@"
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Initialize temp file cleanup
    trap 'rm -f /tmp/*test_output /tmp/test_*.tmp' EXIT
    
    # Setup and run tests
    check_prerequisites
    setup_test_environment
    
    local test_result=0
    
    # Run tests based on configuration
    if [ "$RUN_UNIT_TESTS" = true ] && [ "$RUN_INTEGRATION_TESTS" = false ]; then
        run_unit_tests || test_result=1
    elif [ "$RUN_INTEGRATION_TESTS" = true ] && [ "$RUN_UNIT_TESTS" = false ]; then
        run_integration_tests || test_result=1
    else
        run_all_tests || test_result=1
    fi
    
    # Analysis and reporting
    analyze_test_results
    analyze_coverage
    check_test_performance
    generate_test_report
    print_summary
    
    exit $test_result
}

# Run main function with all arguments
main "$@"