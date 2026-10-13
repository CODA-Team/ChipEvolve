"""The expert's documented read-only probe must reach the native interpreter."""

import unittest

from LLM_call import parse_commands, sanitize_tcl_output, validate_reply


class NativeProbeTests(unittest.TestCase):
    def test_network_probe_survives_transport_and_original_validation(self):
        command = "eco_net_sink_report [get_name [get_nets -of_objects [get_pins {_534_/CON}]]]"
        reply = sanitize_tcl_output("### Tcl recipe\n```tcl\n" + command + "\n```")
        self.assertEqual(parse_commands(reply), [command])
        self.assertEqual(validate_reply(reply, [], set()), (True, ""))


if __name__ == "__main__":
    unittest.main()
