# Builder script for the Application Lifecycle Deployment Engine
#
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Copyright: David García Pérez, Atos Research and Innovation, 2016.
#
# This code is licensed under an Apache 2.0 license. Please, refer to the LICENSE.TXT file for more information

import re
import shell
from model.models import Testbed

def parse_sinfo_partitions(command_output):
    """
    It parses an text in the following format:
    PARTITION    AVAIL  TIMELIMIT  NODES  STATE NODELIST
    bullx           up   infinite      1  drain nd15
    bullx           up   infinite      9   idle nd[10-14,16-19]

    into a list with a struct per node
    """

    nodes = []
    lines = command_output.split('\n')

    for line in lines:
        if line[:9] != "PARTITION":
            line = re.sub(' +', ' ', line)

            words = line.split(' ')
            partition = words[0]
            avail = words[1]
            timelimit = words[2]
            state = words[4]
            nodes_string = words[5]

            if '[' not in nodes_string:
                node = { 'partition': partition,
                         'partition_avail': avail,
                         'partition_timelimit': timelimit,
                         'partition_state': state,
                         'node_name': nodes_string}

                nodes.append(node)

            else:
                node_start_name = nodes_string.split('[')[0]
                boundaries = nodes_string.split('[')[1].split(']')[0].split(',')
                for boundarie in boundaries:
                    if '-' not in boundarie:
                        node_name = node_start_name + boundarie
                        node = { 'partition': partition,
                                 'partition_avail': avail,
                                 'partition_timelimit': timelimit,
                                 'partition_state': state,
                                 'node_name': node_name}

                        nodes.append(node)
                    else:
                        limits = boundarie.split('-')
                        start = int(limits[0])
                        end = int(limits[1]) + 1

                        for number in range(start,end):
                            node_name = node_start_name + str(number)
                            node = { 'partition': partition,
                                     'partition_avail': avail,
                                     'partition_timelimit': timelimit,
                                     'partition_state': state,
                                     'node_name': node_name}

                            nodes.append(node)

    return nodes

def get_nodes_testbed(testbed):
    """
    This function gets the testbed object information, from that information
    it determines if the testbed it is of the category SLURM.

    If it is SLURM, it will determine if it connects via ssh.

        If it connects via ssh it will get the node info executing the command
        via ssh

        If it is not ssh, it will execute directly the sinfo command in console.

    If it is not type SLURM it will just return an empty list
    """

    command = "sinfo"
    params = ["-a"]

    if testbed.category == Testbed.slurm_category:
        if testbed.protocol == Testbed.protocol_local:
            output = shell.execute_command(command=command, params=params)
            print(output)
        else:
            output = shell.execute_command(command=command,
                                           server=testbed.protocol,
                                           params=params)

        return parse_sinfo_partitions(output)
    else:
        return []
