#
# Copyright 2018 Atos Research and Innovation
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# https://www.gnu.org/licenses/agpl-3.0.txt
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
# 
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Unit tests that checks ALDE application execution code
#

import executor
import os
import slurm
import shell
import unittest.mock as mock
from sqlalchemy_mapping_tests.mapping_tests import MappingTest
from models import db, Execution, Deployment, ExecutionConfiguration, Testbed, Executable, ExecutionConfiguration, Application, Node
from uuid import UUID
from unittest.mock import call
from testfixtures import LogCapture

class ExecutorTests(MappingTest):
	"""
	Unit test for the package Executor in charge of executing an application
	"""

	@mock.patch("shell.execute_command")
	@mock.patch("shell.scp_file")
	def test_upload_deployment(self, mock_scp, mock_execute):
		""" Verifies that the upload of the deployment works """

		executable = Executable()
		executable.source_code_file = 'source'
		executable.compilation_script = 'script'
		executable.compilation_type = 'TYPE'
		testbed = Testbed("nova", True, "SLURM", "SSH", "pepito@ssh.com", [ "SINGULARITY" ] )

		executor.upload_deployment(executable, testbed)

		self.assertFalse(mock_scp.called)
		self.assertFalse(mock_execute.called)

		executable = Executable()
		executable.source_code_file = 'source'
		executable.compilation_script = 'script'
		executable.compilation_type = "SINGULARITY:PM"
		testbed = Testbed("nova", True, "SLURM", "SSH", "pepito@ssh.com", [ "SBATCH" ] )

		executor.upload_deployment(executable, testbed)

		self.assertFalse(mock_scp.called)
		self.assertFalse(mock_execute.called)

		executable = Executable()
		executable.source_code_file = 'source'
		executable.compilation_script = 'script'
		executable.compilation_type = "SINGULARITY:PM"
		testbed = Testbed("nova", True, "SLURM", "SSH", "pepito@ssh.com", [ "SINGULARITY" ] )
		executable.status = Executable.__status_compiled__
		executable.singularity_image_file='/tmp/file.img'
		db.session.add(executable)
		db.session.add(testbed)
		db.session.commit()

		deployment = Deployment()
		deployment.executable_id = executable.id
		deployment.testbed_id = testbed.id

		db.session.add(deployment)
		db.session.commit()

		executor.upload_deployment(executable, testbed)
		deployment = db.session.query(Deployment).filter_by(executable_id=executable.id, testbed_id=testbed.id).first()

		path = deployment.path[:36] # Extracting the UUID
		try:
			val = UUID(path, version=4)
		except ValueError:
			self.fail("Filname is not uuid4 complaint: " + path)

		self.assertEquals(Deployment.__status_uploaded_updated__, deployment.status)

		# We verify the calls to shell
		mock_execute.assert_called_with('mkdir', testbed.endpoint, [ path ])
		mock_scp.assert_called_with(executable.singularity_image_file, testbed.endpoint, path + "/")

	@mock.patch("torque.execute_batch")
	@mock.patch("executor.execute_application_type_pm")
	@mock.patch("executor.execute_application_type_slurm_srun")
	@mock.patch("executor.execute_application_type_singularity_srun")
	@mock.patch("executor.execute_application_type_singularity_pm")
	@mock.patch("executor.execute_application_type_slurm_sbatch")
	def test_execute_application(self, mock_slurm_sbatch, mock_singularity, mock_singularity_srun, mock_slurm_srun, mock_pm, mock_torque_qsub):
		"""
		Verifies that the right methods and status are set when an appplication is executed
		"""

		execution_configuration = ExecutionConfiguration()
		execution_configuration.execution_type = "SLURM:SBATCH"
		db.session.add(execution_configuration)
		db.session.commit()

		t = executor.execute_application(execution_configuration, False)

		execution = db.session.query(Execution).filter_by(execution_type="SLURM:SBATCH").first()
		self.assertEquals("SLURM:SBATCH", execution.execution_type)
		self.assertEquals(executor.execute_status_submitted, execution.status)

		# We verify that the right method was called
		t.join()
		mock_slurm_sbatch.assert_called_with(execution,  execution_configuration.id)

		execution_configuration.execution_type = "SINGULARITY:PM"
		db.session.commit()

		t = executor.execute_application(execution_configuration, False)
		execution = db.session.query(Execution).filter_by(execution_type="SINGULARITY:PM").first()
		self.assertEquals("SINGULARITY:PM", execution.execution_type)
		self.assertEquals(executor.execute_status_submitted, execution.status)

		# We verify that the right method was called
		t.join()
		mock_singularity.assert_called_with(execution, execution_configuration.id, False, False, '/profile_folder')

		# # PM
		# execution_configuration.execution_type = "PM"
		# db.session.commit()

		# t = executor.execute_application(execution_configuration, False)
		# execution = db.session.query(Execution).filter_by(execution_type="PM").first()
		# self.assertEquals("PM", execution.execution_type)
		# self.assertEquals(executor.execute_status_submitted, execution.status)

		# # We verify that the right method was called
		# t.join()
		# mock_pm.assert_called_with(execution, execution_configuration.id, False, False, '/profile_folder')

		# SINGULARITY:SRUN
		execution_configuration.execution_type = "SINGULARITY:SRUN"
		db.session.commit()

		t = executor.execute_application(execution_configuration, False)
		execution = db.session.query(Execution).filter_by(execution_type="SINGULARITY:SRUN").first()
		self.assertEquals("SINGULARITY:SRUN", execution.execution_type)
		self.assertEquals(executor.execute_status_submitted, execution.status)

		# We verify that the right method was called
		t.join()
		mock_singularity_srun.assert_called_with(execution, execution_configuration.id)

		# SLURM:SRUN
		execution_configuration.execution_type = "SLURM:SRUN"
		db.session.commit()

		t = executor.execute_application(execution_configuration, False)
		execution = db.session.query(Execution).filter_by(execution_type="SLURM:SRUN").first()
		self.assertEquals("SLURM:SRUN", execution.execution_type)
		self.assertEquals(executor.execute_status_submitted, execution.status)

		# We verify that the right method was called
		t.join()
		mock_slurm_srun.assert_called_with(execution, execution_configuration.id)

		# We verify the wrong status of unrecognize execution type
		execution_configuration.execution_type = "xxx"
		db.session.commit()

		executor.execute_application(execution_configuration, False)

		execution = db.session.query(Execution).filter_by(execution_type="xxx").first()
		self.assertEquals("xxx", execution.execution_type)
		self.assertEquals(executor.execute_status_failed, execution.status)
		self.assertEquals("No support for execurtion type: xxx", execution.output)

		# TORQUE:QSUB
		execution_configuration.execution_type = Executable.__type_torque_qsub__
		db.session.commit()

		t = executor.execute_application(execution_configuration, False)
		execution = db.session.query(Execution).filter_by(execution_type=Executable.__type_torque_qsub__).first()
		self.assertEqual(Executable.__type_torque_qsub__, execution.execution_type)
		self.assertEqual(Execution.__status_submitted__, execution.status)

		# We verify that the right method was called
		t.join()
		mock_torque_qsub.assert_called_with(execution, execution_configuration.id)

		# We verify the wrong status of unrecognize execution type
		execution_configuration.execution_type = "xxx"
		db.session.commit()

		executor.execute_application(execution_configuration, False)

		execution = db.session.query(Execution).filter_by(execution_type="xxx").first()
		self.assertEquals("xxx", execution.execution_type)
		self.assertEquals(Execution.__status_failed__, execution.status)
		self.assertEquals("No support for execurtion type: xxx", execution.output)

	@mock.patch("executor_common.add_nodes_to_execution")
	@mock.patch("shell.execute_command")
	def test_execute_application_type_singularity_pm(self, mock_shell, mock_add_nodes):
		"""
		It verifies the correct work of the function:
		execute_application_type_singularity_pm
		"""

		# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="SLURM",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() # So application and testbed get an id

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SINGULARITY:PM"
		executable.singularity_app_folder="/singularity/app/folder"
		executable.singularity_image_file="pepito.img"
		executable.status = "COMPILED"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		deployment.path="/pepito/pepito.img"
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SINGULARITY:PM"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 1
		execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 12
		execution_config.exec_time = 10 
		execution_config.command = "/apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_ejarquej/demo_test/cpu_gpu_run_data"
		execution_config.compss_config = "--worker_in_master_cpus=12 --worker_in_master_memory=24000 --worker_working_dir=/home_nfs/home_ejarquej --lang=c --monitoring=1000 -d"
		db.session.add(execution_config)
		db.session.commit()

		output = b'COMPSS_HOME=/home_nfs/home_ejarquej/installations/rc1707/COMPSs\nSC Configuration:          nova.cfg\nQueue:                     default\nReservation:               disabled\nNum Nodes:                 1\nNum Switches:              0\nGPUs per node:             2\nJob dependency:            None\nExec-Time:                 00:10:00\nStorage Home:              null\nStorage Properties:        \nOther:                     --sc_cfg=nova.cfg\n\t\t\t--gpus_per_node=2\n\t\t\t--cpus_per_node=12\n\t\t\t--container_image=/tmp/d96d4766-6612-414d-bf5e-0c043a3f30c3.img\n\t\t\t--container_compss_path=/opt/TANGO/TANGO_ProgrammingModel/COMPSs/\n\t\t\t--appdir=/apps/application/\n\t\t\t--worker_in_master_cpus=12\n\t\t\t--worker_in_master_memory=24000\n\t\t\t--worker_working_dir=/home_nfs/home_garciad\n\t\t\t--lang=c\n\t\t\t--monitoring=1000 -d /apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_garciad/demo_test/cpu_gpu_run_data\n \nTemp submit script is: /tmp/tmp.y7WxtgjPSz\nRequesting 2 processes\nSubmitted batch job 3357\n'

		mock_shell.return_value = output

		# TEST starts here:
		execution = Execution()
		execution.execution_type = execution_config.execution_type
		execution.status = executor.execute_status_submitted
		executor.execute_application_type_singularity_pm(execution, execution_config.id)

		mock_shell.assert_called_with("source",
									  "user@testbed.com",
									  [
									  	"/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv",
										";",
										"enqueue_compss",
										"--sc_cfg=nova.cfg",
										"--num_nodes=1",
										"--gpus_per_node=2",
										"--cpus_per_node=12",
										"--container_image=/pepito/pepito.img",
										"--container_compss_path=/opt/TANGO/TANGO_ProgrammingModel/COMPSs/",
										"--appdir=/apps/application/",
										"--exec_time=10",
										"--worker_in_master_cpus=12 --worker_in_master_memory=24000 --worker_working_dir=/home_nfs/home_ejarquej --lang=c --monitoring=1000 -d",
										"/apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_ejarquej/demo_test/cpu_gpu_run_data"
									   ]
									  )

		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_config.id).first()

		self.assertEquals(execution.execution_type, execution_config.execution_type)
		self.assertEquals(execution.status, Execution.__status_running__)
		self.assertEquals(3357, execution.batch_id)

		mock_add_nodes.assert_called_with(execution, "user@testbed.com")

		# TEST with profile
		# TEST starts here:
		execution_config.profile_file = "/tmp/surperprofile.profile"
		db.session.commit()

		execution = Execution()
		execution.execution_type = execution_config.execution_type
		execution.status = executor.execute_status_submitted
		executor.execute_application_type_singularity_pm(execution, execution_config.id, use_storage_profile=True)

		mock_shell.assert_called_with("source",
									  "user@testbed.com",
									  [
									  	"/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv",
										";",
										"enqueue_compss",
										"--sc_cfg=nova.cfg",
										"--num_nodes=1",
										"--gpus_per_node=2",
										"--cpus_per_node=12",
										"--container_image=/pepito/pepito.img",
										"--container_compss_path=/opt/TANGO/TANGO_ProgrammingModel/COMPSs/",
										"--appdir=/apps/application/",
										"--exec_time=10",
										"--input_profile=/tmp/surperprofile.profile",
										"--worker_in_master_cpus=12 --worker_in_master_memory=24000 --worker_working_dir=/home_nfs/home_ejarquej --lang=c --monitoring=1000 -d",
										"/apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_ejarquej/demo_test/cpu_gpu_run_data"
									   ]
									  )

	def test__extract_id_from_sigularity_pm_app__(self):
		"""
		Test the correct work of the method: __extract_id_from_sigularity_pm_app__
		"""

		output = b'COMPSS_HOME=/home_nfs/home_ejarquej/installations/rc1707/COMPSs\nSC Configuration:          nova.cfg\nQueue:                     default\nReservation:               disabled\nNum Nodes:                 1\nNum Switches:              0\nGPUs per node:             2\nJob dependency:            None\nExec-Time:                 00:10:00\nStorage Home:              null\nStorage Properties:        \nOther:                     --sc_cfg=nova.cfg\n\t\t\t--gpus_per_node=2\n\t\t\t--cpus_per_node=12\n\t\t\t--container_image=/tmp/d96d4766-6612-414d-bf5e-0c043a3f30c3.img\n\t\t\t--container_compss_path=/opt/TANGO/TANGO_ProgrammingModel/COMPSs/\n\t\t\t--appdir=/apps/application/\n\t\t\t--worker_in_master_cpus=12\n\t\t\t--worker_in_master_memory=24000\n\t\t\t--worker_working_dir=/home_nfs/home_garciad\n\t\t\t--lang=c\n\t\t\t--monitoring=1000 -d /apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_garciad/demo_test/cpu_gpu_run_data\n \nTemp submit script is: /tmp/tmp.y7WxtgjPSz\nRequesting 2 processes\nSubmitted batch job 3357\n'

		sbatch_id = executor.__extract_id_from_sigularity_pm_app__(output)

		self.assertEquals(3357, sbatch_id)

		output = b'COMPSS_HOME=/home_nfs/home_ejarquej/installations/rc1707/COMPSs\nSC Configuration:          nova.cfg\nQueue:                     default\nReservation:               disabled\nNum Nodes:                 1\nNum Switches:              0\nGPUs per node:             2\nJob dependency:            None\nExec-Time:                 00:10:00\nStorage Home:              null\nStorage Properties:        \nOther:                     --sc_cfg=nova.cfg\n\t\t\t--gpus_per_node=2\n\t\t\t--cpus_per_node=12\n\t\t\t--container_image=/tmp/d96d4766-6612-414d-bf5e-0c043a3f30c3.img\n\t\t\t--container_compss_path=/opt/TANGO/TANGO_ProgrammingModel/COMPSs/\n\t\t\t--appdir=/apps/application/\n\t\t\t--worker_in_master_cpus=12\n\t\t\t--worker_in_master_memory=24000\n\t\t\t--worker_working_dir=/home_nfs/home_garciad\n\t\t\t--lang=c\n\t\t\t--monitoring=1000 -d /apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_garciad/demo_test/cpu_gpu_run_data\n \nTemp submit script is: /tmp/tmp.y7WxtgjPSz\nRequesting 2 processes\nSubmitted batch job     3357    \n\n\n'

		sbatch_id = executor.__extract_id_from_sigularity_pm_app__(output)

		self.assertEquals(3357, sbatch_id)

	@mock.patch("executor_common.add_nodes_to_execution")
	@mock.patch("shell.execute_command")
	def test_execute_application_type_slurm_sbatch(self, mock_shell, mock_add_nodes):
		"""
		It verifies that the application type slurm sbatch is executed
		"""

		# First we verify that the testbed is of type SLURM to be able
		# to execute it, in this case it should give an error since it is
		# not of type slurm

		# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="xxxx",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() # So application and testbed get an id

		executable = Executable()
		executable.compilation_type = "SLURM:SBATCH"
		executable.executable_file = "pepito.sh"
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type = "SLURM:SBATCH"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		db.session.add(execution_config)
		db.session.commit()

		execution = Execution()
		execution.execution_type = "SLURM:SBATCH"
		execution.status =  executor.execute_status_submitted

		executor.execute_application_type_slurm_sbatch(execution, execution_config.id)

		self.assertEquals("SLURM:SBATCH", execution.execution_type)
		self.assertEquals(executor.execute_status_failed, execution.status)
		self.assertEquals("Testbed does not support SLURM:SBATCH applications", execution.output)

		# If the testbed is off-line, execution isn't allowed also
		testbed.category = Testbed.slurm_category
		testbed.on_line = False
		db.session.commit()

		execution.status = executor.execute_status_submitted

		execution = Execution()
		execution.execution_type = "SLURM:SBATCH"
		execution.status = executor.execute_status_submitted

		executor.execute_application_type_slurm_sbatch(execution, execution_config.id)

		self.assertEquals("SLURM:SBATCH", execution.execution_type)
		self.assertEquals(executor.execute_status_failed, execution.status)
		self.assertEquals("Testbed is off-line", execution.output)

		## Test executing
		output = b'Submitted batch job 5740'
		mock_shell.return_value = output

		testbed.category = Testbed.slurm_category
		testbed.on_line = True
		db.session.commit()

		execution.status = executor.execute_status_submitted

		execution = Execution()
		execution.execution_type = "SLURM:SBATCH"
		execution.status = executor.execute_status_submitted

		executor.execute_application_type_slurm_sbatch(execution, execution_config.id)

		mock_shell.assert_called_with("sbatch",
									  "user@testbed.com",
									  [
									  	"pepito.sh"
									   ]
									  )
		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_config.id).first()
		self.assertEquals(execution.execution_type, execution_config.execution_type)
		self.assertEquals(execution.status, Execution.__status_running__)
		self.assertEquals(5740, execution.batch_id)

		mock_add_nodes.assert_called_with(execution, "user@testbed.com")

	@mock.patch("executor.monitor_execution_singularity_apps")
	def test_monitor_execution_apps(self, mock_monitor):
		"""
		It verifies that the method that monitors the execution of apps
		works as expected
		"""

		testbed = Testbed('name', True, 'category', 'protocol', 'endpoint')
		db.session.add(testbed)
		
		execution_configuration = ExecutionConfiguration()
		execution_configuration.testbed = testbed
		db.session.add(execution_configuration)

		execution_1 = Execution()
		execution_1.execution_type = "typeX"
		execution_1.status = Execution.__status_running__
		execution_1.execution_configuration = execution_configuration
		execution_2 = Execution()
		execution_2.execution_type = Executable.__type_singularity_pm__
		execution_2.status = Execution.__status_finished__
		execution_2.execution_configuration = execution_configuration
		execution_3 = Execution()
		execution_3.execution_type = Executable.__type_singularity_pm__
		execution_3.status = Execution.__status_running__
		execution_3.execution_configuration = execution_configuration
		execution_4 = Execution()
		execution_4.execution_type = Executable.__type_torque_qsub__
		execution_4.status = Execution.__status_running__
		execution_4.execution_configuration = execution_configuration

		mock_monitor.return_value = 'pepito'

		db.session.add(execution_1)
		db.session.add(execution_2)
		db.session.add(execution_3)
		db.session.add(execution_4)
		db.session.commit()

		executor.monitor_execution_apps()
		mock_monitor.assert_any_call(execution_3)
		mock_monitor.assert_any_call(execution_4)

		self.assertEquals('pepito', execution_3.status)


	@mock.patch("executor._parse_sacct_output")
	def test_monitor_execution_singularity_apps(self, mock_parse):
		"""
		It checks that the monitoring of singularity apps 
		is working
		"""

		execution = Execution()
		execution.execution_type = "typeX"
		execution.status = "xxx"
		execution.batch_id = 1
		execution_configuration = ExecutionConfiguration()
		execution.execution_configuration=execution_configuration
		testbed = Testbed("name", True, Testbed.slurm_category, "ssh", "user@server", ['slurm'])
		execution_configuration.testbed=testbed

		mock_parse.return_value = '?'

		status = executor.monitor_execution_singularity_apps(execution)

		self.assertEquals("xxx", status)

		mock_parse.return_value = 'RUNNING'

		status = executor.monitor_execution_singularity_apps(execution)

		self.assertEquals("RUNNING", status)

		call_1 = call(1,"user@server")
		call_2 = call(1,"user@server")
		calls = [ call_1, call_2, ]
		mock_parse.assert_has_calls(calls)

	@mock.patch("shell.execute_command")
	def test_parse_sacct_output(self, mock_shell):
		"""
		It checks that the monitoring of singularity apps 
		is working

		Command to be executed:

		[garciad@ns54 ~]$ sacct -j 4340 -o JobID,NNodes,State,ExitCode,DerivedExitcode,Comment
		JobID   NNodes      State ExitCode DerivedExitCode        Comment 
		------------ -------- ---------- -------- --------------- -------------- 
		4340                1  COMPLETED      0:0             1:0                
		4340.batch          1  COMPLETED      0:0                                
		4340.0              1  COMPLETED      0:0                                
		4340.1              1     FAILED      1:0 
		"""

		# TEST NO OUTPUT
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- '

		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('?', status)

		# TEST RUNNING
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- \n4340                1  RUNNING      0:0             0:0                \n4340.batch          1  COMPLETED      0:0                                \n4340.0              1  COMPLETED      0:0                                \n4340.1              1     COMPLETED      0:0 '
		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('RUNNING', status)

		# TEST COMPLETED
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- \n4340                1  COMPLETED      0:0             0:0                \n4340.batch          1  COMPLETED      0:0                                \n4340.0              1  COMPLETED      0:0                                \n4340.1              1     COMPLETED      0:0 '

		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('COMPLETED', status)

		# TEST FAILED
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- \n4340                1  COMPLETED      0:0             1:0                \n4340.batch          1  COMPLETED      0:0                                \n4340.0              1  COMPLETED      0:0                                \n4340.1              1     FAILED      1:0 '

		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('FAILED', status)

		# TEST UNKNOWN
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- \n4340                1  UNKNOWN      0:0             1:0                \n4340.batch          1  UNKNOWN      0:0                                \n4340.0              1  UNKNOWN      0:0                                \n4340.1              1     UNKNOWN      1:0 '

		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('UNKNOWN', status)

		# TEST TIMEOUT
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- \n4340                1  UNKNOWN      0:0             1:0                \n4340.batch          1  TIMEOUT      0:0                                \n4340.0              1  UNKNOWN      0:0                                \n4340.1              1     UNKNOWN      1:0 '

		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('TIMEOUT', status)

		# TEST CANCELLED
		output = b'       JobID   NNodes      State ExitCode DerivedExitCode        Comment \n------------ -------- ---------- -------- --------------- -------------- \n4340                1  CANCELLED      0:0             1:0                \n4340.batch          1  UNKNOWN      0:0                                \n4340.0              1  UNKNOWN      0:0                                \n4340.1              1     UNKNOWN      1:0 '

		mock_shell.return_value = output

		status = executor._parse_sacct_output(4340, 'test@pepito.com')

		self.assertEquals('CANCELLED', status)

		call_1 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		call_2 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		call_3 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		call_4 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		call_5 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		call_6 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		call_7 = call('sacct', server='test@pepito.com', params=['-j', 4340, '-o', 'JobID,NNodes,State,ExitCode,DerivedExitcode,Comment'])
		calls = [ call_1, call_2, call_3, call_4, call_5, call_6, call_7]
		mock_shell.assert_has_calls(calls)

	def test__extract_id_from_squeue__(self):
		"""
		Test that it is possible to extract the id from the first squeue output
		"""

		# example output
		output = b'             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n              4610       all singular  garciad  R       0:01      2 ns[55-56]\n'

		squeue_id = executor.__extract_id_from_squeue__(output)

		self.assertEquals(4610, squeue_id)

	@mock.patch("executor_common.add_nodes_to_execution")
	@mock.patch("slurm.execute_srun")
	def test_execute_application_type_singularity_srun(self, mock_slurm, mock_add_nodes):
		"""
		Test the correct work fo this function
		"""

		# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="SLURM",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() # So application and testbed get an id

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SINGULARITY:SRUN"
		executable.singularity_app_folder="/singularity/app/folder"
		executable.singularity_image_file="pepito.img"
		executable.status = "COMPILED"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		deployment.path="/pepito/pepito.img"
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SINGULARITY:SRUN"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 2
		#execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.exec_time = 10 
		execution_config.command = "/apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_ejarquej/demo_test/cpu_gpu_run_data"
		execution_config.compss_config = "--worker_in_master_cpus=12 --worker_in_master_memory=24000 --worker_working_dir=/home_nfs/home_ejarquej --lang=c --monitoring=1000 -d"
		db.session.add(execution_config)
		db.session.commit()

		output = b'             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n              4610       all singular  garciad  R       0:01      2 ns[55-56]\n'

		mock_slurm.return_value = output

		# TEST starts here:
		execution = Execution()
		execution.execution_type = execution_config.execution_type
		execution.status = executor.execute_status_submitted
		executor.execute_application_type_singularity_srun(execution, execution_config.id)

		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_config.id).first()

		self.assertEquals(execution.execution_type, execution_config.execution_type)
		self.assertEquals(execution.status, Execution.__status_running__)
		self.assertEquals(4610, execution.batch_id)

		call_1 = call(testbed, execution_config, executable, deployment, True)

		# adding a new type of execution
		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SINGULARITY:SRUN"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.exec_time = 10 
		execution_config.command = "/apps/application/master/Matmul 2 1024 12.34 /home_nfs/home_ejarquej/demo_test/cpu_gpu_run_data"
		execution_config.compss_config = "--worker_in_master_cpus=12 --worker_in_master_memory=24000 --worker_working_dir=/home_nfs/home_ejarquej --lang=c --monitoring=1000 -d"
		db.session.add(execution_config)
		db.session.commit()

		execution = Execution()
		execution.execution_type = execution_config.execution_type
		execution.status = executor.execute_status_submitted
		executor.execute_application_type_singularity_srun(execution, execution_config.id)

		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_config.id).first()

		self.assertEquals(execution.execution_type, execution_config.execution_type)
		self.assertEquals(execution.status, Execution.__status_running__)
		self.assertEquals(4610, execution.batch_id)

		call_2 = call(testbed, execution_config, executable, deployment, True)
		calls = [ call_1, call_2]
		mock_slurm.assert_has_calls(calls)
		mock_add_nodes.assert_called_with(execution, "user@testbed.com")

	@mock.patch("executor_common.add_nodes_to_execution")
	@mock.patch("shell.execute_command")
	def test_execute_application_type_slurm_srun(self, mock_shell, mock_add_nodes):
		"""
		Test the correct work fo this function
		"""

		# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="SLURM",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'srun', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() # So application and testbed get an id

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SLURM:SRUN"
		executable.executable_file = "/usr/local/gromacs-4.6.7-cuda2/bin/mdrun"
		executable.status = "COMPILED"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SLURM:SRUN"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 2
		#execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.srun_config = "--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1"
		execution_config.command = "-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet"
		db.session.add(execution_config)
		db.session.commit()

		output = b'             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)\n              4610       all singular  garciad  R       0:01      2 ns[55-56]\n'

		mock_shell.return_value = output

		# TEST starts here:
		execution = Execution()
		execution.execution_type = execution_config.execution_type
		execution.execution_type = executor.execute_status_submitted

		executor.execute_application_type_slurm_srun(execution, execution_config.id)

		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_config.id).first()

		self.assertEquals(execution.execution_type, execution_config.execution_type)
		self.assertEquals(execution.status, Execution.__status_running__)
		self.assertEquals(4610, execution.batch_id)

		call_1 = call('(', "user@testbed.com",
									  [
									  	'srun', 
									  	'-N', 
									  	'2', 
									  	'-n', 
									  	'16', 
									  	'--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1', 
									  	'/usr/local/gromacs-4.6.7-cuda2/bin/mdrun', 
									  	'-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet',							  	
									  	">",
										"allout.txt",
										"2>&1",
									  	"&",
									  	")",
									  	";",
									  	"sleep",
									  	"1;",
									  	"squeue"
									   ])

		# adding a new type of execution
		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SLURM:SRUN"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 2
		execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.srun_config = "--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1"
		execution_config.command = "-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet"
		db.session.add(execution_config)
		db.session.commit()

		execution.execution_type = execution_config.execution_type
		execution.status = executor.execute_status_submitted
		executor.execute_application_type_slurm_srun(execution, execution_config.id)

		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_config.id).first()

		self.assertEquals(execution.execution_type, execution_config.execution_type)
		self.assertEquals(execution.status, Execution.__status_running__)
		self.assertEquals(4610, execution.batch_id)

		call_2 = call('(', "user@testbed.com",
									  [
									  	'srun', 
									  	'-N', 
									  	'2',
									  	"--gres=gpu:2", 
									  	'-n', 
									  	'16', 
									  	'--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1', 
									  	'/usr/local/gromacs-4.6.7-cuda2/bin/mdrun', 
									  	'-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet',							  	
									  	">",
										"allout.txt",
										"2>&1",
									  	"&",
									  	")",
									  	";",
									  	"sleep",
									  	"1;",
									  	"squeue"
									   ])
		calls = [ call_1, call_2]
		mock_shell.assert_has_calls(calls)
		mock_add_nodes.assert_called_with(execution, "user@testbed.com")

	@mock.patch("shell.execute_command")
	def test_cancel_execution(self, mock_shell):
		"""
		It test the correct work of the cancel execution method
		"""

		# We create the execution objects to test
		execution_1 = Execution()
		execution_1.execution_type = Executable.__type_singularity_srun__
		execution_1.status = Execution.__status_running__
		execution_1.batch_id = 1
		execution_2 = Execution()
		execution_2.execution_type = Executable.__type_singularity_pm__
		execution_2.status = Execution.__status_running__
		execution_2.batch_id = 2
		execution_3 = Execution()
		execution_3.execution_type = "other_type"
		execution_3.status = Execution.__status_running__
		execution_3.batch_id = 3
		execution_4 = Execution()
		execution_4.execution_type = Executable.__type_singularity_pm__
		execution_4.status = Execution.__status_finished__
		execution_4.batch_id = 4
		execution_5 = Execution()
		execution_5.execution_type = Executable.__type_slurm_sbatch__
		execution_5.batch_id = 5
		execution_5.status = Execution.__status_running__


		executor.cancel_execution(execution_1, "user@testbed.com")
		executor.cancel_execution(execution_2, "user@testbed.com")
		executor.cancel_execution(execution_3, "user@testbed.com")
		executor.cancel_execution(execution_4, "user@testbed.com")
		executor.cancel_execution(execution_5, "user@testbed.com")

		execution_21 = Execution()
		execution_21.execution_type = Executable.__type_singularity_pm__
		execution_21.status = Execution.__status_running__
		execution_21.batch_id = 34

		execution_22 = Execution()
		execution_22.execution_type = Executable.__type_singularity_pm__
		execution_22.status = Execution.__status_running__
		execution_22.batch_id = 54

		execution_23 = Execution()
		execution_23.execution_type = Executable.__type_singularity_pm__
		execution_23.status = Execution.__status_running__
		execution_23.batch_id = 33

		execution_24 = Execution()
		execution_24.execution_type = Executable.__type_singularity_pm__
		execution_24.status = Execution.__status_cancel__
		execution_24.batch_id = 55

		execution_2.children = [ execution_21, execution_22, execution_23, execution_24]
		executor.cancel_execution(execution_2, "user@testbed.com")

		call_1 = call("scancel", "user@testbed.com", [ "1" ])
		call_2 = call("scancel", "user@testbed.com", [ "2" ])
		call_3 = call("scancel", "user@testbed.com", ["5"])
		call_4 = call("scancel", "user@testbed.com", [ "34" ])
		call_5 = call("scancel", "user@testbed.com", [ "54" ])
		call_6 = call("scancel", "user@testbed.com", [ "33" ])
		call_7 = call("scancel", "user@testbed.com", [ "2" ])
		calls = [ call_1, call_2, call_3, call_4, call_5, call_6, call_7 ]
		mock_shell.assert_has_calls(calls)

	@mock.patch('executor.__add_nodes_to_execution__')
	@mock.patch('executor.get_job_id_after_adaptation')
	@mock.patch('executor.find_first_node')
	@mock.patch("shell.execute_command")
	def test_add_resource(self, mock_shell, mock_find_node, mock_get_job_id, mock_add_nodes):
		"""
		It tests that it is possible to add a resource
		"""

		l = LogCapture() # we cature the logger

		# Sub test 1 - Wrong type of Execution
		execution = Execution()
		execution.execution_type = "pepito"
		execution.status = Execution.__status_running__
		executor.add_resource(execution)

		# Sub test 2 - Execution not running in right state
		execution = Execution()
		execution.execution_type = Executable.__type_singularity_pm__
		execution.status = Execution.__status_failed__
		executor.add_resource(execution)

		# Sub test 3 - Execution should get a new resource
		testbed = Testbed( "testbed", True, "nice_testbed", "ssh", "endpoint")
		extra = {'enqueue_env_file': 'source_file'}
		testbed.extra_config = extra
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() # So application and testbed get an id

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SLURM:SRUN"
		executable.executable_file = "/usr/local/gromacs-4.6.7-cuda2/bin/mdrun"
		executable.status = "COMPILED"
		executable.singularity_image_file = "image_file"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_configuration = ExecutionConfiguration()
		execution_configuration.executable = executable
		execution_configuration.application = application
		execution_configuration.testbed = testbed
		db.session.add(execution_configuration)
		db.session.commit()

		execution = Execution()
		execution.execution_type = Executable.__type_singularity_pm__
		execution.status = Execution.__status_running__
		execution.execution_configuration = execution_configuration
		execution.batch_id = 21
		db.session.add(execution)
		db.session.commit()

		mock_find_node.return_value = 'ns31'
		mock_shell.return_value = b'COMPSS_HOME=/home_nfs/home_ejarquej/installations/2.2.6/COMPSs \n [Adaptation] writting command CREATE SLURM-Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img on /fslustre/tango/matmul/log_dir/.COMPSs/7240/adaptation/command_pipe \n [Adaptation] Reading result /fslustre/tango/matmul/log_dir/.COMPSs/7240/adaptation/result_pipe \n [Adaptation] Read ACK compss15039f76-c700-44af-b451-70c80f7eae6c \n [Adaptation]'
		mock_get_job_id.return_value = '222'
		call_get_job_id_1 = call('compss15039f76-c700-44af-b451-70c80f7eae6c', 'endpoint')

		executor.add_resource(execution)

		call_1 = call('source', 'endpoint', ['source_file', ';', 'adapt_compss_resources', 'ns31', 21, 'CREATE SLURM-Cluster default', 'image_file'])
		calls = [ call_1 ]
		mock_shell.assert_has_calls(calls)
		calls_job_id = [ call_get_job_id_1 ]
		mock_get_job_id.assert_has_calls(calls_job_id)

		# We verify the execution got the extra job id
		execution = db.session.query(Execution).filter_by(execution_configuration_id=execution_configuration.id).first()
		self.assertEquals(222, execution.children[0].batch_id)
		self.assertEquals(Execution.__status_running__, execution.children[0].status)
		self.assertEquals(Executable.__type_singularity_pm__, execution.children[0].execution_type)
		self.assertEquals(execution, execution.children[0].parent)

		mock_add_nodes.assert_called_with(execution.children[0], 'endpoint')

		# We now check it works with an application upperbound
		application.scaling_upper_bound = 1
		db.session.commit()

		executor.add_resource(execution)

		
		# Checking that we are logging the correct message
		l.check(
			('root', 'INFO', 'Execution: pepito it is not compatible with add resource action'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'Execution is not in RUNNING status, no action can be done'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'Execution already reached its maximum number of extra jobs, no adaptation possible')
		)
		l.uninstall() # We uninstall the capture of the logger
  
	@mock.patch("shell.execute_command")
	def test_find_first_node(self, mock_shell):
		"""
		Verifies that it is possible to find the first node under this outputs:
		"""

		# Sub Test 1
		output = b'NODELIST\nns51\n'
		mock_shell.return_value = output

		node = executor.find_first_node(22, 'endpoint')
		self.assertEquals(node, 'ns51')

		# Sub Test 2
		output = b'NODELIST\n   ns51      \n'
		mock_shell.return_value = output

		node = executor.find_first_node(22, 'endpoint')
		self.assertEquals(node, 'ns51')

		# Sub Test 3
		output = b'NODELIST\n   ns[55-60]      \n'
		mock_shell.return_value = output

		node = executor.find_first_node(22, 'endpoint')
		self.assertEquals(node, 'ns55')

		# Sub Test 4
		output = b'NODELIST\n   ns[53-60],ns34      \n'
		mock_shell.return_value = output

		node = executor.find_first_node(22, 'endpoint')
		self.assertEquals(node, 'ns53')

		call_1 = call("squeue", "endpoint", [ '-j', 22, '-o', '%N' ])
		call_2 = call("squeue", "endpoint", [ '-j', 22, '-o', '%N' ])
		call_3 = call("squeue", "endpoint", [ '-j', 22, '-o', '%N' ])
		call_4 = call("squeue", "endpoint", [ '-j', 22, '-o', '%N' ])
		calls = [ call_1, call_2, call_3, call_4 ]
		mock_shell.assert_has_calls(calls)

	@mock.patch("shell.execute_command")
	def test_get_job_id_after_adaptation(self, mock_shell):
		"""
		It tests the correct work of the execution of the following command
		squeue --name=job_name -h -o %A
		"""

		# Test 1
		output = b'7241\n'
		mock_shell.return_value = output
		call_mock_shell_1 = call("squeue", "endpoint", [ '--name=job_name_1', '-h', '-o', '%A' ])

		identifier = executor.get_job_id_after_adaptation("job_name_1", "endpoint")
		self.assertEquals('7241', identifier)

		# Test 2
		output = b'     7241      \n'
		mock_shell.return_value = output
		call_mock_shell_2 = call("squeue", "endpoint", [ '--name=job_name_2', '-h', '-o', '%A' ])

		identifier = executor.get_job_id_after_adaptation("job_name_2", "endpoint")
		self.assertEquals('7241', identifier)

		# Test 3
		output = b'\n'
		mock_shell.return_value = output
		call_mock_shell_3 = call("squeue", "endpoint", [ '--name=job_name_3', '-h', '-o', '%A' ])

		identifier = executor.get_job_id_after_adaptation("job_name_3", "endpoint")
		self.assertEquals('', identifier)

		# We verify all the calls to the mock
		calls = [ call_mock_shell_1, call_mock_shell_2, call_mock_shell_3]
		mock_shell.assert_has_calls(calls)

	def test_parse_add_resource_output(self):
		"""
		Checks that the parser to get the job name
		of COMPSs output when adding a resource works as expected
		"""
		
		output = b'COMPSS_HOME=/home_nfs/home_ejarquej/installations/2.2.6/COMPSs \n [Adaptation] writting command CREATE SLURM-Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img on /fslustre/tango/matmul/log_dir/.COMPSs/7240/adaptation/command_pipe \n [Adaptation] Reading result /fslustre/tango/matmul/log_dir/.COMPSs/7240/adaptation/result_pipe \n [Adaptation] Read ACK compss15039f76-c700-44af-b451-70c80f7eae6c \n [Adaptation]'
		output = executor.parse_add_resource_output(output)
		self.assertEquals('compss15039f76-c700-44af-b451-70c80f7eae6c', output)

		output = b'COMPSS_HOME=/home_nfs/home_ejarquej/installations/2.2.6/COMPSs \n [Adaptation] writting command CREATE SLURM-Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img on /fslustre/tango/matmul/log_dir/.COMPSs/7240/adaptation/command_pipe \n [Adaptation] Reading result /fslustre/tango/matmul/log_dir/.COMPSs/7240/adaptation/result_pipe \n [Adaptation] Read A\n [Adaptation]'
		output = executor.parse_add_resource_output(output)
		self.assertEquals('', output)

	def test_id_to_remove(self):
		"""
		It tests the correct work of executor.id_to_remove method
		"""

		ids = ''

		id_returned, ids = executor.id_to_remove(ids)
		self.assertIsNone(id_returned)
		self.assertEquals('', ids)

		ids = None
		id_returned, ids = executor.id_to_remove(ids)
		self.assertIsNone(id_returned)
		self.assertIsNone(ids)

		ids = '23 33 43'
		id_returned, ids = executor.id_to_remove(ids)
		self.assertEquals('43', id_returned)
		self.assertEquals('23 33', ids)

		ids = '23'
		id_returned, ids = executor.id_to_remove(ids)
		self.assertEquals('23', id_returned)
		self.assertEquals('', ids)

	@mock.patch('executor.find_first_node')
	@mock.patch("shell.execute_command")
	def test_remove_resource(self, mock_shell, mock_first_node): 
		"""
		It tests that it is possible to add a resource
		"""

		l = LogCapture() # we cature the logger

		# Sub test 1 - Wrong type of Execution
		execution = Execution()
		execution.execution_type = "pepito"
		execution.status = Execution.__status_running__
		executor.remove_resource(execution)

		# Sub test 2 - Execution not running in right state
		execution = Execution()
		execution.execution_type = Executable.__type_singularity_pm__
		execution.status = Execution.__status_failed__
		executor.remove_resource(execution)

		# Sub test 3 - Execution should try to remove a new resource but it is not possible
		testbed = Testbed( "testbed", True, "nice_testbed", "ssh", "endpoint")
		extra = {'enqueue_env_file': 'source_file'}
		testbed.extra_config = extra
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() # So application and testbed get an id

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SLURM:SRUN"
		executable.executable_file = "/usr/local/gromacs-4.6.7-cuda2/bin/mdrun"
		executable.status = "COMPILED"
		executable.singularity_image_file = "image_file"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_configuration = ExecutionConfiguration()
		execution_configuration.executable = executable
		execution_configuration.application = application
		execution_configuration.testbed = testbed
		db.session.add(execution_configuration)
		db.session.commit()

		execution = Execution()
		execution.execution_type = Executable.__type_singularity_pm__
		execution.status = Execution.__status_running__
		execution.execution_configuration = execution_configuration
		execution.batch_id = 21
		db.session.add(execution)
		db.session.commit()

		executor.remove_resource(execution)

		# Sub text 4 - Trying to remove a resource but we get an error
		db.session.add(execution)
		db.session.commit()
		child_1 = Execution()
		child_1.batch_id = 34
		child_1.status = Execution.__status_running__
		execution.children.append(child_1)
		child_2 = Execution()
		child_2.batch_id = 35
		child_2.status = Execution.__status_running__
		execution.children.append(child_2)
		db.session.commit()
		

		mock_shell.return_value = b'Something\n fishy\n happening here...'
		mock_first_node.return_value = 'ns31'

		executor.remove_resource(execution)
		
		call_1 = call('source', 'endpoint', ['source_file', ';', 'adapt_compss_resources', 'ns31', 21, 'REMOVE SLURM-Cluster', 'ns31'])

		# Sub text 5 - Now wverything should wokr
		mock_shell.return_value = b'Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img\n     COMPSS_HOME=/home_nfs/home_ejarquej/installations/2.2.6/COMPSs\n     [Adaptation] writting command CREATE SLURM-Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img on /fslustre/tango/matmul/log_dir/.COMPSs/7065/adaptation/command_pipe\n     [Adaptation] Reading result /fslustre/tango/matmul/log_dir/.COMPSs/7065/adaptation/result_pipe\n     [Adaptation] Read ACK\n    [Adaptation]'
		
		executor.remove_resource(execution)
		execution = db.session.query(Execution).filter_by(batch_id=35).first()
		self.assertEquals(Execution.__status_cancelled__, execution.status)

		calls = [ call_1, call_1 ]
		mock_shell.assert_has_calls(calls)

		call_first_node_1 = call(21, 'endpoint')
		call_first_node_2 = call(35, 'endpoint')
		call_first_node_3 = call(21, 'endpoint')
		call_first_node_4 = call(35, 'endpoint')
		calls = [call_first_node_1, call_first_node_2, call_first_node_3, call_first_node_4]
		mock_first_node.assert_has_calls(calls)
		
		# Checking that we are logging the correct message
		l.check(
			('root', 'INFO', 'Execution: pepito it is not compatible with add resource action'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'Execution is not in RUNNING status, no action can be done'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'No extra jobs to be able to delete'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'There was an error in the adaptation:'),
 			('root', 'INFO', 'Something\n fishy\n happening here...'),
			('root', 'INFO', 'Executing type corresponds with SINGULARITY_PM, trying adaptation'),
			('root', 'INFO', 'Adaptation performed ok')
		)
		l.uninstall() # We uninstall the capture of the logger

	def test_verify_adaptation_went_ok(self):
		"""
		Verifies the correct work of the method verify_adaptation_went_ok
		"""

		not_ok = b'Something\n fishy\n happening here...'
		ok = b'Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img\n     COMPSS_HOME=/home_nfs/home_ejarquej/installations/2.2.6/COMPSs\n     [Adaptation] writting command CREATE SLURM-Cluster default /home_nfs/home_ejarquej/matmul-cuda8-y3.img on /fslustre/tango/matmul/log_dir/.COMPSs/7065/adaptation/command_pipe\n     [Adaptation] Reading result /fslustre/tango/matmul/log_dir/.COMPSs/7065/adaptation/result_pipe\n     [Adaptation] Read ACK\n    [Adaptation]'

		self.assertFalse(executor.verify_adaptation_went_ok(not_ok))
		self.assertTrue(executor.verify_adaptation_went_ok(ok))

	@mock.patch("shell.execute_command")
	def test__add_nodes_to_execution__(self, mock_shell):
		"""
		It checks the correct work of the method add nodes to Execution
		"""

		# We need to add some nodes for example that this work as expected
		node_1 = Node()
		node_1.name = "node1"
		db.session.add(node_1)
		node_2 = Node()
		node_2.name = "node2"
		db.session.add(node_2)
		node_50 = Node()
		node_50.name = "node50"
		db.session.add(node_50)
		node_51 = Node()
		node_51.name = "node51"
		db.session.add(node_51)
		node_52 = Node()
		node_52.name = "node52"
		db.session.add(node_52)
		node_53 = Node()
		node_53.name = "node53"
		db.session.add(node_53)
		node_54 = Node()
		node_54.name = "node54"
		db.session.add(node_54)
		node_55 = Node()
		node_55.name = "node55"
		db.session.add(node_55)

		execution = Execution()
		execution.status = Execution.__status_cancel__
		db.session.add(execution)
		db.session.commit()

		# TEST - No node should be added
		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(0, len(execution.nodes))

		# TEST - No node should be added
		mock_shell.return_value = b'\n'
		execution.batch_id = ''
		execution.status = Execution.__status_running__
		db.session.commit()

		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(0, len(execution.nodes))
		call_1 = call('squeue',  'endpoint', [ '-j ', '-h -o "%N"' ])

		# We add the first return
		mock_shell.return_value = b'node1\n'
		
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		db.session.commit()

		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(1, len(execution.nodes))
		self.assertEquals(node_1, execution.nodes[0])
		call_2 = call('squeue',  'endpoint', [ '-j 21', '-h -o "%N"' ])

		# We test it also works with a comma in the middle
		mock_shell.return_value = b'node1,node51\n'

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		db.session.add(execution)
		db.session.commit()

		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(2, len(execution.nodes))
		self.assertEquals(node_1, execution.nodes[0])
		self.assertEquals(node_51, execution.nodes[1])

		# We test with a more complex extructure
		mock_shell.return_value = b'node[50-52]\n'

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		db.session.add(execution)
		db.session.commit()

		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(3, len(execution.nodes))
		self.assertEquals(node_50, execution.nodes[0])
		self.assertEquals(node_51, execution.nodes[1])
		self.assertEquals(node_52, execution.nodes[2])

		# Next possible return
		mock_shell.return_value = b'node[50-51],node[53-54]\n'

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		db.session.add(execution)
		db.session.commit()

		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(4, len(execution.nodes))
		self.assertEquals(node_50, execution.nodes[0])
		self.assertEquals(node_51, execution.nodes[1])
		self.assertEquals(node_53, execution.nodes[2])
		self.assertEquals(node_54, execution.nodes[3])

		# next possible return
		mock_shell.return_value = b'node1,node[50-51]\n'

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		db.session.add(execution)
		db.session.commit()

		executor.__add_nodes_to_execution__(execution, 'endpoint')
		self.assertEquals(3, len(execution.nodes))
		self.assertEquals(node_1, execution.nodes[0])
		self.assertEquals(node_50, execution.nodes[1])
		self.assertEquals(node_51, execution.nodes[2])

		# We check the calls to the mock
		calls = [ call_1, call_2, call_2, call_2, call_2, call_2]
		mock_shell.assert_has_calls(calls)

	@mock.patch('shell.execute_command')
	def test_drain_a_node(self, mock_shell):
		"""
		It verifies that it is possible to drain a node with slurm
		"""

		testbed = Testbed( "testbed", True, "nice_testbed", "ssh", "endpoint")
		extra = {'enqueue_env_file': 'source_file'}
		testbed.extra_config = extra
		db.session.add(testbed)
		db.session.commit()

		node = Node()
		node.name = "pepito"
		node.testbed = testbed
		db.session.add(node)
		db.session.commit()

		executor.drain_a_node(node.id, "some strange reason")

		mock_shell.assert_called_with('scontrol',
		                              'endpoint',
									  [ 
										  'update',
										  'NodeName=pepito',
										  'State=drain',
										  'Reason="some strange reason"'
									  ])

	@mock.patch('shell.execute_command')
	def test_idle_a_node(self, mock_shell):
		"""
		It verifies that it is possible to drain a node with slurm
		"""

		testbed = Testbed( "testbed", True, "nice_testbed", "ssh", "endpoint")
		extra = {'enqueue_env_file': 'source_file'}
		testbed.extra_config = extra
		db.session.add(testbed)
		db.session.commit()

		node = Node()
		node.name = "pepito"
		node.testbed = testbed
		db.session.add(node)
		db.session.commit()

		executor.idle_a_node(node.id)

		mock_shell.assert_called_with('scontrol',
		                              'endpoint',
									  [ 
										  'update',
										  'NodeName=pepito',
										  'State=idle'
									  ])

	@mock.patch("slurm.stop_execution")
	@mock.patch('executor.cancel_execution')
	def test_stop_execution(self, mock_cancel, mock_stop):
		"""
		It tests that it is possible to stop an execution with slurm
		"""

		# Initial data to db for test

		# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="SLURM",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'srun', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		application.application_type = Application.CHECKPOINTABLE
		db.session.add(application)
		db.session.commit() 

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SLURM:SRUN"
		executable.executable_file = "/usr/local/gromacs-4.6.7-cuda2/bin/mdrun"
		executable.status = "COMPILED"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SLURM:SRUN"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 2
		#execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.srun_config = "--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1"
		execution_config.command = "-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet"
		db.session.add(execution_config)
		db.session.commit()

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		execution.execution_configuration = execution_config
		db.session.add(execution)
		db.session.commit()

		# Initial case, the execution has no childs, 
		# we need to create one associated to the initial configuration

		executor.stop_execution(execution)

		execution = db.session.query(Execution).filter_by(id=execution.id).first()
		self.assertEquals(1, len(execution.children))
		self.assertEquals(-1, execution.batch_id)
		self.assertEquals(Execution.__status_stopped__, execution.status)
		child = execution.children[0]
		self.assertEquals(21, child.batch_id)
		self.assertEquals(Execution.__status_running__, child.status) # It should be cancelled, but we are doing that with scancel
		self.assertEquals(execution_config, child.execution_configuration)
		mock_cancel.assert_called_with(child, 'user@testbed.com')

		# Second part of the test, now we have two childs and it has to select the one that 
		# it is running to cancel
		child_2 = Execution()
		child_2.status = Execution.__status_cancelled__
		child_2.execution_configuration = execution.execution_configuration
		child_2.batch_id = 33

		execution.children.append(child)
		execution.status = Execution.__status_restarted__
		db.session.commit()

		executor.stop_execution(execution)
		self.assertEquals(execution.status, Execution.__status_stopped__)
		call_2 = mock_cancel.call_args
		args, kwargs = call_2
		self.assertEquals(child.status, args[0].status)
		self.assertEquals(child.id, args[0].id)

		## testing with no checkpointable application
				# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="SLURM",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'srun', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		db.session.add(application)
		db.session.commit() 

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SLURM:SRUN"
		executable.executable_file = "/usr/local/gromacs-4.6.7-cuda2/bin/mdrun"
		executable.status = "COMPILED"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SLURM:SRUN"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 2
		#execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.srun_config = "--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1"
		execution_config.command = "-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet"
		db.session.add(execution_config)
		db.session.commit()

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_running__
		execution.execution_configuration = execution_config
		db.session.add(execution)
		db.session.commit()

		# Test starts here
		executor.stop_execution(execution)
		mock_stop.assert_called_with(21, "user@testbed.com")


	@mock.patch('executor.execute_application_type_slurm_srun')
	def test_restart_execution(self, mock_slurm):
		"""
		It verifies the correct work of the function restart_execution
		"""

		# We define the different entities necessaryb for the test.
		testbed = Testbed(name="nova2",
						  on_line=True,
						  category="SLURM",
						  protocol="SSH",
						  endpoint="user@testbed.com",
						  package_formats= ['sbatch', 'srun', 'SINGULARITY'],
						  extra_config= {
						  	"enqueue_compss_sc_cfg": "nova.cfg" ,
						  	"enqueue_env_file": "/home_nfs/home_ejarquej/installations/rc1707/COMPSs/compssenv"
						  })
		db.session.add(testbed)

		application = Application(name="super_app")
		application.application_type = Application.CHECKPOINTABLE
		db.session.add(application)
		db.session.commit() 

		executable = Executable()
		executable.source_code_file = 'test.zip'
		executable.compilation_script = 'gcc -X'
		executable.compilation_type = "SLURM:SRUN"
		executable.executable_file = "/usr/local/gromacs-4.6.7-cuda2/bin/mdrun"
		executable.status = "COMPILED"
		executable.application = application
		db.session.add(executable)
		db.session.commit() # We do this so executable gets and id

		deployment = Deployment()
		deployment.testbed_id = testbed.id
		deployment.executable_id = executable.id
		db.session.add(deployment) # We add the executable to the db so it has an id

		execution_config = ExecutionConfiguration()
		execution_config.execution_type ="SLURM:SRUN2"
		execution_config.application = application
		execution_config.testbed = testbed
		execution_config.executable = executable 
		execution_config.num_nodes = 2
		#execution_config.num_gpus_per_node = 2
		execution_config.num_cpus_per_node = 16
		execution_config.srun_config = "--job-name gromacstest --profile=energy,task --acctg-freq=Energy=1,Task=1"
		execution_config.command = "-s /home_nfs/home_dineshkr/Gromacs/gromacs-run/peptide_water_3k.tpr -v -nsteps 50000 -testverlet"
		db.session.add(execution_config)
		db.session.commit()

		execution = Execution()
		execution.batch_id = 21
		execution.status = Execution.__status_stopped__
		execution.execution_configuration = execution_config
		execution.execution_type = execution_config.execution_type
		db.session.add(execution)
		db.session.commit()

		child = Execution()
		child.status = Execution.__status_cancelled__
		child.execution_configuration = execution.execution_configuration
		child.batch_id = 33
		execution.children.append(child)
		db.session.commit()

		# Test starts here
		executor.restart_execution(execution)
		
		execution = db.session.query(Execution).filter_by(id=execution.id).first()
		new_child = execution.children[1]
		self.assertEquals(execution.execution_type, new_child.execution_type)
		self.assertEquals(Execution.__status_failed__, new_child.status)

		# Test 2
		execution_config.execution_type ="SLURM:SRUN"
		db.session.commit()

		executor.restart_execution(execution)
		
		execution = db.session.query(Execution).filter_by(id=execution.id).first()
		new_child = execution.children[2]
		self.assertEquals(execution_config.execution_type, new_child.execution_type)
		self.assertEquals(Execution.__status_running__, new_child.status)
		self.assertEquals(Execution.__status_restarted__, execution.status)
