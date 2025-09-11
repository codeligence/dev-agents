#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[ENTRYPOINT]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[ENTRYPOINT]${NC} $1"
}

# Auto-detect and adjust user permissions for mounted volumes
adjust_user_permissions() {
    # Check if /code directory is mounted and has different ownership
    if [ -d /code ] && [ "$(ls -A /code 2>/dev/null)" ]; then
        # Get the ownership of the /code directory
        CODE_USER_ID=$(stat -c '%u' /code 2>/dev/null || echo "1000")
        CODE_GROUP_ID=$(stat -c '%g' /code 2>/dev/null || echo "1000")

        # Get current appuser IDs
        CURRENT_USER_ID=$(id -u appuser)
        CURRENT_GROUP_ID=$(id -g appuser)

        # Only adjust if they're different
        if [ "$CODE_USER_ID" != "$CURRENT_USER_ID" ] || [ "$CODE_GROUP_ID" != "$CURRENT_GROUP_ID" ]; then
            print_info "Adjusting container user to match host directory ownership (${CODE_USER_ID}:${CODE_GROUP_ID})"

            # Update group first
            if [ "$CODE_GROUP_ID" != "$CURRENT_GROUP_ID" ]; then
                groupmod -g "$CODE_GROUP_ID" appuser 2>/dev/null || true
            fi

            # Update user
            if [ "$CODE_USER_ID" != "$CURRENT_USER_ID" ]; then
                usermod -u "$CODE_USER_ID" appuser 2>/dev/null || true
            fi

            # Fix ownership of user home and app directories
            chown -R appuser:appuser /home/appuser 2>/dev/null || true
            chown -R appuser:appuser /app 2>/dev/null || true

            print_info "User permissions adjusted successfully"
        else
            print_info "Container user already matches host directory ownership"
        fi
    else
        print_info "No /code volume mounted or directory empty, using default user permissions"
    fi

    # Ensure /data directory has proper permissions if it exists and is mounted
    if [ -d /data ]; then
        chown -R appuser:appuser /data 2>/dev/null || true
    fi
}

# Main execution
print_info "Starting Dev Agents container..."

# Adjust permissions before switching to appuser
adjust_user_permissions

git config --system --add safe.directory /code

# Always use the main Python script, passing any arguments to it
print_info "Executing: python -m entrypoints.main $*"
exec gosu appuser python -m entrypoints.main "$@"
