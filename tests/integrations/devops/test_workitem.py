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


from pathlib import Path
import json
import unittest

from integrations.devops.models import Person, WorkItem


class TestWorkItem(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        """Load the mock data before each test."""
        mock_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "integrations"
            / "devops"
            / "mocks"
            / "devops_workitem.json"
        )
        with mock_path.open() as f:
            self.response_json = json.load(f)
        self.workitem = WorkItem(self.response_json)

    def test_get_system_team_project(self):
        """Test retrieving the team project."""
        self.assertEqual(self.workitem.get_system_team_project(), "acmecorp.com")

    def test_get_system_state(self):
        """Test retrieving the state."""
        self.assertEqual(self.workitem.get_system_state(), "Ready for Review")

    def test_get_system_reason(self):
        """Test retrieving the reason."""
        self.assertEqual(
            self.workitem.get_system_reason(), "Updated for general review"
        )

    def test_get_system_created_date(self):
        """Test retrieving the creation date."""
        self.assertEqual(
            self.workitem.get_system_created_date(), "2025-04-16T14:23:16.797Z"
        )

    def test_get_system_created_by(self):
        """Test retrieving the creator."""
        person = self.workitem.get_system_created_by()
        self.assertIsInstance(person, Person)
        self.assertEqual(person.display_name, "Jane Doe")
        self.assertEqual(person.unique_name, "jane.doe@acmecorp.com")
        self.assertEqual(person.format(), "Jane Doe <jane.doe@acmecorp.com>")

    def test_get_system_changed_date(self):
        """Test retrieving the last changed date."""
        self.assertEqual(
            self.workitem.get_system_changed_date(), "2025-04-28T04:17:00.723Z"
        )

    def test_get_system_changed_by(self):
        """Test retrieving who last changed the item."""
        person = self.workitem.get_system_changed_by()
        self.assertIsInstance(person, Person)
        self.assertEqual(person.display_name, "Jane Doe")
        self.assertEqual(person.unique_name, "jane.doe@acmecorp.com")
        self.assertEqual(person.format(), "Jane Doe <jane.doe@acmecorp.com>")

    def test_get_system_title(self):
        """Test retrieving the title."""
        self.assertEqual(
            self.workitem.get_system_title(),
            "General Task Issue: Minor UI Inconsistency",
        )

    def test_get_custom_application(self):
        """Test retrieving the custom application field."""
        self.assertEqual(self.workitem.get_custom_application(), "Generic App")

    def test_get_custom_dev(self):
        """Test retrieving the custom dev field."""
        person = self.workitem.get_custom_dev()
        self.assertIsInstance(person, Person)
        self.assertEqual(person.display_name, "John Doe")
        self.assertEqual(person.unique_name, "john.doe@acmecorp.com")
        self.assertEqual(person.format(), "John Doe <john.doe@acmecorp.com>")

    def test_get_system_description(self):
        """Test retrieving the description."""
        expected = '<div><img src="https://example.com/assets/sample-image.png" alt="Generic Image"><br></div><div><p>This issue describes a minor inconsistency in the user interface. The text label or icon might not appear as expected in some conditions.</p></div><div><p>Please refer to the internal documentation for more details.</p></div>'
        self.assertEqual(self.workitem.get_system_description(), expected)

    def test_get_system_description_plain(self):
        """Test retrieving the plain text description with HTML removed."""
        expected = "This issue describes a minor inconsistency in the user interface. The text label or icon might not appear as expected in some conditions. Please refer to the internal documentation for more details."
        self.assertEqual(self.workitem.get_system_description_plain(), expected)

    def test_get_relation_urls(self):
        """Test retrieving relation URLs."""
        urls = self.workitem.get_relation_urls()
        self.assertEqual(len(urls), 2)
        self.assertIn("https://example.com/apis/wit/workItems/10002", urls)
        self.assertIn(
            "vstfs:///Git/PullRequestId/EXAMPLE-GUID-PR/NEW-PR-GUID/54321", urls
        )

    def test_get_pull_request_ids(self):
        """Test retrieving pull request IDs."""
        pull_request_ids = self.workitem.get_pull_request_ids()
        self.assertEqual(len(pull_request_ids), 1)
        self.assertEqual(pull_request_ids[0], "54321")

    def test_get_commit_hashes(self):
        """Test retrieving commit hashes."""
        # The mock doesn't have commit relations, should return an empty list
        commit_hashes = self.workitem.get_commit_hashes()
        self.assertEqual(len(commit_hashes), 0)

    def test_get_description_images(self):
        """Test extracting image URLs from description."""
        image_urls = self.workitem.get_description_images()
        self.assertEqual(len(image_urls), 1)
        self.assertEqual(image_urls[0], "https://example.com/assets/sample-image.png")

    def test_get_composed_work_item_info(self):
        """Test composing all work item information into a string."""
        info = self.workitem.get_composed_work_item_info()

        # Check that key information is included in the composed string
        self.assertIn("Title: General Task Issue: Minor UI Inconsistency", info)
        self.assertIn("Team Project: acmecorp.com", info)
        self.assertIn("State: Ready for Review", info)
        self.assertIn("Created By: Jane Doe <jane.doe@acmecorp.com>", info)
        self.assertIn("Application: Generic App", info)


if __name__ == "__main__":
    unittest.main()
