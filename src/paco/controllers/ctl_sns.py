from paco import utils
from paco.controllers.controllers import Controller
from paco.core.exception import StackException
from paco.stack import StackGroup, Stack, StackTags
from paco.models.references import get_model_obj_from_ref, resolve_ref_outputs, Reference
from paco.models import deepcopy_except_parent
from paco.models.metrics import SNSTopics
from paco.models.base import RegionContainer, AccountContainer
import json
import paco.cftemplates
import os
import pathlib


class SNSTopicsStackGroup(StackGroup):
    def __init__(
        self,
        paco_ctx,
        account_ctx,
        region,
        group_name,
        controller,
        resource,
        topics,
        stack_tags
    ):
        aws_name = group_name
        super().__init__(paco_ctx, account_ctx, group_name, aws_name, controller)
        self.paco_ctx.log_start('Init', resource)
        stack = self.add_new_stack(
            region,
            resource,
            paco.cftemplates.SNS,
            stack_tags=StackTags(stack_tags),
            extra_context={'grp_id': account_ctx.name, 'topics': topics},
            set_resource_stack=True,
        )
        hook_arg = {'resource': resource, 'account_ctx': account_ctx}
        # Hook to create and upload imageDefinitions.json S3 source artifact
        stack.hooks.add(
            name='StoreResourceSNSState.' + resource.name,
            stack_action='update',
            stack_timing='post',
            hook_method=self.store_resource_sns_state,
            cache_method=self.store_resource_sns_state_cache,
            hook_arg=hook_arg
        )
        stack.hooks.add(
            name='StoreResourceSNSState.' + resource.name,
            stack_action='create',
            stack_timing='post',
            hook_method=self.store_resource_sns_state,
            cache_method=self.store_resource_sns_state_cache,
            hook_arg=hook_arg
        )
        self.paco_ctx.log_finish('Init', resource)

    def get_aws_name(self):
        return 'SNS'

    def build_sns_state(self, resource):
        state = {}
        for group_name in resource.keys():
            group = resource[group_name]
            state[group_name] = resolve_ref_outputs(Reference(group.paco_ref+'.arn'), self.paco_ctx.project['home'])

        return state

    def store_resource_sns_state_cache(self, hook, config):
        "Create a cache id for resource.sns state"
        return json.dumps(self.build_sns_state(config['resource']))

    def store_resource_sns_state(self, hook, config):
        "Store resource.sns state in the Paco work bucket"
        resource = config['resource']
        account_ctx = config['account_ctx']
        state = self.build_sns_state(resource)
        self.paco_ctx.store_resource_state('SNS', 'resource', account_ctx.id, resource.stack.aws_region, state)

class SNSController(Controller):
    def __init__(self, paco_ctx):
        super().__init__(paco_ctx, "SNS", None)
        try:
            self.sns = self.paco_ctx.project['resource']['sns']
            # inject the controller into the model
            self.sns.resolve_ref_obj = self
        except KeyError:
            self.init_done = True
            return
        self.init_done = False

    def init(self, command=None, model_obj=None):
        "Initialize SNS Controller"
        if self.init_done:
            return
        stack_tags = StackTags()
        # aggregate SNS Topics grouped by account/region and apply to the computed attr
        default_locations = self.sns.default_locations
        sns_computed = self.sns.computed
        for snstopic in self.sns.topics.values():
            if len(snstopic.locations) == 0:
                locations = default_locations
            else:
                locations = snstopic.locations
            for location in locations:
                account_name = location.account.split('.')[-1]
                if not account_name in sns_computed:
                    sns_computed[account_name] = AccountContainer(account_name, sns_computed)
                    sns_computed[account_name].stackgroups = []
                for region in location.regions:
                    if region not in sns_computed[account_name]:
                        sns_computed[account_name][region] = RegionContainer(region, sns_computed[account_name])
                    snstopic = deepcopy_except_parent(snstopic)
                    snstopic.__parent__ = sns_computed[account_name][region]
                    sns_computed[account_name][region][snstopic.name] = snstopic

        # create a SNSTopicsGroup stack group for each active region
        for account in sns_computed.keys():
            account_ctx = self.paco_ctx.get_account_context(account_name=account)
            sns_computed[account].account_ctx = account_ctx
            for region in sns_computed[account].keys():
                topics = sns_computed[account][region].values()
                stackgroup = SNSTopicsStackGroup(
                    self.paco_ctx,
                    account_ctx,
                    region,
                    'SNS',
                    self,
                    sns_computed[account][region],
                    topics,
                    StackTags(stack_tags)
                )
                sns_computed[account].stackgroups.append(stackgroup)

        self.init_done = True

    def validate(self):
        "Validate"
        for account in self.sns.computed.keys():
            account_ctx = self.sns.computed[account].account_ctx
            for stackgroup in self.sns.computed[account].stackgroups:
                stackgroup.validate()

    def provision(self):
        "Provision"
        for account in self.sns.computed.keys():
            account_ctx = self.sns.computed[account].account_ctx
            for stackgroup in self.sns.computed[account].stackgroups:
                stackgroup.provision()

    def delete(self):
        "Delete"
        for account in self.sns.computed.keys():
            account_ctx = self.sns.computed[account].account_ctx
            for stackgroup in self.sns.computed[account].stackgroups:
                stackgroup.delete()

    def resolve_ref(self, ref):
        if ref.last_part == 'arn':
            region_container = get_model_obj_from_ref('paco.ref ' + '.'.join(ref.parts[:-2]), self.paco_ctx.project)
            return region_container.stack
        else:
            return None
