"""
test_message_bus.py — Message Bus Integration Tests
====================================================
Tests multi-agent communication via Unix sockets.

Scenarios:
1. Collaborative agents: Josecito sends message to Alex
2. Isolated agent: Freya cannot see other agents
3. Broadcast: System notification to all agents
4. Agent list: Filter by mode (collaborative/isolated)

Run: python3 tests/test_message_bus.py -v
"""

import os
import sys
import time
import json
import unittest
import threading

_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from bus import MessageBus, AgentBusClient, BUS_DIR


class TestMessageBus(unittest.TestCase):
    """Multi-agent communication via the message bus."""

    @classmethod
    def setUpClass(cls):
        """Start the bus once for all tests."""
        cls.bus = MessageBus()
        cls.bus.set_message_callback(lambda msg: None)
        # Register agents before starting
        cls.bus.register_agent("josecito", "collaborative")
        cls.bus.register_agent("alex", "collaborative")
        cls.bus.register_agent("freya", "isolated")
        cls.bus.register_agent("sheykox", "isolated")
        # Start the bus
        cls.bus.start()
        # Wait for bus to be ready (sockets created and listening)
        for _ in range(20):
            sock_path = BUS_DIR / "josecito.sock"
            if sock_path.exists():
                break
            time.sleep(0.2)
        # Extra time for the listening thread to start
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.bus.stop()
        # Clean up socket files
        import shutil
        if BUS_DIR.exists():
            shutil.rmtree(BUS_DIR)

    def test_01_agents_registered(self):
        """Four agents should be registered with correct modes."""
        agents = self.bus.list_agents()
        names = [a["name"] for a in agents]
        self.assertIn("josecito", names)
        self.assertIn("alex", names)
        self.assertIn("freya", names)
        modes = {a["name"]: a["mode"] for a in agents}
        self.assertEqual(modes["josecito"], "collaborative")
        self.assertEqual(modes["freya"], "isolated")

    def test_02_agent_clients_connect(self):
        """Agents should be able to connect as clients."""
        client = AgentBusClient("josecito")
        ok = client.connect()
        self.assertTrue(ok)
        time.sleep(0.5)  # let bus register the connection
        client.disconnect()

    def test_03_collaborative_send(self):
        """Josecito should be able to send a message to Alex."""
        sender = AgentBusClient("josecito")
        sender.connect()
        time.sleep(0.5)  # let register complete

        result = sender.send("alex", "Hello from Josecito!")
        self.assertTrue(result)
        sender.disconnect()

    def test_04_isolated_cannot_list(self):
        """Freya (isolated) should NOT be able to list agents."""
        freya = AgentBusClient("freya")
        freya.connect()
        time.sleep(0.5)

        agents = freya.list_agents()
        self.assertIsNone(agents)
        freya.disconnect()

    def test_05_collaborative_can_list(self):
        """Josecito (collaborative) SHOULD be able to list agents."""
        jose = AgentBusClient("josecito")
        jose.connect()
        time.sleep(0.5)

        agents = jose.list_agents()
        self.assertIsNotNone(agents)
        names = [a["name"] for a in agents]
        self.assertIn("alex", names)
        jose.disconnect()

    def test_06_isolated_send_to_supervisor(self):
        """Freya should be able to send messages to supervisor (Control Tower)."""
        freya = AgentBusClient("freya")
        freya.connect()
        time.sleep(0.5)

        result = freya.send_to_supervisor("Status report from Freya")
        self.assertTrue(result)
        freya.disconnect()

    def test_07_isolated_cannot_send_to_other(self):
        """Freya should NOT be able to send directly to another agent."""
        freya = AgentBusClient("freya")
        freya.connect()
        time.sleep(0.5)

        result = freya.send("alex", "Hey Alex")
        self.assertFalse(result)
        freya.disconnect()

    def test_08_concurrent_messages(self):
        """Multiple agents sending messages simultaneously."""
        results = []
        lock = threading.Lock()

        def send_as(agent_name, target, msg):
            client = AgentBusClient(agent_name)
            if client.connect():
                time.sleep(0.5)
                ok = client.send(target, msg)
                with lock:
                    results.append((agent_name, ok))
                client.disconnect()

        threads = []
        threads.append(threading.Thread(target=send_as, args=("josecito", "alex", "msg1")))
        threads.append(threading.Thread(target=send_as, args=("alex", "josecito", "msg2")))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 2)
        for name, ok in results:
            self.assertTrue(ok, f"{name} failed to send")

    def test_09_agent_list_filtered(self):
        """List agents filtered by mode."""
        jose = AgentBusClient("josecito")
        jose.connect()
        time.sleep(0.5)

        collaborative = jose.list_agents("collaborative")
        self.assertIsNotNone(collaborative)
        if collaborative:
            modes = [a["mode"] for a in collaborative]
            self.assertTrue(all(m == "collaborative" for m in modes))
        jose.disconnect()

    def test_10_reconnect_after_disconnect(self):
        """Agent should be able to disconnect and reconnect."""
        client = AgentBusClient("josecito")
        # Retry connect in case bus isn't ready yet
        ok1 = False
        for _ in range(10):
            ok1 = client.connect()
            if ok1:
                break
            time.sleep(0.3)
        time.sleep(0.3)
        self.assertTrue(ok1)
        client.disconnect()
        time.sleep(0.3)

        ok2 = False
        for _ in range(10):
            ok2 = client.connect()
            if ok2:
                break
            time.sleep(0.3)
        time.sleep(0.3)
        self.assertTrue(ok2)
        client.disconnect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
