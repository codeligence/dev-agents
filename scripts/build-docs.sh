#!/bin/bash
# Build and serve Dev Agents documentation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if mkdocs is installed
check_dependencies() {
    log_info "Checking documentation dependencies..."
    
    if ! command -v mkdocs &> /dev/null; then
        log_error "MkDocs not found. Installing documentation dependencies..."
        pip install -e .[docs]
    else
        log_success "MkDocs found"
    fi
    
    # Check if key plugins are available
    python -c "import mkdocs_material" 2>/dev/null || {
        log_warning "Material theme not found. Installing..."
        pip install -e .[docs]
    }
}

# Build the documentation
build_docs() {
    log_info "Building documentation..."
    
    # Clean previous build
    if [ -d "site" ]; then
        rm -rf site
        log_info "Cleaned previous build"
    fi
    
    # Set strict mode based on environment variable
    local strict_flag=""
    if [ "${STRICT_BUILD:-true}" = "true" ]; then
        strict_flag="--strict"
    fi
    
    # Build documentation
    mkdocs build $strict_flag
    
    if [ $? -eq 0 ]; then
        log_success "Documentation built successfully in 'site/' directory"
        
        # Show build statistics
        if [ -d "site" ]; then
            local size=$(du -sh site/ | cut -f1)
            local files=$(find site/ -type f | wc -l)
            log_info "Build statistics: $size total, $files files"
        fi
    else
        log_error "Documentation build failed"
        exit 1
    fi
}

# Serve documentation locally
serve_docs() {
    local host="${DOCS_HOST:-127.0.0.1}"
    local port="${DOCS_PORT:-8000}"
    
    log_info "Starting documentation server..."
    log_info "Documentation will be available at: http://$host:$port"
    log_info "Press Ctrl+C to stop the server"
    
    mkdocs serve --dev-addr="$host:$port"
}

# Deploy to GitHub Pages (if configured)
deploy_docs() {
    log_info "Deploying documentation to GitHub Pages..."
    
    # Check if gh-pages branch exists
    if git show-ref --verify --quiet refs/heads/gh-pages; then
        log_info "gh-pages branch found"
    else
        log_warning "gh-pages branch not found. Creating it..."
        git checkout --orphan gh-pages
        git rm -rf .
        git commit --allow-empty -m "Initial gh-pages commit"
        git checkout main
    fi
    
    mkdocs gh-deploy --force
    
    if [ $? -eq 0 ]; then
        log_success "Documentation deployed to GitHub Pages"
    else
        log_error "Documentation deployment failed"
        exit 1
    fi
}

# Validate documentation links and structure
validate_docs() {
    log_info "Validating documentation..."
    
    # Build first to generate the site
    mkdocs build --quiet
    
    # Check for broken internal links with linkchecker
    log_info "Checking for broken internal links..."
    if command -v linkchecker &> /dev/null; then
        linkchecker \
            --check-extern=0 \
            --ignore-url="^mailto:" \
            --ignore-url=".*#.*" \
            --no-warnings \
            --output=text \
            site/ > linkcheck.log 2>&1 || true
        
        if grep -q "ERROR" linkcheck.log; then
            log_error "Found broken links:"
            grep "ERROR" linkcheck.log
            rm -f linkcheck.log
            return 1
        else
            log_success "No broken links found"
        fi
        rm -f linkcheck.log
    else
        log_warning "linkchecker not found, skipping link validation"
    fi
    
    # Validate documentation structure
    log_info "Validating documentation structure..."
    python -c "
import os
import yaml
from pathlib import Path

# Load mkdocs.yml
with open('mkdocs.yml', 'r') as f:
    config = yaml.safe_load(f)

# Check navigation structure
nav = config.get('nav', [])
missing_files = []

def check_nav_files(nav_items, prefix='docs/'):
    for item in nav_items:
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, list):
                    check_nav_files(value, prefix)
                elif isinstance(value, str) and value.endswith('.md'):
                    file_path = Path(prefix + value)
                    if not file_path.exists():
                        missing_files.append(str(file_path))
        elif isinstance(item, str) and item.endswith('.md'):
            file_path = Path(prefix + item)
            if not file_path.exists():
                missing_files.append(str(file_path))

check_nav_files(nav)

if missing_files:
    print('Missing documentation files:')
    for file in missing_files:
        print(f'  - {file}')
    exit(1)
else:
    print('✅ All navigation files exist')
"
    
    if [ $? -eq 0 ]; then
        log_success "Documentation structure validation passed"
    else
        log_error "Documentation structure validation failed"
        return 1
    fi
    
    # Check API documentation coverage
    log_info "Validating API documentation coverage..."
    python -c "
import ast
from pathlib import Path

def get_public_classes_and_functions(file_path):
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        public_items = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
                public_items.append(f'class {node.name}')
            elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                public_items.append(f'function {node.name}')
        
        return public_items
    except:
        return []

# Find all Python files in src/
src_path = Path('src')
if src_path.exists():
    python_files = list(src_path.rglob('*.py'))
    python_files = [f for f in python_files if '__pycache__' not in str(f)]
    
    total_items = 0
    for py_file in python_files:
        items = get_public_classes_and_functions(py_file)
        total_items += len(items)
    
    print(f'Found {len(python_files)} Python files with {total_items} public items')
    
    # Check if API documentation exists
    api_docs = Path('docs/api')
    if api_docs.exists():
        api_files = list(api_docs.glob('*.md'))
        print(f'Found {len(api_files)} API documentation files')
        
        if len(api_files) >= 4:
            print('✅ API documentation structure looks complete')
        else:
            print('⚠️  API documentation may be incomplete')
    else:
        print('❌ No API documentation directory found')
else:
    print('No src/ directory found')
"
}

# Version management with mike
manage_versions() {
    local action="$1"
    local version="$2"
    local alias="$3"
    
    case "$action" in
        "list")
            log_info "Available documentation versions:"
            mike list
            ;;
        "deploy")
            if [ -z "$version" ]; then
                log_error "Version required for deploy command"
                echo "Usage: $0 version deploy <version> [alias]"
                exit 1
            fi
            
            log_info "Deploying documentation version: $version"
            if [ -n "$alias" ]; then
                mike deploy --push --update-aliases "$version" "$alias"
                log_success "Deployed version $version with alias $alias"
            else
                mike deploy --push "$version"
                log_success "Deployed version $version"
            fi
            ;;
        "delete")
            if [ -z "$version" ]; then
                log_error "Version required for delete command"
                echo "Usage: $0 version delete <version>"
                exit 1
            fi
            
            log_info "Deleting documentation version: $version"
            mike delete --push "$version"
            log_success "Deleted version $version"
            ;;
        "set-default")
            if [ -z "$version" ]; then
                log_error "Version required for set-default command"
                echo "Usage: $0 version set-default <version>"
                exit 1
            fi
            
            log_info "Setting default version: $version"
            mike set-default --push "$version"
            log_success "Set $version as default version"
            ;;
        *)
            log_error "Unknown version command: $action"
            echo "Available version commands: list, deploy, delete, set-default"
            exit 1
            ;;
    esac
}

# Generate comprehensive documentation report
generate_report() {
    log_info "Generating documentation report..."
    
    local report_file="docs_report_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$report_file" << EOF
# Documentation Report

Generated: $(date)

## Build Information

- MkDocs Version: $(mkdocs --version)
- Python Version: $(python --version)
- Working Directory: $(pwd)

## Documentation Statistics

EOF
    
    # Count files
    local total_md=$(find docs/ -name "*.md" | wc -l)
    local api_md=$(find docs/api/ -name "*.md" 2>/dev/null | wc -l || echo "0")
    local total_images=$(find docs/ -name "*.png" -o -name "*.jpg" -o -name "*.gif" -o -name "*.svg" | wc -l)
    
    cat >> "$report_file" << EOF
- Total Markdown files: $total_md
- API documentation files: $api_md
- Image files: $total_images
- Site directory size: $(du -sh site/ 2>/dev/null | cut -f1 || echo "Not built")

## Navigation Structure

EOF
    
    # Add navigation info
    python -c "
import yaml
with open('mkdocs.yml', 'r') as f:
    config = yaml.safe_load(f)
nav = config.get('nav', [])
def print_nav(items, level=0):
    for item in items:
        indent = '  ' * level
        if isinstance(item, dict):
            for key, value in item.items():
                print(f'{indent}- {key}')
                if isinstance(value, list):
                    print_nav(value, level + 1)
                else:
                    print(f'{indent}  - {value}')
        else:
            print(f'{indent}- {item}')
print_nav(nav)
" >> "$report_file"
    
    echo "" >> "$report_file"
    echo "## Plugin Configuration" >> "$report_file"
    echo "" >> "$report_file"
    
    # Add plugin info
    python -c "
import yaml
with open('mkdocs.yml', 'r') as f:
    config = yaml.safe_load(f)
plugins = config.get('plugins', [])
for plugin in plugins:
    if isinstance(plugin, dict):
        for name, settings in plugin.items():
            print(f'- {name}: Configured with settings')
    else:
        print(f'- {plugin}: Default configuration')
" >> "$report_file"
    
    log_success "Documentation report generated: $report_file"
}

# Show help
show_help() {
    echo "Dev Agents Documentation Builder"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build         Build documentation (default)"
    echo "  serve         Build and serve documentation locally"
    echo "  deploy        Deploy documentation to GitHub Pages"
    echo "  validate      Validate documentation structure and links"
    echo "  clean         Clean build artifacts"
    echo "  report        Generate comprehensive documentation report"
    echo "  version       Manage documentation versions with mike"
    echo "  help          Show this help message"
    echo ""
    echo "Version Management:"
    echo "  version list                    List all available versions"
    echo "  version deploy <ver> [alias]    Deploy a new version"
    echo "  version delete <version>        Delete a version"
    echo "  version set-default <version>   Set default version"
    echo ""
    echo "Examples:"
    echo "  $0 build                        # Build documentation"
    echo "  $0 serve                        # Serve locally for development"
    echo "  $0 validate                     # Check links and structure"
    echo "  $0 version deploy 1.0.0 latest  # Deploy version with alias"
    echo "  $0 version list                 # Show all versions"
    echo "  $0 report                       # Generate documentation report"
    echo ""
    echo "Environment Variables:"
    echo "  DOCS_PORT     Port for local server (default: 8000)"
    echo "  DOCS_HOST     Host for local server (default: 127.0.0.1)"
    echo "  STRICT_BUILD  Enable strict mode (default: true)"
}

# Clean build artifacts
clean_docs() {
    log_info "Cleaning documentation build artifacts..."
    
    if [ -d "site" ]; then
        rm -rf site
        log_success "Removed 'site' directory"
    fi
    
    # Clean any temporary files
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Clean completed"
}

# Main script logic
main() {
    local command="${1:-build}"
    
    # Change to script directory
    cd "$(dirname "$0")/.."
    
    case "$command" in
        "build")
            check_dependencies
            build_docs
            ;;
        "serve")
            check_dependencies
            serve_docs
            ;;
        "deploy")
            check_dependencies
            deploy_docs
            ;;
        "validate")
            check_dependencies
            validate_docs
            ;;
        "clean")
            clean_docs
            ;;
        "report")
            check_dependencies
            generate_report
            ;;
        "version")
            check_dependencies
            shift  # Remove 'version' from arguments
            manage_versions "$@"
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"