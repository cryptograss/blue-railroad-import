"""Tests for submission page operations."""

import pytest

from blue_railroad_import.submission import (
    get_submission_page_title,
    update_submission_field,
    update_submission_cid,
    parse_submission_content,
    fetch_submission,
    fetch_all_submissions,
    match_tokens_to_submissions,
    get_submission_id_for_token,
    update_submission_token_ids,
)
from blue_railroad_import.models import Submission, Token
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


class TestParseSubmissionContent:
    def test_parses_basic_submission(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|video=File:BlueRailroad-test.mp4
|block_height=24207967
|status=Pending
}}"""
        sub = parse_submission_content(wikitext, 1)

        assert sub.id == 1
        assert sub.exercise == 'Blue Railroad Train (Squats)'
        assert sub.video == 'File:BlueRailroad-test.mp4'
        assert sub.block_height == 24207967
        assert sub.status == 'Pending'
        assert sub.ipfs_cid is None
        assert sub.token_ids == []

    def test_parses_submission_with_cid_and_tokens(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Nine Pound Hammer (Pushups)
|video=File:test.mp4
|block_height=24000000
|status=Minted
|ipfs_cid=QmTest123abc
|token_ids=5,6,7
}}"""
        sub = parse_submission_content(wikitext, 3)

        assert sub.id == 3
        assert sub.ipfs_cid == 'QmTest123abc'
        assert sub.token_ids == [5, 6, 7]
        assert sub.status == 'Minted'
        assert sub.is_minted is True

    def test_parses_participants_wallet_only(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
}}
{{Blue Railroad Participant
|wallet=0xabc123
}}
{{Blue Railroad Participant
|wallet=0xdef456
}}"""
        sub = parse_submission_content(wikitext, 1)

        assert sub.participants == ['0xabc123', '0xdef456']

    def test_parses_participants_name_wallet_format(self):
        wikitext = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
}}
{{Blue Railroad Participant
|name=Alice
|wallet=0xalice
}}"""
        sub = parse_submission_content(wikitext, 1)

        assert sub.participants == ['0xalice']

    def test_defaults_for_missing_fields(self):
        wikitext = """{{Blue Railroad Submission
}}"""
        sub = parse_submission_content(wikitext, 99)

        assert sub.id == 99
        assert sub.exercise == ''
        assert sub.video is None
        assert sub.block_height is None
        assert sub.status == 'Pending'
        assert sub.has_cid is False


class TestFetchSubmission:
    def test_fetches_existing_submission(self):
        content = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|ipfs_cid=QmTestCid
}}"""
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/5': content
        })

        sub = fetch_submission(client, 5)

        assert sub is not None
        assert sub.id == 5
        assert sub.exercise == 'Blue Railroad Train (Squats)'
        assert sub.ipfs_cid == 'QmTestCid'

    def test_returns_none_for_missing_submission(self):
        client = DryRunClient(existing_pages={})

        sub = fetch_submission(client, 999)

        assert sub is None


class TestFetchAllSubmissions:
    def test_fetches_multiple_submissions(self):
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/1': '{{Blue Railroad Submission\n|exercise=Ex1\n}}',
            'Blue Railroad Submission/3': '{{Blue Railroad Submission\n|exercise=Ex3\n}}',
            'Blue Railroad Submission/5': '{{Blue Railroad Submission\n|exercise=Ex5\n}}',
        })

        subs = fetch_all_submissions(client, max_id=5)

        assert len(subs) == 3
        assert subs[0].id == 1
        assert subs[1].id == 3
        assert subs[2].id == 5

    def test_returns_empty_when_no_submissions(self):
        client = DryRunClient(existing_pages={})

        subs = fetch_all_submissions(client, max_id=5)

        assert subs == []


class TestMatchTokensToSubmissions:
    def test_matches_token_to_submission_by_cid(self):
        tokens = {
            '5': Token(
                token_id='5',
                source_key='blueRailroadV2s',
                owner='0x123',
                owner_display='alice.eth',
                blockheight=24000000,
                # This video_hash produces a specific CID
                video_hash='0x' + 'ab' * 32,
            ),
        }
        # The token's ipfs_cid will be 'QmZtnFaddFtzGNT8BxdHVbQrhSFdq1pWxud5z4fA4kxfDt'
        submissions = [
            Submission(id=1, ipfs_cid='QmOtherCid'),
            Submission(id=2, ipfs_cid='QmZtnFaddFtzGNT8BxdHVbQrhSFdq1pWxud5z4fA4kxfDt'),
        ]

        result = match_tokens_to_submissions(tokens, submissions)

        assert result == {2: [5]}

    def test_matches_multiple_tokens_to_same_submission(self):
        # Same video_hash = same CID = same submission
        tokens = {
            '5': Token(
                token_id='5',
                source_key='blueRailroadV2s',
                owner='0x123',
                owner_display='alice.eth',
                blockheight=24000000,
                video_hash='0x' + 'ab' * 32,
            ),
            '6': Token(
                token_id='6',
                source_key='blueRailroadV2s',
                owner='0x456',
                owner_display='bob.eth',
                blockheight=24000000,
                video_hash='0x' + 'ab' * 32,  # Same hash
            ),
        }
        submissions = [
            Submission(id=3, ipfs_cid='QmZtnFaddFtzGNT8BxdHVbQrhSFdq1pWxud5z4fA4kxfDt'),
        ]

        result = match_tokens_to_submissions(tokens, submissions)

        assert 3 in result
        assert sorted(result[3]) == [5, 6]

    def test_no_match_when_cid_missing(self):
        tokens = {
            '1': Token(
                token_id='1',
                source_key='blueRailroadV2s',
                owner='0x123',
                owner_display='alice.eth',
                blockheight=24000000,
                video_hash='0x' + '00' * 32,  # Zero hash = no CID
            ),
        }
        submissions = [
            Submission(id=1, ipfs_cid='QmSomeCid'),
        ]

        result = match_tokens_to_submissions(tokens, submissions)

        assert result == {}

    def test_no_match_when_submission_has_no_cid(self):
        tokens = {
            '1': Token(
                token_id='1',
                source_key='blueRailroadV2s',
                owner='0x123',
                owner_display='alice.eth',
                blockheight=24000000,
                video_hash='0x' + 'ab' * 32,
            ),
        }
        submissions = [
            Submission(id=1, ipfs_cid=None),
        ]

        result = match_tokens_to_submissions(tokens, submissions)

        assert result == {}


class TestGetSubmissionIdForToken:
    def test_finds_matching_submission(self):
        token = Token(
            token_id='5',
            source_key='blueRailroadV2s',
            owner='0x123',
            owner_display='alice.eth',
            blockheight=24000000,
            video_hash='0x' + 'ab' * 32,
        )
        submissions = [
            Submission(id=1, ipfs_cid='QmOther'),
            Submission(id=2, ipfs_cid='QmZtnFaddFtzGNT8BxdHVbQrhSFdq1pWxud5z4fA4kxfDt'),
        ]

        result = get_submission_id_for_token(token, submissions)

        assert result == 2

    def test_returns_none_when_no_match(self):
        token = Token(
            token_id='5',
            source_key='blueRailroadV2s',
            owner='0x123',
            owner_display='alice.eth',
            blockheight=24000000,
            video_hash='0x' + 'ab' * 32,
        )
        submissions = [
            Submission(id=1, ipfs_cid='QmNoMatch'),
        ]

        result = get_submission_id_for_token(token, submissions)

        assert result is None


class TestUpdateSubmissionTokenIds:
    def test_updates_token_ids_and_status(self):
        existing_content = """{{Blue Railroad Submission
|exercise=Blue Railroad Train (Squats)
|video=test.mp4
|block_height=24207967
|status=Pending
}}"""
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/1': existing_content
        })

        result = update_submission_token_ids(client, 1, [5, 6, 7])

        assert result.action in ('updated', 'created')
        assert len(client.saved_pages) == 1
        title, content, summary = client.saved_pages[0]
        assert '|token_ids=5,6,7' in content
        assert '|status=Minted' in content

    def test_sorts_and_dedupes_token_ids(self):
        existing_content = """{{Blue Railroad Submission
|exercise=Test
}}"""
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/1': existing_content
        })

        result = update_submission_token_ids(client, 1, [7, 5, 5, 6, 7])

        title, content, summary = client.saved_pages[0]
        assert '|token_ids=5,6,7' in content

    def test_returns_unchanged_when_already_set(self):
        existing_content = """{{Blue Railroad Submission
|exercise=Test
|status=Minted
|token_ids=5,6,7
}}"""
        client = DryRunClient(existing_pages={
            'Blue Railroad Submission/1': existing_content
        })

        result = update_submission_token_ids(client, 1, [5, 6, 7])

        assert result.action == 'unchanged'
        assert len(client.saved_pages) == 0

    def test_returns_error_for_missing_page(self):
        client = DryRunClient(existing_pages={})

        result = update_submission_token_ids(client, 999, [1, 2])

        assert result.action == 'error'
        assert 'not found' in result.message.lower()
