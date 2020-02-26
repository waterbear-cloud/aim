import paco.cftemplates
from paco.application.res_engine import ResourceEngine
from paco.core.yaml import YAML
import paco.models

yaml=YAML()
yaml.default_flow_sytle = False

class ASGResourceEngine(ResourceEngine):

    @property
    def stack_name(self):
        name_list = [
            self.app_engine.get_aws_name(),
            self.grp_id,
            self.res_id
        ]

        if self.paco_ctx.legacy_flag('cftemplate_aws_name_2019_09_17') == True:
            name_list.insert(1, 'ASG')
        else:
            name_list.append('ASG')

        stack_name = '-'.join(name_list)
        return stack_name

    def init_resource(self):
        # Create instance role
        role_profile_arn = None

        if self.resource.instance_iam_role.enabled == False:
            role_config_yaml = """
instance_profile: false
path: /
role_name: %s""" % ("ASGInstance")
            role_config_dict = yaml.load(role_config_yaml)
            role_config = paco.models.iam.Role('instance_iam_role', self.resource)
            role_config.apply_config(role_config_dict)
        else:
            role_config = self.resource.instance_iam_role

        # The ID to give this role is: group.resource.instance_iam_role
        instance_iam_role_ref = self.resource.paco_ref_parts + '.instance_iam_role'
        instance_iam_role_id = self.gen_iam_role_id(self.res_id, 'instance_iam_role')
        # If no assume policy has been added, force one here since we know its
        # an EC2 instance using it.
        # Set defaults if assume role policy was not explicitly configured
        if not hasattr(role_config, 'assume_role_policy') or role_config.assume_role_policy == None:
            policy_dict = { 'effect': 'Allow',
                            'service': ['ec2.amazonaws.com'] }
            role_config.set_assume_role_policy(policy_dict)
        # Always turn on instance profiles for ASG instances
        role_config.instance_profile = True
        role_config.enabled = self.resource.is_enabled()
        iam_ctl = self.paco_ctx.get_controller('IAM')
        iam_ctl.add_role(
            region=self.aws_region,
            resource=self.resource,
            role=role_config,
            iam_role_id=instance_iam_role_id,
            stack_group=self.stack_group,
            stack_tags=self.stack_tags,
        )
        role_profile_arn = iam_ctl.role_profile_arn(instance_iam_role_ref)

        # EC2 Launch Manger Bundles
        self.app_engine.ec2_launch_manager.process_bundles(self.resource, instance_iam_role_ref)

        # Create ASG stack
        ec2_manager_user_data_script = self.app_engine.ec2_launch_manager.user_data_script(
            self.app_id,
            self.grp_id,
            self.res_id,
            self.resource,
            instance_iam_role_ref,
            self.stack_name
        )
        self.stack_group.add_new_stack(
            self.aws_region,
            self.resource,
            paco.cftemplates.ASG,
            stack_tags=self.stack_tags,
            extra_context={
                'env_ctx': self.env_ctx,
                'role_profile_arn': role_profile_arn,
                'ec2_manager_user_data_script': ec2_manager_user_data_script,
                'ec2_manager_cache_id': self.app_engine.ec2_launch_manager.get_cache_id(self.resource, self.app_id, self.grp_id),
            },
        )

