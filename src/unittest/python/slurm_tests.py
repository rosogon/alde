# Builder script for the Application Lifecycle Deployment Engine
#
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Copyright: David García Pérez, Atos Research and Innovation, 2016.
#
# This code is licensed under an Apache 2.0 license. Please, refer to the LICENSE.TXT file for more information


import unittest
import unittest.mock as mock
import slurm
from model.models import Testbed

class SlurmTests(unittest.TestCase):
    """
    Unittests of the functions used to interact with and slurm
    testbed
    """

    command_output = """PARTITION    AVAIL  TIMELIMIT  NODES  STATE NODELIST
bullx           up   infinite      1  drain nd15
bullx           up   infinite      9   idle nd[10-14,16-19]
partners*       up    8:00:00      1  drain nd15
partners*       up    8:00:00      9   idle nd[10-14,16-19]
gpus            up   infinite      2 drain* nd[20-21]
gpus            up   infinite      1   idle nd22
gpu2075         up   infinite      1 maint* nd23
B510_2.2GHz     up   infinite      2 maint* nd[36-37]
B510_2.2GHz     up   infinite      2   idle nd[38-39]
B510_2.6GHz     up   infinite      2 maint* nd[32-33]
B510_2.6GHz     up   infinite      1  maint nd31
B510_2.6GHz     up   infinite      9   idle nd[24-26,28-30,40-41,43]
B510_2.6GHz     up   infinite      2   down nd[27,42]
B515k20x        up   infinite      2 drain* nd[44-45]
B515xeon-phi    up   infinite      2 drain* nd[46-47]
B520            up   infinite      1 drain* nd56
B520            up   infinite      9  drain nd[57-65]
bullion         up   infinite      1  maint nd76
bullion_S       up   infinite      1  alloc nd80"""

    example1 = {
                'partition_state': 'drain',
                'partition': 'bullx',
                'node_name': 'nd15',
                'partition_timelimit': 'infinite',
                'partition_avail': 'up'
               }
    example2 = {
                'partition_state': 'idle',
                'partition': 'bullx',
                'node_name': 'nd10',
                'partition_timelimit': 'infinite',
                'partition_avail': 'up'
               }
    example3 = {
                'partition_state': 'idle',
                'partition': 'B510_2.6GHz',
                'node_name': 'nd43',
                'partition_timelimit': 'infinite',
                'partition_avail': 'up'
               }
    example4 = {
                'partition_avail': 'up',
                'partition': 'B510_2.6GHz',
                'node_name': 'nd41',
                'partition_timelimit': 'infinite',
                'partition_state': 'idle'
               }

    def test_parse_sinfo_partitions(self):
        """
        Check it is possible to parse the output of the slurm
        sinfo -a
        command
        """
        output = slurm.parse_sinfo_partitions(self.command_output)

        # We verify the output
        self.assertEquals(58,len(output))
        self.assertTrue(self.example1 in output)
        self.assertTrue(self.example2 in output)
        self.assertTrue(self.example3 in output)
        self.assertTrue(self.example4 in output)

    @mock.patch('slurm.shell.execute_command')
    def test_get_nodes_testbed(self, mock_shell):
        """
        It verifies the correct work of the function get_nodes_testbed
        """
        command="sinfo"
        params=["-a"]

        # It checks first if it is type SLURM
        testbed = Testbed('x', 'false', 'xxx', 'protocol', 'xxx')

        nodes = slurm.get_nodes_testbed(testbed)
        self.assertEquals(0, len(nodes))

        # We create a testbed with local access
        testbed = Testbed('x', 'false', Testbed.slurm_category, Testbed.protocol_local, 'xxx')
        mock_shell.return_value = self.command_output
        nodes = slurm.get_nodes_testbed(testbed)

        self.assertEquals(58,len(nodes))
        self.assertTrue(self.example1 in nodes)
        self.assertTrue(self.example2 in nodes)
        self.assertTrue(self.example3 in nodes)
        self.assertTrue(self.example4 in nodes)
        mock_shell.assert_called_with(command=command, params=params)

        # We create a testbe with ssh access
        testbed = Testbed('x', 'false', Testbed.slurm_category, "user@ssh.com", 'xxx')
        mock_shell.return_value = self.command_output
        nodes = slurm.get_nodes_testbed(testbed)

        self.assertEquals(58,len(nodes))
        self.assertTrue(self.example1 in nodes)
        self.assertTrue(self.example2 in nodes)
        self.assertTrue(self.example3 in nodes)
        self.assertTrue(self.example4 in nodes)
        mock_shell.assert_called_with(command=command, server="user@ssh.com", params=params)
