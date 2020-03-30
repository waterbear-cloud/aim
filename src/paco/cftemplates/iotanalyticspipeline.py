"""
IoT Analytics Pipeline template
"""

from paco.cftemplates.cftemplates import StackTemplate
import troposphere
import troposphere.iotanalytics


class IoTAnalyticsPipeline(StackTemplate):
    def __init__(self, stack, paco_ctx, role):
        super().__init__(stack, paco_ctx)
        self.set_aws_name('IoTAnalyticsPipeline', self.resource_group_name, self.resource_name)
        iotap = self.resource

        # Init Troposphere template
        self.init_template('IoT Analytics pipeline')
        if not iotap.is_enabled():
            return

        # Role ARN for IoT
        role_arn_param = self.create_cfn_parameter(
            param_type='String',
            name='IoTRoleArn',
            description='IoT Topic Rule Service Role ARN',
            value=role.get_arn(),
        )

        # Channel Resource
        iotchannel_logical_id = 'IoTAnalyticsChannel'
        cfn_export_dict = {}
        if iotap.channel_storage.bucket == None:
            channel_storage_dict = {'ServiceManagedS3':{}}
            cfn_export_dict['RetentionPeriod'] = convert_expire_to_cfn_dict(iotap.channel_storage.expire_events_after_days)
        else:
            channel_bucket_param = self.create_cfn_parameter(
                param_type='String',
                name='IoTAnalyticsChannelBucketName',
                description='IoT Analytics Channel storage bucket name',
                value=iotap.channel_storage.bucket + '.name',
            )
            channel_storage_dict = {'CustomerManagedS3': {
                'Bucket': troposphere.Ref(channel_bucket_param),
                'KeyPrefix':iotap.channel_storage.key_prefix,
                'RoleArn': troposphere.Ref(role_arn_param),
            }}
        cfn_export_dict['ChannelStorage'] = channel_storage_dict
        iot_channel_resource = troposphere.iotanalytics.Channel.from_dict(
            iotchannel_logical_id,
            cfn_export_dict
        )
        self.template.add_resource(iot_channel_resource)

        self.create_output(
            title='ChannelName',
            description='IoT Analytics Channel name',
            value=troposphere.Ref(iot_channel_resource),
            ref=self.resource.paco_ref_parts + '.channel.name',
        )

        # Datastore Resource
        iotchannel_logical_id = 'IoTAnalyticsDatastore'
        cfn_export_dict = {}
        if iotap.datastore_storage.bucket == None:
            datastore_storage_dict = {'ServiceManagedS3':{}}
            cfn_export_dict['RetentionPeriod'] = convert_expire_to_cfn_dict(iotap.datastore_storage.expire_events_after_days)
        else:
            datastore_bucket_param = self.create_cfn_parameter(
                param_type='String',
                name='IoTAnalyticsDatastoreBucketName',
                description='IoT Analytics Datastore storage bucket name',
                value=iotap.datastore_storage.bucket + '.name',
            )
            datastore_storage_dict = {'CustomerManagedS3': {
                'Bucket': troposphere.Ref(datastore_bucket_param),
                'KeyPrefix':iotap.datastore_storage.key_prefix,
                'RoleArn': troposphere.Ref(role_arn_param),
            }}

        cfn_export_dict['DatastoreStorage'] = datastore_storage_dict
        iotap_datastore_resource = troposphere.iotanalytics.Datastore.from_dict(
            iotchannel_logical_id,
            cfn_export_dict
        )
        self.template.add_resource(iotap_datastore_resource)

        self.create_output(
            title='DatastoreName',
            description='IoT Analytics Datastore name',
            value=troposphere.Ref(iotap_datastore_resource),
            ref=self.resource.paco_ref_parts + '.datastore.name',
        )

        # Pipeline Resource
        iotpipeline_logical_id = 'IoTAnalyticsPipeline'
        cfn_export_dict = {}
        cfn_export_dict['PipelineActivities'] = []
        idx = 0
        activity_list = list(iotap.pipeline_activities.values())

        # start with a Channel activity
        if len(activity_list) == 0:
            next_name = "DatastoreActivity"
        else:
            next_name = activity_list[idx].name + "Activity"
        cfn_export_dict['PipelineActivities'].append({
            'Channel':{
                'Name': "ChannelActivity",
                'ChannelName': troposphere.Ref(iot_channel_resource),
                'Next': next_name,
            }
        })

        for activity in iotap.pipeline_activities.values():
            if len(activity_list) == idx + 1:
                next_name = 'DatastoreActivity'
            else:
                next_name = activity_list[idx + 1].name + "Activity"
            if activity.activity_type == 'lambda':
                lambda_param = self.create_cfn_parameter(
                    param_type='String',
                    name=f'LambdaFunction{idx}',
                    description=f'IoT Analytics Lambda for Activity {idx}',
                    value=activity.function + '.arn',
                )
                activity_dict = {
                    'Lambda': {
                        'LambdaName': troposphere.Join('', ['',
                            troposphere.Select(6, troposphere.Split(':', troposphere.Ref(lambda_param)))
                        ]),
                        'BatchSize': activity.batch_size,
                        'Name': activity.name + "Activity",
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'add_attributes':
                activity_dict = {
                    'AddAttributes': {
                        'Name': activity.name + "Activity",
                        'Attributes': activity.attributes,
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'remove_attributes':
                activity_dict = {
                    'RemoveAttributes': {
                        'Name': activity.name + "Activity",
                        'Attributes': activity.attribute_list,
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'select_attributes':
                activity_dict = {
                    'SelectAttributes': {
                        'Name': activity.name + "Activity",
                        'Attributes': activity.attribute_list,
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'filter':
                activity_dict = {
                    'Filter': {
                        'Name': activity.name + "Activity",
                        'Filter': activity.filter,
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'math':
                activity_dict = {
                    'Math': {
                        'Name': activity.name + "Activity",
                        'Attribute': activity.attribute,
                        'Math': activity.math,
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'device_registry_enrich':
                activity_dict = {
                    'DeviceRegistryEnrich': {
                        'Name': activity.name + "Activity",
                        'Attribute': activity.attribute,
                        'ThingName': activity.thing_name,
                        'Next': next_name,
                    }
                }
            elif activity.activity_type == 'device_shadow_enrich':
                activity_dict = {
                    'DeviceShadowEnrich': {
                        'Name': activity.name + "Activity",
                        'Attribute': activity.attribute,
                        'ThingName': activity.thing_name,
                        'Next': next_name,
                    }
                }

            cfn_export_dict['PipelineActivities'].append(activity_dict)
            idx += 1

        # finish with a Datastore activity
        cfn_export_dict['PipelineActivities'].append({
            'Datastore':{
                'Name': "DatastoreActivity",
                'DatastoreName': troposphere.Ref(iotap_datastore_resource),
            }
        })

        iotpipeline_resource = troposphere.iotanalytics.Pipeline.from_dict(
            iotpipeline_logical_id,
            cfn_export_dict,
        )
        self.template.add_resource(iotpipeline_resource)

        self.create_output(
            title='PipelineName',
            description='IoT Analytics Pipeline name',
            value=troposphere.Ref(iotpipeline_resource),
            ref=self.resource.paco_ref_parts + '.pipeline.name',
        )

    def resolve_ref(self, ref):
        if ref.resource_ref == 'channel.name':
            return self.stack.get_outputs_value('ChannelName')
        elif ref.resource_ref == 'datastore.name':
            return self.stack.get_outputs_value('DatastoreName')
        elif ref.resource_ref == 'pipeline.name':
            return self.stack.get_outputs_value('PipelineName')


def convert_expire_to_cfn_dict(expire):
    if expire == 0:
        return {'Unlimited': True}
    else:
        return {'Unlimited': False, 'NumberOfDays': expire}