"""
CloudFormation template for CloudWatch Alarms
"""

import aim.models.services
import json
import troposphere
from aim import utils
from aim.models import schemas
from aim.models import vocabulary
from aim.cftemplates.cftemplates import CFTemplate
from aim.models.locations import get_parent_by_interface
from aim.utils import prefixed_name


class CFBaseAlarm(CFTemplate):
    "Methods shared by different CFTemplates that can create a CloudWatch Alarm"
    # allow services the chance to send notifications to another region
    notification_region = None

    def create_notification_params(self, alarm):
        "Create a Parameter for each SNS Topic an alarm should notify. Return a list of Refs to those Params."
        notification_aim_refs = []
        for group in alarm.notification_groups:
            if not self.notification_region:
                region = alarm.region_name
            else:
                region = self.notification_region
            notification_aim_refs.append(
                self.aim_ctx.project['resource']['notificationgroups'][region][group].aim_ref + '.arn'
            )

        notification_cfn_refs = []
        for notification_aim_ref in notification_aim_refs:
            # Create parameter
            param_name = 'Notification{}'.format(utils.md5sum(str_data=notification_aim_ref))
            if param_name in self.notification_param_map.keys():
                notification_param = self.notification_param_map[param_name]
            else:
                notification_param = self.create_cfn_parameter(
                    param_type = 'String',
                    name = param_name,
                    description = 'SNS Topic to notify',
                    value = notification_aim_ref,
                    use_troposphere = True
                )
                self.template.add_parameter(notification_param)
                self.notification_param_map[param_name] = notification_param
            notification_cfn_refs.append(troposphere.Ref(notification_param))
        return notification_cfn_refs

    def set_alarm_actions_to_cfn_export(self, alarm, cfn_export_dict):
        "Sets the AlarmActions, OKActions and InsufficientDataActions for a Troposphere dict"
        alarm_action_list = []
        for alarm_action in alarm.get_alarm_actions_aim_refs():
            # Create parameter
            param_name = 'AlarmAction{}'.format(utils.md5sum(str_data=alarm_action))
            if param_name in self.alarm_action_param_map.keys():
                alarm_action_param = self.alarm_action_param_map[param_name]
            else:
                alarm_action_param = self.create_cfn_parameter(
                    param_type = 'String',
                    name = param_name,
                    description = 'SNSTopic for Alarm to notify.',
                    value = alarm_action,
                    use_troposphere = True
                )
                self.template.add_parameter(alarm_action_param)
                self.alarm_action_param_map[param_name] = alarm_action_param
            alarm_action_list.append(troposphere.Ref(alarm_action_param))

        cfn_export_dict['AlarmActions'] = alarm_action_list
        if getattr(alarm, 'enable_ok_actions', False):
            cfn_export_dict['OKActions'] = alarm_action_list
        if getattr(alarm, 'enable_insufficient_data_actions', False):
            cfn_export_dict['InsufficientDataActions'] = alarm_action_list


class CWAlarms(CFBaseAlarm):
    """
    CloudFormation template for CloudWatch Alarms
    """

    def __init__(
        self,
        aim_ctx,
        account_ctx,
        aws_region,
        stack_group,
        stack_tags,
        alarm_sets,
        res_config_ref,
        resource,
        grp_id=None,
        res_id=None,
    ):
        super().__init__(
            aim_ctx,
            account_ctx,
            aws_region,
            enabled=resource.is_enabled(),
            config_ref=res_config_ref,
            stack_group=stack_group,
            stack_tags=stack_tags
        )
        if grp_id and res_id:
            self.set_aws_name('Alarms', grp_id, res_id, resource.type)
        else:
            # Application-level Alarms
            self.set_aws_name('Alarms')
        self.alarm_sets = alarm_sets
        self.dimension = vocabulary.cloudwatch[resource.type]['dimension']

        # build a list of Alarm objects
        alarms = []
        for alarm_set_id in alarm_sets.keys():
            alarm_set = alarm_sets[alarm_set_id]
            for alarm_id in alarm_set.keys():
                cfn_resource_name = 'Alarm{}{}'.format(
                    self.create_cfn_logical_id(alarm_set_id),
                    self.create_cfn_logical_id(alarm_id)
                )
                alarm_set[alarm_id].cfn_resource_name = cfn_resource_name
                alarms.append(alarm_set[alarm_id])

        # Define the Template
        self.init_template('CloudWatch Alarms')
        template = self.template

        self.alarm_action_param_map = {}
        self.notification_param_map = {}
        if resource.is_enabled() and resource.monitoring.enabled:
            self.add_alarms(
                template,
                alarms,
                resource,
                res_config_ref,
                self.aim_ctx.project,
                alarm_id,
                alarm_set_id,
            )
        self.set_template(template.to_yaml())

    def add_alarms(
            self,
            template,
            alarms,
            resource,
            res_config_ref,
            project,
            alarm_id,
            alarm_set_id,
        ):
        # Add Parameters
        if schemas.IResource.providedBy(resource):
            value = resource.aim_ref + '.name'
            if schemas.IElastiCacheRedis.providedBy(resource):
                # Primary node uses the aws name with '-001' appended to it
                # ToDo: how to have Alarms for the read replica nodes?
                value = resource.get_aws_name() + '-001'
            dimension_param = self.create_cfn_parameter(
                param_type = 'String',
                name = 'DimensionResource',
                description = 'The resource id or name for the metric dimension.',
                value = value,
                use_troposphere = True
            )
            template.add_parameter(dimension_param)
        for alarm in alarms:
            if len(alarm.dimensions) > 0:
                for dimension in alarm.dimensions:
                    dimension.parameter = self.create_cfn_parameter(
                        param_type = 'String',
                        name = 'DimensionResource{}{}'.format(alarm.cfn_resource_name, dimension.name),
                        description = 'The resource id or name for the metric dimension.',
                        value = dimension.value,
                        use_troposphere = True
                    )
                    template.add_parameter(dimension.parameter)

        # Add Alarm resources
        for alarm in alarms:
            # compute dynamic attributes for cfn_export_dict
            alarm_export_dict = alarm.cfn_export_dict
            self.set_alarm_actions_to_cfn_export(alarm, alarm_export_dict)

            # AlarmDescription
            notification_cfn_refs = self.create_notification_params(alarm)
            alarm_export_dict['AlarmDescription'] = alarm.get_alarm_description(notification_cfn_refs)

            # Namespace
            if not alarm.namespace:
                # if not supplied default to the Namespace for the Resource type
                alarm_export_dict['Namespace'] = vocabulary.cloudwatch[resource.type]['namespace']
            else:
                # Namespace look-up if tied to a LogGroup MetricFilter
                if alarm.namespace.startswith('log_sets.'):
                    obj = get_parent_by_interface(alarm, schemas.IMonitorConfig)
                    for part_name in alarm.namespace.split('.'):
                        new_obj = getattr(obj, part_name, None)
                        if new_obj == None:
                            new_obj = obj[part_name]
                        obj = new_obj
                    alarm_export_dict['Namespace'] = "Logs/" + prefixed_name(resource, obj.get_log_group_name(), self.aim_ctx.legacy_flag)
                else:
                    # Use the Namespace as directly supplied
                    alarm_export_dict['Namespace'] = alarm.namespace

            # Dimensions
            # if there are no dimensions, then fallback to the default of
            # a primary dimension and the resource's resource_name
            # This only happens for Resource-level Alarms
            # MetricFilter LogGroup Alarms must have no dimensions
            if alarm_export_dict['Namespace'].startswith('Logs/'):
                dimensions = []
            elif schemas.IResource.providedBy(resource) and len(alarm.dimensions) < 1:
                dimensions = [
                    {'Name': vocabulary.cloudwatch[resource.type]['dimension'],
                     'Value': troposphere.Ref(dimension_param)}
                ]
            else:
                dimensions = []
                for dimension in alarm.dimensions:
                    dimensions.append(
                        {'Name': dimension.name, 'Value': troposphere.Ref(dimension.parameter)}
                    )
            alarm_export_dict['Dimensions'] = dimensions

            # Add Alarm resource
            alarm_resource = troposphere.cloudwatch.Alarm.from_dict(
                alarm.cfn_resource_name,
                alarm_export_dict
            )
            template.add_resource(alarm_resource)

            # Alarm Output
            output_ref = '.'.join([res_config_ref, 'monitoring', 'alarm_sets', alarm_set_id, alarm_id])
            self.register_stack_output_config(output_ref, alarm.cfn_resource_name)
            alarm_output = troposphere.Output(
                alarm.cfn_resource_name,
                Value=troposphere.Ref(alarm_resource)
            )
            template.add_output(alarm_output)
