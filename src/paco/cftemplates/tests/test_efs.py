from paco.cftemplates.tests import BaseTestProject
from paco.cftemplates.efs import EFS
import troposphere
import troposphere.efs


class TestEFS(BaseTestProject):

    fixture_name = 'config_city'
    app_name = 'app'
    netenv_name = 'res'
    group_name = 'things'

    def test_efs(self):
        efs_resource = self.get_resource_by_type('EFS')
        network = self.get_network()
        netenv_ctl = self.paco_ctx.get_controller('netenv', None, self.env_region)
        body = efs_resource.stack.template.body
        troposphere_tmpl = efs_resource.stack.template.template

        # EFS has an EFS Resource
        assert troposphere_tmpl.resources['EFS'].resource_type, 'AWS::EFS::FileSystem'

        # EFSId Output
        self.assertIsInstance(troposphere_tmpl.outputs['EFSId'], troposphere.Output)

        # MountTarget for every Subnet in the AvailabiltyZones
        assert troposphere_tmpl.resources['EFSMountTargetAZ1'].resource_type, troposphere.efs.MountTarget.resource_type
        assert troposphere_tmpl.resources['EFSMountTargetAZ2'].resource_type, troposphere.efs.MountTarget.resource_type
