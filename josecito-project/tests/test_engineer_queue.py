"""
test_engineer_queue.py — Engineer Queue Unit Tests
====================================================
Tests FIFO ordering, ticket creation, queue display,
and threading safety for the SystemEngineer.

⚠️  Uses a TEMP directory — never touches real ticket data.

Run: python3 tests/test_engineer_queue.py -v
"""

import os
import sys
import time
import threading
import unittest
import tempfile
from pathlib import Path
import shutil

_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from digos_lib.core_engineer import SystemEngineer
from digos_lib.core_log import LogKeeper


def make_engine():
    """Create an Engineer with a temp directory — safe for tests."""
    log = LogKeeper()
    tmp = tempfile.mkdtemp(prefix="josecito_test_")
    profiles_dir = Path(tmp)
    return SystemEngineer(log, profiles_dir=profiles_dir), tmp


class TestTicketCreation(unittest.TestCase):
    """Basic ticket creation and retrieval."""

    def setUp(self):
        self.engineer, self.tmpdir = make_engine()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_single_ticket(self):
        tid = self.engineer.create_ticket("test-agent", "api_key", "API key failed", "high")
        self.assertIsNotNone(tid)
        self.assertTrue(len(tid) > 10)

    def test_create_and_retrieve(self):
        tid = self.engineer.create_ticket("tg-test", "telegram", "Token invalid", "high")
        ticket = self.engineer.get_ticket(tid)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["target"], "telegram")
        self.assertEqual(ticket["status"], "open")

    def test_multiple_profiles(self):
        t1 = self.engineer.create_ticket("alice", "voice", "STT needed", "medium")
        t2 = self.engineer.create_ticket("bob", "web", "Browser needed", "low")
        self.assertNotEqual(t1, t2)

        alice_tickets = self.engineer.get_profile_tickets("alice")
        self.assertEqual(len(alice_tickets), 1)

        bob_tickets = self.engineer.get_profile_tickets("bob")
        self.assertEqual(len(bob_tickets), 1)


class TestFIFOOrdering(unittest.TestCase):
    """Tickets must be returned in FIFO order (oldest first)."""

    def setUp(self):
        self.engineer, self.tmpdir = make_engine()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_fifo_per_profile(self):
        """Tickets in the same profile should be FIFO."""
        t1 = self.engineer.create_ticket("fifo-order", "a", "first", "low")
        time.sleep(0.01)
        t2 = self.engineer.create_ticket("fifo-order", "b", "second", "low")
        time.sleep(0.01)
        t3 = self.engineer.create_ticket("fifo-order", "c", "third", "low")

        tickets = self.engineer.get_profile_tickets("fifo-order")
        self.assertEqual(len(tickets), 3)
        self.assertEqual(tickets[0]["target"], "a")
        self.assertEqual(tickets[1]["target"], "b")
        self.assertEqual(tickets[2]["target"], "c")

    def test_queue_global_ordering(self):
        """Global queue should sort all tickets by creation time."""
        import random
        suf = str(random.randint(10000, 99999))
        t1 = self.engineer.create_ticket(f"qa-{suf}", "first", "first ticket", "low")
        time.sleep(0.02)
        t2 = self.engineer.create_ticket(f"qb-{suf}", "second", "second ticket", "low")

        queue = self.engineer.queue()
        # Our 2 tickets should be in the queue
        queue_ids = [t["id"] for t in queue]
        self.assertIn(t1, queue_ids)
        self.assertIn(t2, queue_ids)
        # t1 should come before t2 in the queue
        self.assertLess(queue_ids.index(t1), queue_ids.index(t2))


class TestTicketLifecycle(unittest.TestCase):
    """Ticket must support status transitions."""

    def setUp(self):
        self.engineer, self.tmpdir = make_engine()
        self.profile = f"lifecycle-{id(self)}"
        self.tid = self.engineer.create_ticket(self.profile, "test-api", "test ticket", "medium")

    def tearDown(self):
        if hasattr(self, 'tmpdir'):
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_open_status(self):
        ticket = self.engineer.get_ticket(self.tid)
        self.assertEqual(ticket["status"], "open")

    def test_close_ticket(self):
        result = self.engineer.close_ticket(self.profile, self.tid, "resolved")
        self.assertTrue(result)
        ticket = self.engineer.get_ticket(self.tid)
        self.assertEqual(ticket["status"], "closed")

    def test_add_note(self):
        result = self.engineer.add_note(self.profile, self.tid, "Diagnosed as invalid key")
        self.assertTrue(result)
        ticket = self.engineer.get_ticket(self.tid)
        self.assertEqual(len(ticket.get("notes", [])), 1)
        self.assertIn("Diagnosed", ticket["notes"][0]["text"])

    def test_update_status(self):
        self.engineer.update_status(self.profile, self.tid, "processing")
        ticket = self.engineer.get_ticket(self.tid)
        self.assertEqual(ticket["status"], "processing")


class TestConcurrentTickets(unittest.TestCase):
    """Multiple threads creating tickets must not conflict."""

    def setUp(self):
        self.engineer, self.tmpdir = make_engine()
        self.errors = []

    def _create_ticket(self, profile):
        try:
            self.engineer.create_ticket(profile, "concurrent", "test", "low")
        except Exception as e:
            self.errors.append(str(e))

    def test_25_concurrent_requests(self):
        threads = []
        for i in range(25):
            t = threading.Thread(target=self._create_ticket, args=(f"con-{i:02d}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(self.errors), 0)

        # Verify all tickets exist
        for i in range(25):
            tickets = self.engineer.get_profile_tickets(f"con-{i:02d}")
            self.assertEqual(len(tickets), 1, f"Missing ticket for con-{i:02d}")


class TestQueueDisplay(unittest.TestCase):
    """Queue display must generate readable output."""

    def setUp(self):
        self.engineer, self.tmpdir = make_engine()

    def test_empty_queue_display(self):
        output = self.engineer.show_queue()
        self.assertIn("empty", output.lower())

    def test_queue_with_tickets(self):
        self.engineer.create_ticket("display-test-v", "voice-input", "STT needed", "high")
        self.engineer.create_ticket("display-test-w", "web-search", "Browser", "medium")
        output = self.engineer.show_queue()
        self.assertIn("QUEUE", output)
        self.assertIn("voice", output)

    def test_next_ticket(self):
        t1 = self.engineer.create_ticket("next-demo", "first-job", "first", "high")
        time.sleep(0.02)
        self.engineer.create_ticket("next-demo", "second-job", "second", "low")

        next_t = self.engineer.next_ticket()
        self.assertIsNotNone(next_t)
        self.assertEqual(next_t["id"], t1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
