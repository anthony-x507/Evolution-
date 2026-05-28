"""
Factory Flow Test — 50 Concurrent Agent Requests
=================================================
Simulates 50 agents sending different skill/tool requests simultaneously
to test the Engineer queue system under load.

Tests:
1. FIFO ordering under concurrent load
2. No lost/overwritten tickets
3. Queue display works after batch
4. Skill audit trigger (if applicable)
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path — needed for both main thread and worker threads
_PROJECT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_PROJECT)  # tests/ is one level deep
for p in [_PROJECT, _PARENT]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Simulated agent profiles
AGENTS = [
    "josecito", "alex", "freya", "oslox", "sheykox",
    "builder-01", "builder-02", "auditor-01", "reviewer-01",
    "agent-10", "agent-11", "agent-12", "agent-13", "agent-14",
    "agent-15", "agent-16", "agent-17", "agent-18", "agent-19",
    "agent-20", "agent-21", "agent-22", "agent-23", "agent-24",
    "agent-25", "agent-26", "agent-27", "agent-28", "agent-29",
    "agent-30", "agent-31", "agent-32", "agent-33", "agent-34",
    "agent-35", "agent-36", "agent-37", "agent-38", "agent-39",
    "agent-40", "agent-41", "agent-42", "agent-43", "agent-44",
    "agent-45", "agent-46", "agent-47", "agent-48", "agent-49",
]

# Simulated skill/tool requests
REQUESTS = [
    ("voice_input", "I need STT capability to receive voice messages"),
    ("voice_output", "I need TTS capability to speak responses"),
    ("web_browsing", "I need to browse websites"),
    ("web_search", "I need to search the internet"),
    ("file_editor", "I need to edit files programmatically"),
    ("image_gen", "I need to generate images"),
    ("data_fetch", "I need to fetch data from APIs"),
    ("email_send", "I need to send emails"),
    ("calendar", "I need calendar integration"),
    ("database", "I need database query capability"),
]

# Results tracking
results = {
    "total": 0,
    "success": 0,
    "errors": [],
    "tickets": [],
    "timestamps": [],
}
results_lock = threading.Lock()


def create_ticket(agent_name, target, problem):
    """Simulates creating a ticket. Mirrors SystemEngineer.create_ticket logic."""
    from digos_lib.core_engineer import SystemEngineer
    from digos_lib.core_log import LogKeeper

    try:
        log = LogKeeper()
        engineer = SystemEngineer(log)
        tid = engineer.create_ticket(agent_name, target, problem, severity="medium")

        with results_lock:
            results["total"] += 1
            results["success"] += 1
            results["tickets"].append({
                "tid": tid,
                "agent": agent_name,
                "target": target,
                "time": datetime.now(timezone.utc).isoformat(),
            })
            results["timestamps"].append(time.time())
        return tid
    except Exception as e:
        with results_lock:
            results["total"] += 1
            results["errors"].append(f"{agent_name}/{target}: {e}")
        return None


def worker(agent_name, target, problem):
    """Worker thread: creates a ticket."""
    create_ticket(agent_name, target, problem)


def main():
    print("=" * 60)
    print("  FACTORY FLOW TEST — 50 Concurrent Requests")
    print("=" * 60)
    print()

    # Phase 1: Clean previous test tickets
    print("📋 Phase 1: Clearing previous test tickets...")
    profiles_dir = Path.home() / ".digos" / "profiles"
    for agent in AGENTS[:5]:  # only clean first 5 (test agents)
        mailbox = profiles_dir / agent / "MAILBOX"
        if mailbox.exists():
            for f in mailbox.glob("*.json"):
                f.unlink()
    print("   Done.")

    # Phase 2: Launch 50 concurrent requests
    print(f"\n📋 Phase 2: Launching {len(AGENTS)} concurrent requests...")
    threads = []
    start_time = time.time()

    for i, agent in enumerate(AGENTS):
        target, problem = REQUESTS[i % len(REQUESTS)]
        t = threading.Thread(target=worker, args=(agent, target, problem))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    elapsed = time.time() - start_time
    print(f"   All threads completed in {elapsed:.2f}s")

    # Phase 3: Verify results
    print(f"\n📋 Phase 3: Results")
    print(f"   Total requests: {results['total']}")
    print(f"   Successful:     {results['success']}")
    print(f"   Errors:         {len(results['errors'])}")
    if results['errors']:
        for e in results['errors'][:5]:
            print(f"     ❌ {e}")
        if len(results['errors']) > 5:
            print(f"     ... and {len(results['errors']) - 5} more")

    # Phase 4: Check Engineer queue
    print(f"\n📋 Phase 4: Engineer Queue Check")
    from digos_lib.core_engineer import SystemEngineer
    from digos_lib.core_log import LogKeeper
    log = LogKeeper()
    engineer = SystemEngineer(log)

    # Check each profile's tickets
    total_tickets = 0
    ticket_ids = []
    for agent in AGENTS:
        tickets = engineer.get_profile_tickets(agent)
        if tickets:
            total_tickets += len(tickets)
            for t in tickets:
                ticket_ids.append(t.get("id", "?"))

    print(f"   Tickets found: {total_tickets}")
    print(f"   Expected:      {len(AGENTS)}")

    if total_tickets == len(AGENTS):
        print("   ✅ All tickets created successfully")
    else:
        print(f"   ❌ Mismatch: {total_tickets} != {len(AGENTS)}")

    # Check for duplicate ticket IDs
    if len(ticket_ids) != len(set(ticket_ids)):
        print("   ❌ DUPLICATE TICKET IDs FOUND!")
        from collections import Counter
        dupes = [tid for tid, count in Counter(ticket_ids).items() if count > 1]
        for d in dupes[:5]:
            print(f"      Duplicate: {d}")
    else:
        print("   ✅ No duplicate ticket IDs")

    # Check FIFO ordering — use engineer.queue() which sorts globally
    print(f"\n📋 Phase 5: FIFO Ordering Check")
    queue = engineer.queue()
    if len(queue) >= 2:
        timestamps = [t.get("created_at", "") for t in queue]
        is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
        if is_sorted:
            print("   ✅ Tickets are FIFO-ordered by creation time")
        else:
            print("   ❌ Tickets NOT in FIFO order!")

    # Phase 6: Show queue summary
    print(f"\n📋 Phase 6: Engineer Queue Summary")
    print(engineer.show_queue(10))

    # Phase 7: Timing analysis
    print(f"\n📋 Phase 7: Timing Analysis")
    if results["timestamps"]:
        first = min(results["timestamps"])
        last = max(results["timestamps"])
        span = last - first
        print(f"   First request:  {datetime.fromtimestamp(first).strftime('%H:%M:%S.%f')}")
        print(f"   Last request:   {datetime.fromtimestamp(last).strftime('%H:%M:%S.%f')}")
        print(f"   Total span:     {span:.3f}s")
        print(f"   Throughput:     {len(results['timestamps']) / span:.0f} tickets/second")

    print()
    print("=" * 60)
    if total_tickets == len(AGENTS) and not ticket_ids or len(ticket_ids) == len(set(ticket_ids)):
        print("  ✅ FACTORY FLOW TEST: PASSED")
    else:
        print("  ⚠️  FACTORY FLOW TEST: ISSUES FOUND — review above")
    print("=" * 60)


if __name__ == "__main__":
    main()
