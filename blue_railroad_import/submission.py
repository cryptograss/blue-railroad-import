"""Operations for Blue Railroad submission pages."""

import re
from typing import Optional, Tuple

from .wiki_client import WikiClientProtocol, SaveResult


SUBMISSION_PAGE_PREFIX = 'Blue Railroad Submission/'


def get_submission_page_title(submission_id: int) -> str:
    """Get the wiki page title for a submission."""
    return f"{SUBMISSION_PAGE_PREFIX}{submission_id}"


def update_submission_field(
    wikitext: str,
    field_name: str,
    field_value: str,
) -> Tuple[str, bool]:
    """Update or add a field in the Blue Railroad Submission template.

    Returns (updated_wikitext, was_changed).
    """
    # Pattern to match the template and capture its contents
    template_pattern = r'(\{\{Blue Railroad Submission\s*)(.*?)(\}\})'
    match = re.search(template_pattern, wikitext, re.DOTALL | re.IGNORECASE)

    if not match:
        raise ValueError("Could not find {{Blue Railroad Submission}} template in page")

    template_start = match.group(1)
    template_body = match.group(2)
    template_end = match.group(3)

    # Check if field already exists
    field_pattern = rf'\|{field_name}\s*=\s*[^\|]*'
    existing_match = re.search(field_pattern, template_body, re.IGNORECASE)

    if existing_match:
        # Update existing field
        old_value = existing_match.group(0)
        new_value = f"|{field_name}={field_value}"
        if old_value.strip() == new_value.strip():
            return wikitext, False  # No change needed
        new_body = template_body[:existing_match.start()] + new_value + template_body[existing_match.end():]
    else:
        # Add new field before the closing }}
        # Find a good place to insert (after last existing field)
        new_body = template_body.rstrip()
        if not new_body.endswith('\n'):
            new_body += '\n'
        new_body += f"|{field_name}={field_value}\n"

    new_wikitext = wikitext[:match.start()] + template_start + new_body + template_end + wikitext[match.end():]
    return new_wikitext, True


def update_submission_cid(
    wiki_client: WikiClientProtocol,
    submission_id: int,
    ipfs_cid: str,
    verbose: bool = False,
) -> SaveResult:
    """Update a submission page with the IPFS CID.

    Args:
        wiki_client: Wiki client for reading/writing pages
        submission_id: The submission number (e.g., 1 for "Blue Railroad Submission/1")
        ipfs_cid: The IPFS CID to add (e.g., "bafybeif...")
        verbose: Print progress messages

    Returns:
        SaveResult indicating what happened
    """
    page_title = get_submission_page_title(submission_id)

    if verbose:
        print(f"Updating {page_title} with IPFS CID: {ipfs_cid}")

    # Get current page content
    current_content = wiki_client.get_page_content(page_title)

    if current_content is None:
        return SaveResult(page_title, 'error', f'Page not found: {page_title}')

    try:
        updated_content, was_changed = update_submission_field(
            current_content,
            'ipfs_cid',
            ipfs_cid,
        )
    except ValueError as e:
        return SaveResult(page_title, 'error', str(e))

    if not was_changed:
        return SaveResult(page_title, 'unchanged', 'IPFS CID already set to this value')

    summary = f"Add IPFS CID: {ipfs_cid[:20]}..."
    return wiki_client.save_page(page_title, updated_content, summary)


def update_submission_token_id(
    wiki_client: WikiClientProtocol,
    submission_id: int,
    participant_wallet: str,
    token_id: int,
    verbose: bool = False,
) -> SaveResult:
    """Update a submission page to record a minted token for a participant.

    This updates the status field and could potentially update participant records.
    For now, it just updates the status to 'Minted'.

    Args:
        wiki_client: Wiki client for reading/writing pages
        submission_id: The submission number
        participant_wallet: The wallet address that received the token
        token_id: The minted token ID
        verbose: Print progress messages

    Returns:
        SaveResult indicating what happened
    """
    page_title = get_submission_page_title(submission_id)

    if verbose:
        print(f"Recording mint for {page_title}: Token #{token_id} to {participant_wallet}")

    current_content = wiki_client.get_page_content(page_title)

    if current_content is None:
        return SaveResult(page_title, 'error', f'Page not found: {page_title}')

    try:
        # Update status to Minted
        updated_content, was_changed = update_submission_field(
            current_content,
            'status',
            'Minted',
        )
    except ValueError as e:
        return SaveResult(page_title, 'error', str(e))

    if not was_changed:
        return SaveResult(page_title, 'unchanged', 'Status already set to Minted')

    summary = f"Mark as minted: Token #{token_id} to {participant_wallet[:10]}..."
    return wiki_client.save_page(page_title, updated_content, summary)
