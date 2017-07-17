# Builder script for the Application Lifecycle Deployment Engine
#
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Copyright: David García Pérez, Atos Research and Innovation, 2016.
#
# This code is licensed under an Apache 2.0 license. Please, refer to the LICENSE.TXT file for more information

from sqlalchemy_mapping_tests.mapping_tests import MappingTest
from models import db, ExecutionScript, Testbed, Execution

class ExecutionScriptMappingTest(MappingTest):
    """
    Series of test to validate the correct mapping to the class
    ExecutionScript to be stored into an SQL relational db
    """

    def test_crud_execution_script(self):
        """It test basic CRUD operations of an ExecutionScript Class"""

        # We verify that the object is not in the db after creating
        execution_script = ExecutionScript("ls", "slurm:sbatch", "-X")
        self.assertIsNone(execution_script.id)

        # We store the object in the db
        db.session.add(execution_script)

        # We recover the execution_script from the db
        execution_script = db.session.query(ExecutionScript).filter_by(command='ls').first()
        self.assertIsNotNone(execution_script.id)
        self.assertEquals("ls", execution_script.command)
        self.assertEquals("slurm:sbatch", execution_script.execution_type)
        self.assertEquals("-X", execution_script.parameters)

        # We check that we can update the application
        execution_script.parameters = '-X1'
        db.session.commit()
        execution_script_2 = db.session.query(ExecutionScript).filter_by(command='ls').first()
        self.assertEquals(execution_script.id, execution_script_2.id)
        self.assertEquals("-X1", execution_script.parameters)

        # We check the deletion
        db.session.delete(execution_script_2)
        count = db.session.query(ExecutionScript).filter_by(command='ls').count()
        self.assertEquals(0, count)

    def test_relation_with_testbed(self):
        """It check it is possible to relate the application with the testbed"""

        # We create first a testbed and commit it to the db
        testbed = Testbed("name", True, "slurm", "ssh", "user@server", ['slurm'])

        db.session.add(testbed)
        db.session.commit()

        # We create an execution script
        execution_script = ExecutionScript("ls", "slurm:sbatch", "-x1")
        execution_script.testbed = testbed

        db.session.add(execution_script)
        db.session.commit()

        # We retrieve the execution script from the db
        execution_script = db.session.query(ExecutionScript).filter_by(command='ls').first()
        self.assertEquals("name", execution_script.testbed.name)
        self.assertEquals(testbed.id, execution_script.testbed.id)

    def test_relation_with_execution(self):
        """
        Validates the 1 to n relation with Execution
        """

        # We create an execution
        execution_script = ExecutionScript("ls", "slurm:sbatch", "-X")

        # We create several executions
        execution_script.executions = [
            Execution("command1", "execution_type1", "parameters1", "status1"),
            Execution("command2", "execution_type2", "parameters2", "status2"),
            Execution("command3", "execution_type3", "parameters3", "status3")]

        # We save everything to the db
        db.session.add(execution_script)
        db.session.commit()

        # We retrieve the execution_script from the db and verify it contains all executions
        execution_script = db.session.query(ExecutionScript).filter_by(command="ls").first()

        self.assertEquals(3, len(execution_script.executions))
        self.assertEquals("command1", execution_script.executions[0].command)
        self.assertEquals("command2", execution_script.executions[1].command)
        self.assertEquals("command3", execution_script.executions[2].command)

        # lets delte a execution directly
        db.session.delete(execution_script.executions[0])
        db.session.commit()

        execution_script = db.session.query(ExecutionScript).filter_by(command="ls").first()
        self.assertEquals(2, len(execution_script.executions))
        self.assertEquals("command2", execution_script.executions[0].command)
        self.assertEquals("command3", execution_script.executions[1].command)

        # It should be only two executions in the db
        executions = db.session.query(Execution).all()
        self.assertEquals(2, len(executions))
        self.assertEquals("command2", executions[0].command)
        self.assertEquals("command3", executions[1].command)