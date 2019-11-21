import os
from aim.stack_grps.grp_route53 import Route53StackGroup
from aim.stack_group import StackGroup
from aim.cftemplates import Route53RecordSet
from aim.core.exception import StackException
from aim.core.exception import AimErrorCode
from aim.controllers.controllers import Controller

class Route53RecordSetStackGroup(StackGroup):
    def __init__(self, aim_ctx, account_ctx, controller):
        aws_name = account_ctx.get_name()
        super().__init__(aim_ctx,
                         account_ctx,
                         'Route53',
                         aws_name,
                         controller)

        # Initialize config with a deepcopy of the project defaults
        self.account_ctx = account_ctx
        self.stack_list = []

class Route53Controller(Controller):
    def __init__(self, aim_ctx):
        if aim_ctx.legacy_flag('route53_controller_type_2019_09_18') == True:
            controller_type = 'Service'
        else:
            controller_type = 'Resource'

        super().__init__(aim_ctx,
                         controller_type,
                         "Route53")

        if not 'route53' in self.aim_ctx.project['resource'].keys():
            self.init_done = True
            return
        self.config = self.aim_ctx.project['resource']['route53']
        if self.config != None:
            self.config.resolve_ref_obj = self

        #self.aim_ctx.log("Route53 Service: Configuration: %s" % (name))

        self.stack_grps = []
        self.second = False
        self.init_done = False

    def init(self, command=None, model_obj=None):
        if self.init_done:
            return
        self.config.resolve_ref_obj = self
        self.init_done = True
        self.aim_ctx.log_action_col("Init", "Route53")
        self.init_stack_groups()
        self.aim_ctx.log_action_col("Init", "Route53", "Completed")

    def init_stack_groups(self):
        # TODO: Fixed above now with init done flag?
        if self.second == True:
            raise StackException(AimErrorCode.Unknown)
        self.second = True
        for account_name in self.config.get_hosted_zones_account_names():
            account_ctx = self.aim_ctx.get_account_context(account_name=account_name)
            route53_stack_grp = Route53StackGroup(self.aim_ctx,
                                                  account_ctx,
                                                  self.config,
                                                  self)
            self.stack_grps.append(route53_stack_grp)

    def add_record_set(self,
        account_ctx,
        region,
        dns,
        record_set_type,
        enabled = True,
        resource_records = None,
        alias_dns_name = None,
        alias_hosted_zone_id = None,
        stack_group = None,
        config_ref = None):

        record_set_config = {
            'enabled' : enabled,
            'change_protected': False,
            'dns': dns,
            'alias_dns_name': alias_dns_name,
            'alias_hosted_zone_id': alias_hosted_zone_id,
            'record_set_type': record_set_type,
            'resource_records': resource_records
        }
        #config_ref = 'route53.record_set.dns.domain_name'
        record_set_stack_group = Route53RecordSetStackGroup(
            self.aim_ctx, account_ctx, self
        )
        Route53RecordSet(
            self.aim_ctx,
            account_ctx,
            region,
            record_set_stack_group, # stack_group
            None, # stack_tags

            dns.domain_name,
            record_set_config,
            config_ref
        )
        stack_group.add_stack_group(record_set_stack_group)

    def validate(self):
        for stack_grp in self.stack_grps:
            stack_grp.validate()

    def provision(self):
        for stack_grp in self.stack_grps:
            stack_grp.provision()

    def delete(self):
        for stack_grp in reversed(self.stack_grps):
            stack_grp.delete()

    def get_stack(self, zone_id):
        for stack_grp in self.stack_grps:
            if stack_grp.has_zone_id(zone_id):
                return stack_grp.get_stack(zone_id)
        return None

    def resolve_ref(self, ref):
        # route53.example.id
        if ref.last_part == "id":
            return self.get_stack(zone_id=ref.parts[2])

        return None
