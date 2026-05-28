"""
Factory Throughput Test — 25 tickets, 3 categories
===================================================
Measures end-to-end processing time from ticket creation to queue completion.

- 5 STT (voice input) requests
- 15 Web tool requests
- 5 Vision tool review requests

Run with: python3 tests/test_factory_25_tickets.py
"""

import os, sys, json, time, threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from digos_lib.core_engineer import SystemEngineer
from digos_lib.core_log import LogKeeper

# ── CONFIG ──────────────────────────────────────────
TICKET_GROUPS = {
    "STT (voice input)": {
        "count": 5,
        "agents": [f"stt-agent-{i:02d}" for i in range(5)],
        "target": "capability_request:stt_audio_input",
        "problem": "Need STT capability to receive voice messages and audio input",
    },
    "Web tool": {
        "count": 15,
        "agents": [f"web-agent-{i:02d}" for i in range(15)],
        "target": "capability_request:web_browsing",
        "problem": "Need web browsing capability to navigate and search the internet",
    },
    "Vision review": {
        "count": 5,
        "agents": [f"vision-agent-{i:02d}" for i in range(5)],
        "target": "tool_request:vision_analyze",
        "problem": "Need vision analysis tool for image and video processing",
    },
}

log = LogKeeper()
engineer = SystemEngineer(log)
results = {"tickets": [], "errors": []}
results_lock = threading.Lock()
start_time = None
end_time = None


def create_ticket(agent, target, problem):
    """Create a ticket and record timing."""
    global start_time, end_time
    try:
        t0 = time.time()
        tid = engineer.create_ticket(agent, target, problem, severity="medium")
        t1 = time.time()
        with results_lock:
            results["tickets"].append({
                "tid": tid, "agent": agent, "target": target,
                "created": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round((t1 - t0) * 1000, 2),
            })
        return tid
    except Exception as e:
        with results_lock:
            results["errors"].append(f"{agent}: {e}")
        return None


def worker(agent, target, problem):
    create_ticket(agent, target, problem)


def compute_queue_processing_time():
    """Simulate factory processing: read all open tickets in FIFO order."""
    queue = engineer.queue()
    if not queue:
        return 0, 0, []

    processing_log = []
    total_ms = 0

    for i, ticket in enumerate(queue):
        p_start = time.time()

        # Simulate processing: update status through lifecycle
        profile = ticket.get("profile", "system")
        tid = ticket.get("id", "")
        if not tid:
            continue

        engineer.update_status(profile, tid, "processing")
        time.sleep(0.001)  # 1ms simulated processing per ticket
        engineer.add_note(profile, tid, f"Processing started: {ticket.get('target','?')}")

        engineer.update_status(profile, tid, "reviewing")
        time.sleep(0.001)  # 1ms simulated review

        engineer.add_note(profile, tid, "Factory review complete, routing to build")
        engineer.update_status(profile, tid, "completed")

        p_end = time.time()
        p_ms = round((p_end - p_start) * 1000, 2)
        total_ms += p_ms

        processing_log.append({
            "pos": i + 1,
            "tid": tid,
            "agent": profile,
            "target": ticket.get("target", "?"),
            "processing_ms": p_ms,
        })

    return total_ms, len(queue), processing_log


def main():
    global start_time, end_time

    print("=" * 65)
    print("  FACTORY THROUGHPUT TEST — 25 Tickets, 3 Categories")
    print("=" * 65)
    print()

    # ── Phase 1: Clean mailboxes ──
    print("📋 Phase 1: Cleaning mailboxes...")
    profiles_dir = Path.home() / ".digos" / "profiles"
    if profiles_dir.exists():
        for p in profiles_dir.iterdir():
            if p.is_dir():
                mbox = p / "MAILBOX"
                if mbox.exists():
                    import shutil
                    shutil.rmtree(mbox)
    print("   Done.")

    # ── Phase 2: Launch all tickets ──
    total_expected = sum(g["count"] for g in TICKET_GROUPS.values())
    print(f"\n📋 Phase 2: Launching {total_expected} tickets...")
    for group_name, group in TICKET_GROUPS.items():
        print(f"   {group['count']:2d} × {group_name}")
    print()

    threads = []
    start_time = time.time()

    for group_name, group in TICKET_GROUPS.items():
        for i in range(group["count"]):
            agent = group["agents"][i]
            t = threading.Thread(target=worker, args=(agent, group["target"], group["problem"]))
            threads.append(t)
            t.start()

    for t in threads:
        t.join()

    end_time = time.time()
    creation_span = round((end_time - start_time) * 1000, 2)

    # ── Phase 3: Verify tickets ──
    print(f"\n📋 Phase 3: Ticket Creation Results")
    all_tickets = engineer.get_all_tickets()
    print(f"   Created:      {len(results['tickets'])}")
    print(f"   Expected:     {total_expected}")
    print(f"   Errors:       {len(results['errors'])}")
    print(f"   Creation span: {creation_span}ms")
    print(f"   Throughput:   {round(total_expected / (creation_span/1000))} tickets/sec")

    if len(results['tickets']) == total_expected:
        print("   ✅ All tickets created")
    else:
        print(f"   ⚠️  Mismatch: check errors")

    # Check for duplicates
    ids = [t["tid"] for t in results["tickets"]]
    if len(ids) != len(set(ids)):
        print("   ❌ DUPLICATE IDs FOUND!")
    else:
        print("   ✅ No duplicate IDs")

    # Check FIFO
    queue = engineer.queue()
    timestamps = [t.get("created_at", "") for t in queue]
    if all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1)):
        print("   ✅ FIFO ordering correct")
    else:
        print("   ❌ FIFO ordering broken")

    # ── Phase 4: Factory processing time ──
    print(f"\n📋 Phase 4: Factory Processing (simulated)")
    total_ms, processed_count, proc_log = compute_queue_processing_time()
    print(f"   Queue size:   {processed_count}")
    print(f"   Total time:   {total_ms}ms")
    print(f"   Avg/ticket:   {round(total_ms/processed_count, 2)}ms" if processed_count else "   N/A")

    # Show details per category
    print(f"\n📋 Phase 5: Category Breakdown")
    for group_name, group in TICKET_GROUPS.items():
        group_tickets = [t for t in results["tickets"] if t["agent"] in group["agents"]]
        group_queue = [t for t in queue if t.get("profile") in group["agents"]]
        print(f"   {group_name}:")
        print(f"      Created: {len(group_tickets)}")
        print(f"      In queue: {len(group_queue)}")
        avg_dur = round(sum(t["duration_ms"] for t in group_tickets) / len(group_tickets), 2) if group_tickets else 0
        print(f"      Avg creation: {avg_dur}ms")

    # ── Phase 6: Timing Summary ──
    print(f"\n📋 Phase 6: TIMING SUMMARY — MEASURE THIS")
    wall_start = datetime.now(timezone.utc)
    print(f"   Frame start (UTC):  {wall_start.isoformat(timespec='milliseconds')}")
    print(f"   Creation done (UTC): {(wall_start + timedelta(milliseconds=creation_span)).isoformat(timespec='milliseconds')}")
    print(f"   Creation wall time:  {creation_span}ms")
    print(f"   Simulated factory:   {total_ms}ms")
    print(f"   Total throughput:    {round(total_expected / ((creation_span + total_ms)/1000))} tickets/sec")

    # ── Result ──
    print(f"\n{'=' * 65}")
    passed = len(results['tickets']) == total_expected and len(results['errors']) == 0
    tag = "✅ FACTORY TEST PASSED" if passed else "⚠️ FACTORY TEST ISSUES"
    print(f"  {tag}")
    print(f"  🎯 Compare this time with your external measurement.")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
