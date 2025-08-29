#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}\n"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_version() {
    echo -e "${BOLD}$1${NC}"
}

# Function to get current version from pyproject.toml
get_current_version() {
    if command -v python3 &> /dev/null; then
        python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || \
        python3 -c "import toml; print(toml.load('pyproject.toml')['project']['version'])" 2>/dev/null || \
        grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/' || echo "unknown"
    else
        grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/' || echo "unknown"
    fi
}

# Function to calculate next version
calculate_next_version() {
    local current_version="$1"
    local bump_type="$2"
    
    IFS='.' read -ra VERSION_PARTS <<< "$current_version"
    local major=${VERSION_PARTS[0]:-0}
    local minor=${VERSION_PARTS[1]:-0}
    local patch=${VERSION_PARTS[2]:-0}
    
    case $bump_type in
        "patch")
            echo "$major.$minor.$((patch + 1))"
            ;;
        "minor")
            echo "$major.$((minor + 1)).0"
            ;;
        "major")
            echo "$((major + 1)).0.0"
            ;;
        *)
            echo "$current_version"
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if we're in a git repository
    if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi
    
    # Check if commitizen is installed
    if ! command -v cz &> /dev/null; then
        print_error "Commitizen is not installed. Install with: pip install commitizen"
        exit 1
    fi
    
    # Check if pyproject.toml exists
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found in current directory"
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

# Check git status
check_git_status() {
    print_info "Checking git status..."
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        print_warning "You have uncommitted changes:"
        git status --porcelain
        echo
        read -p "Continue with version bump anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Version bump cancelled"
            exit 0
        fi
    fi
    
    print_success "Git status clean or user confirmed to proceed"
}

# Main function
main() {
    print_header "Dev Agents Version Bump Tool"
    
    # Run checks
    check_prerequisites
    check_git_status
    
    # Get current version
    CURRENT_VERSION=$(get_current_version)
    print_info "Current version: $(print_version "$CURRENT_VERSION")"
    
    # Show menu
    echo
    echo "Select version bump type:"
    echo
    echo "  ${BOLD}1. Patch${NC} (${CURRENT_VERSION} → $(calculate_next_version "$CURRENT_VERSION" "patch"))  - Bug fixes, small improvements"
    echo "  ${BOLD}2. Minor${NC} (${CURRENT_VERSION} → $(calculate_next_version "$CURRENT_VERSION" "minor"))  - New features, backward compatible"
    echo "  ${BOLD}3. Major${NC} (${CURRENT_VERSION} → $(calculate_next_version "$CURRENT_VERSION" "major"))  - Breaking changes, major updates"
    echo "  ${BOLD}4. Exit${NC}   - Cancel version bump"
    echo
    
    # Get user choice
    while true; do
        read -p "Choose option (1-4): " -n 1 -r
        echo
        case $REPLY in
            1)
                BUMP_TYPE="patch"
                NEW_VERSION=$(calculate_next_version "$CURRENT_VERSION" "patch")
                break
                ;;
            2)
                BUMP_TYPE="minor"  
                NEW_VERSION=$(calculate_next_version "$CURRENT_VERSION" "minor")
                break
                ;;
            3)
                BUMP_TYPE="major"
                NEW_VERSION=$(calculate_next_version "$CURRENT_VERSION" "major")
                break
                ;;
            4)
                print_info "Version bump cancelled"
                exit 0
                ;;
            *)
                print_error "Invalid option. Please choose 1-4."
                ;;
        esac
    done
    
    # Confirm the bump
    echo
    print_warning "About to bump version:"
    echo "  Current: $(print_version "$CURRENT_VERSION")"
    echo "  New:     $(print_version "$NEW_VERSION")"
    echo "  Type:    $(print_version "$BUMP_TYPE")"
    echo
    print_info "This will:"
    echo "  - Update version in pyproject.toml"
    echo "  - Update version in src/__init__.py"
    echo "  - Update version in docs/index.md"  
    echo "  - Update version in COMPLIANCE_SUMMARY.md"
    echo "  - Create a git commit with conventional format"
    echo "  - Create a git tag (v$NEW_VERSION)"
    echo "  - Run pre/post bump hooks (quality checks, docs generation)"
    echo
    
    read -p "Proceed with version bump? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Version bump cancelled"
        exit 0
    fi
    
    # Execute the bump
    print_header "Executing Version Bump"
    print_info "Running: cz bump --increment $BUMP_TYPE"
    
    if cz bump --increment "$BUMP_TYPE"; then
        print_success "Version bump completed successfully!"
        print_success "New version: $(print_version "$NEW_VERSION")"
        print_success "Git tag created: $(print_version "v$NEW_VERSION")"
        
        # Show what was updated
        echo
        print_info "Updated files:"
        git show --name-only --format="" HEAD | while read -r file; do
            if [ -n "$file" ]; then
                echo "  - $file"
            fi
        done
        
        echo
        print_info "Next steps:"
        echo "  - Review the changes: git show"
        echo "  - Push to remote: git push && git push --tags"
        echo "  - Create a release on GitHub/GitLab if needed"
        
    else
        print_error "Version bump failed!"
        print_info "Check the output above for details"
        exit 1
    fi
}

# Run main function
main "$@"