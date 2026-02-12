"""Tests for submission page operations."""

import pytest

from blue_railroad_import.submission import (
    get_submission_page_title,
    update_submission_field,
    update_submission_cid,
)
from blue_railroad_import.wiki_client import DryRunClient, SaveResult


class TestGetSubmissionPageTitle:
    def test_returns_correct_title(self):
        assert get_submission_page_title(1) == "Blue Railroad Submission/1"
        assert get_submission_page_title(42) == "Blue Railroad Submission/42"


class TestUpdateSubmissionField:
    def test_adds_new_field(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|video=test.mp4
|block_height=24207967
}}"""
        updated, changed = update_submission_field(wikitext, 'ipfs_cid', 'bafytest123')

        assert changed is True
        assert '|ipfs_cid=bafytest123' in updated
        assert '|exercise=Blue Railroad Train (Squats)' in updated

    def test_updates_existing_field(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|ipfs_cid=oldcid
|block_height=24207967
}}"""
        updated, changed = update_submission_field(wikitext, 'ipfs_cid', 'newcid')

        assert changed is True
        assert '|ipfs_cid=newcid' in updated
        assert 'oldcid' not in updated

    def test_no_change_when_value_same(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|ipfs_cid=samecid
|block_height=24207967
}}"""
        updated, changed = update_submission_field(wikitext, 'ipfs_cid', 'samecid')

        assert changed is False
        assert updated == wikitext

    def test_raises_when_template_not_found(self):
        wikitext = "This page has no template"

        with pytest.raises(ValueError, match="Could not find"):
            update_submission_field(wikitext, 'ipfs_cid', 'test')

    def test_preserves_other_content(self):
        wikitext = """Some text before

{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|video=test.mp4
}}
{{Blue Railroad Participant
|wallet=0x123
}}

Some text after"""
        updated, changed = update_submission_field(wikitext, 'ipfs_cid', 'bafytest')

        assert changed is True
        assert 'Some text before' in updated
        assert 'Some text after' in updated
        assert '{{Blue Railroad Participant' in updated
        assert '|wallet=0x123' in updated


class TestUpdateSubmissionCid:
    def test_updates_existing_page(self):
        existing_content = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|video=test.mp4
|block_height=24207967
}}"""
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/1': existing_content
        })

        result = update_submission_cid(client, 1, 'bafynewtestcid')

        assert result.action in ('updated', 'created')  # DryRunClient returns action
        assert len(client.saved_pages) == 1
        title, content, summary = client.saved_pages[0]
        assert title == 'Blue Railroad Submission/1'
        assert '|ipfs_cid=bafynewtestcid' in content
        assert 'bafynewtestcid' in summary

    def test_returns_error_for_missing_page(self):
        client = DryRunClient(existing_pages={})

        result = update_submission_cid(client, 999, 'bafytest')

        assert result.action == 'error'
        assert 'not found' in result.message.lower()

    def test_returns_unchanged_when_cid_already_set(self):
        existing_content = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|ipfs_cid=bafyalreadyset
}}"""
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/1': existing_content
        })

        result = update_submission_cid(client, 1, 'bafyalreadyset')

        assert result.action == 'unchanged'
        assert len(client.saved_pages) == 0  # No save attempted
