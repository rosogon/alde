# Builder script for the Application Lifecycle Deployment Engine
#
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Copyright: David García Pérez, Atos Research and Innovation, 2016.
#
# This code is licensed under an Apache 2.0 license. Please, refer to
# the LICENSE.TXT file for more information

import unittest
from model.testbed import Testbed
from model.node import Node

class TestbedTest(unittest.TestCase):
    """Check the correct work of the different mthods in the Testbed class
       that represents a Testbed for the Application Lifecycle Deployment
       Engine"""

    def test_add_node(self):
        """Test that the method that add a node to the list of nodes works
           as expected"""

        # We create a testbed first
        testbed = Testbed("name", True, "slurm", "ssh", "user@server", ['slurm'])
        self.assertEquals(0, len(testbed.nodes))

        # We add a node to the testbed and veriy it is added
        node_1 = Node(1, "node333", "on-line")
        testbed.add_node(node_1)
        self.assertEquals(1, len(testbed.nodes))
        self.assertEquals(node_1, testbed.nodes[0])

        # We verify that it is not possible to add an object that it is not
        # from type Node
        no_node = "xxx"
        testbed.add_node(no_node)
        #self.assertEquals(1, len(testbed.nodes))
        self.assertEquals(node_1, testbed.nodes[0])