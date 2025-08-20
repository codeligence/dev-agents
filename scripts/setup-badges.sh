#!/bin/bash

# Badge Setup Script for dev-agents
# This script helps configure external services for project badges

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project information
PROJECT_OWNER="${GITHUB_REPOSITORY_OWNER:-codeligence}"
PROJECT_NAME="${GITHUB_REPOSITORY##*/}"
REPO_URL="https://github.com/${PROJECT_OWNER}/${PROJECT_NAME}"

echo -e "${BLUE}🏷️  Badge Setup for ${PROJECT_NAME}${NC}"
echo "========================================"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check if GitHub CLI is installed
if command -v gh &> /dev/null; then
    print_status "GitHub CLI (gh) is installed"
else
    print_error "GitHub CLI (gh) is not installed. Please install it from https://cli.github.com/"
    exit 1
fi

# Check if logged into GitHub
if gh auth status &> /dev/null; then
    print_status "Authenticated with GitHub CLI"
else
    print_error "Not authenticated with GitHub CLI. Run 'gh auth login' first"
    exit 1
fi

echo ""
echo -e "${BLUE}Current Badge Status:${NC}"
echo "===================="

# Check existing secrets
echo "Checking GitHub repository secrets..."

# Function to check if secret exists
check_secret() {
    local secret_name=$1
    local description=$2
    local setup_url=$3
    
    if gh secret list | grep -q "^${secret_name}"; then
        print_status "${secret_name}: Configured"
        return 0
    else
        print_warning "${secret_name}: Not configured - ${description}"
        echo "   Setup: ${setup_url}"
        return 1
    fi
}

# Check required secrets for badges
CODECOV_CONFIGURED=false
if check_secret "CODECOV_TOKEN" "Required for Codecov coverage badge" "https://app.codecov.io/gh/${PROJECT_OWNER}/${PROJECT_NAME}"; then
    CODECOV_CONFIGURED=true
fi

DOCKER_CONFIGURED=false
if check_secret "DOCKER_USERNAME" "Required for Docker Hub badges" "https://hub.docker.com/settings/security"; then
    if check_secret "DOCKER_PASSWORD" "Docker Hub access token" "https://hub.docker.com/settings/security"; then
        DOCKER_CONFIGURED=true
    fi
fi

echo ""
echo -e "${BLUE}Badge Service Setup Instructions:${NC}"
echo "================================="

# Codecov setup
if [ "$CODECOV_CONFIGURED" = false ]; then
    echo ""
    echo -e "${YELLOW}📊 Codecov Coverage Badge Setup:${NC}"
    echo "1. Go to https://app.codecov.io/"
    echo "2. Sign in with GitHub and add your repository"
    echo "3. Get your repository token from the settings"
    echo "4. Add it as a GitHub secret:"
    echo "   gh secret set CODECOV_TOKEN --body 'your-codecov-token-here'"
fi

# CodeFactor setup
echo ""
echo -e "${YELLOW}🔍 CodeFactor Code Quality Setup:${NC}"
echo "1. Go to https://www.codefactor.io/"
echo "2. Sign in with GitHub"
echo "3. Add your repository: ${REPO_URL}"
echo "4. The badge will automatically work once added"
echo "   Badge URL: https://img.shields.io/codefactor/grade/github/${PROJECT_OWNER}/${PROJECT_NAME}/main"

# Code Climate setup  
echo ""
echo -e "${YELLOW}🌡️  Code Climate Maintainability Setup:${NC}"
echo "1. Go to https://codeclimate.com/"
echo "2. Sign in with GitHub"
echo "3. Add your repository: ${REPO_URL}"
echo "4. Get your repository ID from the badge settings"
echo "5. Update README.md with the correct badge ID"
echo "   Current: https://api.codeclimate.com/v1/badges/12345/maintainability"

# Snyk setup
echo ""
echo -e "${YELLOW}🛡️  Snyk Security Badge Setup:${NC}"
echo "1. Go to https://snyk.io/"
echo "2. Sign in with GitHub"
echo "3. Add your repository: ${REPO_URL}"
echo "4. The badge will automatically work once added"
echo "   Badge URL: https://snyk.io/test/github/${PROJECT_OWNER}/${PROJECT_NAME}/badge.svg"

# Libraries.io setup
echo ""
echo -e "${YELLOW}📚 Libraries.io Dependency Monitoring Setup:${NC}"
echo "1. Go to https://libraries.io/"
echo "2. Search for your repository or add it"
echo "3. The badge works automatically for public repositories"
echo "   Badge URL: https://img.shields.io/librariesio/github/${PROJECT_OWNER}/${PROJECT_NAME}"

# OpenSSF Scorecard
echo ""
echo -e "${YELLOW}🏆 OpenSSF Security Scorecard Setup:${NC}"
echo "1. The OpenSSF Scorecard runs automatically for public repositories"
echo "2. Enable security policies in your repository:"
echo "   - Add SECURITY.md (✅ already present)"
echo "   - Configure branch protection rules"
echo "   - Enable security advisories"
echo "3. Badge URL: https://api.securityscorecards.dev/projects/github.com/${PROJECT_OWNER}/${PROJECT_NAME}/badge"

echo ""
echo -e "${BLUE}Automated Badge Updates:${NC}"
echo "========================"

print_info "Badge Update Workflow: .github/workflows/badge-update.yml"
echo "- Runs daily at 6:00 AM UTC"
echo "- Validates all badge URLs"
echo "- Updates version references"
echo "- Can be triggered manually: gh workflow run badge-update.yml"

echo ""
echo -e "${BLUE}Testing Badge URLs:${NC}"
echo "==================="

# Function to test badge URL
test_badge() {
    local name=$1
    local url=$2
    
    echo -n "Testing ${name}... "
    if curl -s -I "$url" | grep -q "200 OK\|302 Found\|301 Moved"; then
        print_status "OK"
    else
        print_error "Failed"
    fi
}

# Test some key badges
test_badge "CI Pipeline" "https://img.shields.io/github/actions/workflow/status/${PROJECT_OWNER}/${PROJECT_NAME}/ci.yml?branch=main"
test_badge "GitHub Release" "https://img.shields.io/github/v/release/${PROJECT_OWNER}/${PROJECT_NAME}"
test_badge "PyPI Version" "https://img.shields.io/pypi/v/dev-agents"
test_badge "Python Version" "https://img.shields.io/pypi/pyversions/dev-agents"

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "============"
echo "1. Set up external services (Codecov, CodeFactor, etc.)"
echo "2. Configure repository secrets for services that require them"
echo "3. Update Code Climate badge ID in README.md with your actual repository ID"
echo "4. Run the badge update workflow to validate everything:"
echo "   gh workflow run badge-update.yml"
echo "5. Check badge status report in workflow artifacts"

if [ "$CODECOV_CONFIGURED" = true ]; then
    echo ""
    print_status "Badge setup is mostly complete! 🎉"
else
    echo ""
    print_warning "Some badges require additional setup. See instructions above."
fi

echo ""
echo -e "${GREEN}Badge setup script completed!${NC}"