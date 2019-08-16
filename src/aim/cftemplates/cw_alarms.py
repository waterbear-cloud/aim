"""
CloudFormation template for CloudWatch Alarms
"""

import aim.models.services
import json
from aim.cftemplates.cftemplates import CFTemplate
from aim.models import schemas
from aim.models import vocabulary
from aim.models.locations import get_parent_by_interface
from aim.models.formatter import get_formatted_model_context


def get_alarm_actions(notificationgroups, alarm):
    """Return a list of SNS Topic alarm actions.
    This will by default be a list of SNS Topics that the alarm is subscribed to.
    However, if a plugin is registered, it will provide the actions instead.
    """
    # if a service plugin provides override_alarm_actions, call that instead
    service_plugins = aim.models.services.list_service_plugins()

    # Error if more than one plugin provides override_alarm_actions
    count = 0
    for plugin_module in service_plugins.values():
        if hasattr(plugin_module, 'override_alarm_actions'):
            count += 1
    if count > 1:
        raise aim.models.exceptions.InvalidAimProjectFile('More than one Service plugin is overriding alarm actions')

    for plugin_name, plugin_module in service_plugins.items():
        if hasattr(plugin_module, 'override_alarm_actions'):
            return plugin_module.override_alarm_actions(None, alarm)

    # default behaviour is to use notification groups directly
    notification_arns = [
        notificationgroups[group].resource_name for group in alarm.notification_groups
    ]
    if len(notification_arns) > 5:
        raise aim.models.exceptions.InvalidAimProjectFile("""
Alarm {} has {} actions, but CloudWatch Alarms allow a maximum of 5 actions.

{}""".format(alarm.name, len(notification_arns), get_formatted_model_context(alarm))
        )

    return notification_arns


class CWAlarms(CFTemplate):
    """
    CloudFormation template for CloudWatch Alarms
    """
    def __init__(
        self,
        aim_ctx,
        account_ctx,
        aws_region,
        alarm_sets,
        res_type,
        res_config_ref,
        resource,
        aws_name
    ):
        aws_name='-'.join([aws_name, 'Alarms'])
        super().__init__(
            aim_ctx,
            account_ctx,
            aws_region,
            config_ref=res_config_ref,
            aws_name=aws_name
        )
        self.alarm_sets = alarm_sets
        self.dimension = vocabulary.cloudwatch[res_type]['dimension']

        # Define the Template
        template_fmt = """
AWSTemplateFormatVersion: '2010-09-09'
Description: 'CloudWatch Alarms'

Resources:

{0[alarms]:s}

Outputs:

{0[outputs]:s}
"""
        template_table = {
          'alarms': None,
          'outputs': None,
        }

        output_fmt = """
  Alarm{0[id]:s}:
    Value: !Ref Alarm{0[id]:s}
"""

        # Important: If you specify a name, you cannot perform updates that require
        # replacement of this resource. You can perform updates that require no or
        # some interruption. If you must replace the resource, specify a new name.
        # AlarmName: '{0[name]:s}'
        # ToDo: enable settings for
        # Metrics :
        #   - MetricDataQuery
        # Unit: String
        # DatapointsToAlarm: Integer

        alarm_fmt = """
  Alarm{0[id]:s}:
    Type: AWS::CloudWatch::Alarm
    Properties:
{0[alarm_actions]:s}
      AlarmDescription: '{0[description]:s}'
      ComparisonOperator: {0[comparison_operator]:s}
      Dimensions: {0[dimensions]:s}
      EvaluateLowSampleCountPercentile: {0[evaluate_low_sample_count_percentile]:s}
      EvaluationPeriods: {0[evaluation_periods]:d}
      ExtendedStatistic: {0[extended_statistic]:s}
      MetricName: {0[metric_name]:s}
      Namespace: {0[namespace]:s}
      Period: {0[period]:d}
      Statistic: {0[statistic]:s}
      Threshold: {0[threshold]:f}
      TreatMissingData: {0[treat_missing_data]:s}
"""
        dimensions_fmt = """
        - Name: {}
          Value: {}"""

        alarm_table = {
            'id': None,
            'description': None,
            'name': None,
            'comparison_operator': None,
            'dimensions': None,
            'evaluation_periods': 0,
            'metric_name': None,
            'namespace': None,
            'period': 0,
            'statistic': None,
            'threshold': 0,
            'treat_missing_data': None,
            'extended_statistic': None,
            'evaluate_low_sample_count_percentile': None,
            'alarm_actions': None
        }

        alarms_yaml = ""
        outputs_yaml = ""
        for alarm_set_id in alarm_sets.keys():
            alarm_set = alarm_sets[alarm_set_id]
            for alarm_id in alarm_set.keys():
                netenv = get_parent_by_interface(resource, schemas.INetworkEnvironment)
                env = get_parent_by_interface(resource, schemas.IEnvironment)
                envreg = get_parent_by_interface(resource, schemas.IEnvironmentRegion)
                app = get_parent_by_interface(resource, schemas.IApplication)
                group = get_parent_by_interface(resource, schemas.IResourceGroup)
                alarm = alarm_set[alarm_id]
                notification_arns = [
                    self.aim_ctx.project['notificationgroups'][group].resource_name for group in alarm.notification_groups
                ]
                if netenv == None:
                    # service applications do not live in a NetEnv, they have a shorter description
                    description = {
                        "app_name": app.name,
                        "app_title": app.title,
                        "resource_group_name": group.name,
                        "resource_group_title": group.title,
                        "resource_name": resource.name,
                        "resource_title": resource.title,
                        "alarm_name": alarm.name,
                        "classification": alarm.classification,
                        "severity": alarm.severity,
                        "topic_arns": notification_arns
                    }
                else:
                    # full, normal netenv description
                    description = {
                        "netenv_name": netenv.name,
                        "netenv_title": netenv.title,
                        "env_name": env.name,
                        "env_title": env.title,
                        "envreg_name": envreg.name,
                        "envreg_title": envreg.title,
                        "app_name": app.name,
                        "app_title": app.title,
                        "resource_group_name": group.name,
                        "resource_group_title": group.title,
                        "resource_name": resource.name,
                        "resource_title": resource.title,
                        "alarm_name": alarm.name,
                        "classification": alarm.classification,
                        "severity": alarm.severity,
                        "topic_arns": notification_arns
                    }
                normalized_set_id = self.normalize_resource_name(alarm_set_id)
                normalized_id = self.normalize_resource_name(alarm_id)

                # Alarm actions
                alarm_actions = get_alarm_actions(self.aim_ctx.project['notificationgroups'], alarm)
                if len(alarm_actions) > 0 and alarm_actions[0] != None and alarm_actions[0] != '':
                    alarm_actions_cfn = "      ActionsEnabled: True\n      AlarmActions:\n"
                    for action in alarm_actions:
                        alarm_actions_cfn += "         - " + action
                else:
                    alarm_actions_cfn = '      ActionsEnabled: False\n'

                # Dimensions
                # if there are no dimensions, then fallback to the default of
                # a primary dimension and the resource's resource_name
                if len(alarm.dimensions) < 1:
                    dimensions = [
                        (vocabulary.cloudwatch[res_type]['dimension'], resource.resource_name)
                    ]
                else:
                    dimensions = []
                    for dimension in alarm.dimensions:
                        if dimension.value.startswith('python:'):
                            # XXX improve eval saftey or rework as a ref ...
                            value = eval(dimension.value[7:])
                        else:
                            value = dimension.value
                        dimensions.append(
                            (dimension.name, value)
                        )
                dimensions_str = ''
                for name, value in dimensions:
                    dimensions_str += dimensions_fmt.format(name, value)

                # Metric Namespace can override default Resource Namespace
                if alarm.namespace:
                    namespace = alarm.namespace
                else:
                    namespace = vocabulary.cloudwatch[res_type]['namespace']

                alarm_table['alarm_actions'] = alarm_actions_cfn
                alarm_table['id'] = normalized_set_id+normalized_id
                alarm_table['description'] = json.dumps(description)
                alarm_table['name'] = alarm_id
                alarm_table['comparison_operator'] = alarm.comparison_operator
                alarm_table['evaluation_periods'] = alarm.evaluation_periods
                alarm_table['namespace'] = namespace
                alarm_table['dimensions'] = dimensions_str
                alarm_table['evaluation_periods'] = alarm.evaluation_periods
                alarm_table['metric_name'] = alarm.metric_name
                alarm_table['period'] = alarm.period
                alarm_table['threshold'] = alarm.threshold
                alarm_table['treat_missing_data'] = alarm.treat_missing_data
                if alarm.extended_statistic == None:
                    alarm_table['statistic'] = alarm.statistic
                    alarm_table['extended_statistic'] = "!Ref AWS::NoValue"
                else:
                    alarm_table['statistic'] = '!Ref AWS::NoValue'
                    alarm_table['extended_statistic'] = alarm.extended_statistic
                if alarm.evaluate_low_sample_count_percentile == None:
                    alarm_table['evaluate_low_sample_count_percentile'] = "!Ref AWS::NoValue"
                else:
                    alarm_table['evaluate_low_sample_count_percentile'] = alarm.evaluate_low_sample_count_percentile

                alarms_yaml += alarm_fmt.format(alarm_table)
                outputs_yaml += output_fmt.format(alarm_table)
                output_ref = '.'.join([res_config_ref, 'monitoring', 'alarm_sets', alarm_set_id, alarm_id])
                self.register_stack_output_config(output_ref, 'Alarm'+alarm_table['id'])

        template_table['alarms'] = alarms_yaml
        template_table['outputs'] = outputs_yaml

        self.set_template(template_fmt.format(template_table))

    def validate(self):
        super().validate()

    def get_outputs_key_from_ref(self, ref):
        # There is only one output key
        return None
