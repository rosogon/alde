# Builder script for the Application Lifecycle Deployment Engine
#
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Copyright: David García Pérez, Atos Research and Innovation, 2016.
#
# This code is licensed under an Apache 2.0 license. Please, refer to the LICENSE.TXT file for more information

import re
import shell
import query
import logging
import linux_probes.cpu_info_parser as parser
from model.models import Testbed, Node, CPU
from model.base import db

def parse_sinfo_partitions(command_output):
    """
    It parses an text in the following format:
    PARTITION    AVAIL  TIMELIMIT  NODES  STATE NODELIST
    bullx           up   infinite      1  drain nd15
    bullx           up   infinite      9   idle nd[10-14,16-19]

    into a list with a struct per node
    """

    nodes = []
    lines = command_output.decode('utf-8').split('\n')

    for line in lines:

        if not line.startswith("PARTITION") and line:
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
        elif testbed.protocol == Testbed.protocol_ssh:
            output = shell.execute_command(command=command,
                                           server=testbed.endpoint,
                                           params=params)
        else:
            return []

        return parse_sinfo_partitions(output)
    else:
        return []

def check_nodes_in_db_for_on_line_testbeds():
    """
    This function it is going to get all the nodes in the db that are:
        on-line
        Type slurm

    To each node it is going to get the nodes and it is going to compare the
    information with the information in the db. It can happen two things:
        * If the node is in the db, info it is updated if necessary
        * If the node is not in the db, it is added

    After that, the method it is going to verify if there is a node that it is
    in the db but it is not in the list provided. If that happens, the node
    it is changed to dissabled
    """

    testbeds = query.get_slurm_online_testbeds()

    for testbed in testbeds:
        logging.info("Checking node info for testbed: " + testbed.name)

        nodes_from_slurm = get_nodes_testbed(testbed)
        nodes_names_from_slurm = [x['node_name'] for x in nodes_from_slurm]
        nodes_names_from_db = []
        nodes_ids = []
        for node in testbed.nodes:
            nodes_names_from_db.append(node.name)
            nodes_ids.append({'name' : node.name, 'id': node.id})

        nodes_in_slurm_and_db = set(nodes_names_from_slurm).intersection(set(nodes_names_from_db))
        nodes_in_slurm_and_not_in_db = set(nodes_names_from_slurm).difference(set(nodes_names_from_db))
        nodes_in_db_and_not_in_slurm = set(nodes_names_from_db).difference(set(nodes_names_from_slurm))

        # We add new nodes if not previously present in the db
        for node in nodes_in_slurm_and_not_in_db:
            logging.info("Adding a new node: " + node + " to testbed: " + testbed.name)
            new_node = Node(name = node, information_retrieved = True)
            testbed.add_node(new_node)
            db.session.commit()

        # We check that the nodes in the db are updated if necessary
        for node in nodes_in_slurm_and_db:
            interested_nodes = [d for d in nodes_ids if d['name'] == node]

            for node_id in interested_nodes:
                node_from_db = db.session.query(Node).filter_by(id=node_id['id']).first()
                if node_from_db.disabled:
                    logging.info("Enabling node: " + node)
                    node_from_db.disabled = False
                    db.session.commit()

        # We check that the nodes not returned by slurm are set to 0
        for node in nodes_in_db_and_not_in_slurm:
            interested_nodes = [d for d in nodes_ids if d['name'] == node]

            for node_id in interested_nodes:
                node_from_db = db.session.query(Node).filter_by(id=node_id['id']).first()

                if not node_from_db.disabled:
                    logging.info("Disabling node: " + node)
                    node_from_db.disabled = True
                    db.session.commit()

def  update_cpu_node_information():
    """
    This method updates the CPU information of nodes in case of
    on-line SLURM testbeds.

    It is going to try to ssh into the node, if the node is enabled, if an
    error occours it keeps the node information as it is. If no error occours
    updates the entries in the db deleting the old CPU information first.
    """

    testbeds = query.get_slurm_online_testbeds()

    for testbed in testbeds:
        for node in testbed.nodes:
            if not node.disabled:
                cpus = parser.get_cpuinfo_node(testbed, node)

                if cpus != []:
                    logging.info("Updating CPU info for node: " + node.name)
                    db.session.query(CPU).filter_by(node_id=node.id).delete()
                    node.cpus = cpus
                    db.session.commit()
                else:
                    logging.error("Impossible to update CPU info for node: " + node.name)
