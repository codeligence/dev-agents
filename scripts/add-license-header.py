# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.

import os


def add_license_header():
    header = """\
# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.
"""
    current_dir = os.getcwd()
    target_dirs = ['src', 'tests']

    for target in target_dirs:
        target_path = os.path.join(current_dir, target)
        if not os.path.exists(target_path):
            print(f"Directory {target_path} does not exist. Skipping.")
            continue

        for dirpath, _dirnames, filenames in os.walk(target_path):
            for filename in filenames:
                if filename.endswith('.py'):
                    file_path = os.path.join(dirpath, filename)
                    with open(file_path, encoding='utf-8') as f:
                        content = f.read()

                    # Check if the header is already present
                    if 'GNU Affero General Public License' in content:
                        print(f"Skipping {file_path}: Header already present.")
                        continue

                    # Prepend the header
                    new_content = header + '\n\n' + content.strip()

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)

                    print(f"Added header to {file_path}")

if __name__ == "__main__":
    add_license_header()
