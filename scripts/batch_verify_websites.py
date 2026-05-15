"""
batch_verify_websites.py — Check all leads with no website for actual domains.

Resumable: updates the DB as it goes. Can be stopped and restarted.
Usage: python3 batch_verify_websites.py [--batch 50] [--delay 0.5]
"""

import sqlite3
import sys
import time
import os
from pathlib import Path

HERE = Path(__file__).parent.parent
DB_PATH = HERE / 'data' / 'sales_agent.db'

# Import the detector — add parent to path
sys.path.insert(0, str(HERE / 'agents'))
from website_detector import detect_website


def main():
    batch_size = 50
    delay = 0.5  # seconds between checks

    # Parse args
    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith('--batch='):
            batch_size = int(arg.split('=')[1])
        elif arg.startswith('--delay='):
            delay = float(arg.split('=')[1])

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Get leads with no website
    leads = conn.execute("""
        SELECT id, business_name, city FROM leads 
        WHERE website IS NULL OR website = ''
        ORDER BY id
    """).fetchall()

    total = len(leads)
    print(f'Checking {total} leads for websites...')
    print(f'Batch size: {batch_size}, Delay: {delay}s')
    print()

    found = 0
    not_found = 0
    errors = 0
    processed = 0
    report = []

    for i, lead_row in enumerate(leads):
        lead = dict(lead_row)
        lead_id = lead['id']
        name = lead['business_name']
        city = lead.get('city', '') or ''

        if i > 0 and delay > 0 and i % 5 == 0:
            time.sleep(delay)

        try:
            url = detect_website(name, city, delay=0)  # no extra delay inside
            if url:
                conn.execute(
                    "UPDATE leads SET website = ? WHERE id = ?",
                    (url, lead_id)
                )
                conn.commit()
                found += 1
                report.append(f'  ✓ #{lead_id}: {name} → {url}')
            else:
                not_found += 1
        except Exception as e:
            errors += 1
            report.append(f'  ✗ #{lead_id}: {name} → ERROR: {e}')

        processed += 1

        # Progress report every batch
        if processed % batch_size == 0 or processed == total:
            pct = processed / total * 100
            print(f'[{processed}/{total} ({pct:.0f}%)] Found: {found} | Not found: {not_found} | Errors: {errors}')
            # Print last batch of discoveries
            for line in report[-batch_size:]:
                if line.startswith('  ✓'):
                    print(line)
            print()

    conn.close()

    print('=' * 50)
    print(f'DONE — {total} leads checked')
    print(f'  Found websites:  {found}')
    print(f'  No website:      {not_found}')
    print(f'  Errors:          {errors}')
    print(f'  New sites added: {found}')

    # Summary
    conn2 = sqlite3.connect(str(DB_PATH))
    with_website = conn2.execute("SELECT COUNT(*) FROM leads WHERE website IS NOT NULL AND website != ''").fetchone()[0]
    total_leads = conn2.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    print(f'\n  Leads with website NOW: {with_website}/{total_leads} ({with_website/total_leads*100:.1f}%)')
    conn2.close()


if __name__ == '__main__':
    main()
