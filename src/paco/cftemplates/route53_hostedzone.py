from paco.cftemplates.cftemplates import StackTemplate
import troposphere
import troposphere.route53


class Route53HostedZone(StackTemplate):
    def __init__(self, stack, paco_ctx):
        zone_config = stack.resource
        config_ref = zone_config.paco_ref_parts
        super().__init__(stack, paco_ctx, iam_capabilities=["CAPABILITY_NAMED_IAM"])
        self.set_aws_name('HostedZone', zone_config.name)
        self.init_template('Route53 Hosted Zone: ' + zone_config.domain_name)

        self.paco_ctx.log_action_col("Init", "Route53", "Hosted Zone", "{}".format(zone_config.domain_name))

        hosted_zone_res = None
        if zone_config.external_resource != None and zone_config.external_resource.is_enabled():
            hosted_zone_id_output_value = zone_config.external_resource.hosted_zone_id
            nameservers_output_value = ','.join(zone_config.external_resource.nameservers)
        else:
            hosted_zone_dict = {
                'Name': zone_config.domain_name
            }
            if zone_config.private_hosted_zone == True:
                vpc_id_param = self.create_cfn_parameter(
                        param_type = 'String',
                        name = 'VPCId',
                        description = 'The Id of the VPC where the private hosted zone will be provisioned.',
                        value = zone_config.vpc_associations+'.id'
                    )
                vpc_region = zone_config.vpc_associations.split('.')[4]
                hosted_zone_dict['VPCs'] = [ {
                    'VPCId': troposphere.Ref(vpc_id_param),
                    'VPCRegion': vpc_region
                }]
            hosted_zone_res = troposphere.route53.HostedZone.from_dict(
                'HostedZone', hosted_zone_dict
                )
            self.template.add_resource(hosted_zone_res)
            hosted_zone_id_output_value = troposphere.Ref(hosted_zone_res)
            # NameServers attribute is not supported for private hosted zones
            if zone_config.private_hosted_zone == False:
                nameservers_output_value = troposphere.Join(',', troposphere.GetAtt(hosted_zone_res, 'NameServers'))

        self.create_output(
            title='HostedZoneId',
            value=hosted_zone_id_output_value,
            ref=config_ref+'.id'
        )
        # NameServers attribute is not supported for private hosted zones (except external resources)
        if zone_config.private_hosted_zone == False or (zone_config.external_resource != None and zone_config.external_resource.is_enabled()):
            self.create_output(
                title='HostedZoneNameServers',
                value=nameservers_output_value,
                ref=config_ref+'.name_servers'
            )

        if len(zone_config.record_sets) > 0:
            record_set_list = []
            for record_set_config in zone_config.record_sets:
                record_set_dict = {
                    'Name': record_set_config.record_name,
                }
                if record_set_config.type == 'Alias':
                    record_set_dict['Type'] = 'A'
                    if record_set_config.resource_records[0].find('cloudfront.net') != -1:
                        hosted_zone_id = 'Z2FDTNDATAQYW2'
                    elif record_set_config.resource_records[0].find('elb.amazonaws.com') != -1:
                        elb_region = record_set_config.resource_records[0].split('.')[1]
                        hosted_zone_id = self.lb_hosted_zone_id('alb', elb_region)
                    elif record_set_config.resource_records[0].find('awsglobalaccelerator.com') != -1:
                        hosted_zone_id = 'Z2BJ6XQ5FK7U4H'
                    record_set_dict['AliasTarget'] = troposphere.route53.AliasTarget(
                            HostedZoneId=hosted_zone_id,
                            DNSName=record_set_config.resource_records[0]
                        )
                else:
                    record_set_dict['Type'] = record_set_config.type
                    record_set_dict['ResourceRecords'] = record_set_config.resource_records
                    record_set_dict['TTL'] = record_set_config.ttl

                record_set_res = troposphere.route53.RecordSet(**record_set_dict)
                record_set_list.append(record_set_res)

            if zone_config.external_resource != None and zone_config.external_resource.is_enabled():
                hosted_zone_id = zone_config.external_resource.hosted_zone_id
            else:
                hosted_zone_id = troposphere.Ref(hosted_zone_res)

            group_res = troposphere.route53.RecordSetGroup(
                title='RecordSetGroup',
                template=self.template,
                HostedZoneId=hosted_zone_id,
                RecordSets=record_set_list
            )
            if zone_config.external_resource == None or zone_config.external_resource.is_enabled() == False:
                group_res.DependsOn = hosted_zone_res
