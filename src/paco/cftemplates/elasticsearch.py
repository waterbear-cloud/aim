from paco.cftemplates.cftemplates import CFTemplate
import json
import troposphere
import troposphere.elasticsearch


class ElasticsearchDomain(CFTemplate):
    def __init__(
        self,
        paco_ctx,
        account_ctx,
        aws_region,
        stack_group,
        stack_tags,
        env_ctx,
        grp_id,
        res_id,
        esdomain
    ):
        super().__init__(
            paco_ctx,
            account_ctx,
            aws_region,
            enabled=esdomain.is_enabled(),
            config_ref=esdomain.paco_ref_parts,
            stack_group=stack_group,
            stack_tags=stack_tags,
        )
        self.env_ctx = env_ctx
        self.set_aws_name('ESDomain', grp_id, res_id)
        self.esdomain = esdomain
        self.init_template('Elasticsearch Domain')

        # if disabled on leave an empty placeholder and finish
        if not esdomain.is_enabled():
            return self.set_template()

        # Parameters
        elasticsearch_version_param = self.create_cfn_parameter(
            name='ElasticsearchVersion',
            param_type='String',
            description='The version of Elasticsearch to use, such as 2.3.',
            value=self.esdomain.elasticsearch_version
        )

        if esdomain.segment != None:
            subnet_params = []
            segment_stack = self.env_ctx.get_segment_stack(esdomain.segment)
            if esdomain.cluster != None:
                if esdomain.cluster.zone_awareness_enabled:
                    azs = esdomain.cluster.zone_awareness_availability_zone_count
                else:
                    azs = 1
            else:
                azs = 2
            for az_idx in range(1, azs + 1):
                subnet_params.append(
                    self.create_cfn_parameter(
                        param_type='String',
                        name='ESDomainSubnet{}'.format(az_idx),
                        description='A subnet for the Elasticsearch Domain',
                        value='paco.ref {}.az{}.subnet_id'.format(segment_stack.template.config_ref, az_idx)
                    )
                )

        if esdomain.security_groups:
            security_group_list_param = self.create_cfn_ref_list_param(
                param_type='List<AWS::EC2::SecurityGroup::Id>',
                name='SecurityGroupList',
                description='List of security group ids for the Elasticsearch Domain.',
                value=esdomain.security_groups,
                ref_attribute='id',
            )

        # ElasticsearchDomain resource
        esdomain_logical_id = 'ElasticsearchDomain'
        cfn_export_dict = esdomain.cfn_export_dict
        if esdomain.access_policies_json != None:
            cfn_export_dict['AccessPolicies'] = json.loads(esdomain.access_policies_json)

        # ToDo: VPC currently fails as there needs to be a service-linked role for es.amazonaws.com
        # to allow it to create the ENI
        if esdomain.segment != None:
            cfn_export_dict['VPCOptions'] = {'SubnetIds': [troposphere.Ref(param) for param in subnet_params] }
            if esdomain.security_groups:
                cfn_export_dict['VPCOptions']['SecurityGroupIds'] = troposphere.Ref(security_group_list_param)

        esdomain_resource = troposphere.elasticsearch.ElasticsearchDomain.from_dict(
            esdomain_logical_id,
            cfn_export_dict,
        )
        self.template.add_resource(esdomain_resource)

        # Outputs
        troposphere.Output(
            title='Arn',
            template=self.template,
            Value=troposphere.GetAtt(esdomain_resource, 'Arn'),
            Description='Arn of the domain. The same value as DomainArn.'
        )
        self.register_stack_output_config(esdomain.paco_ref_parts, 'Arn')

        troposphere.Output(
            title='DomainArn',
            template=self.template,
            Value=troposphere.GetAtt(esdomain_resource, "DomainArn"),
            Description='DomainArn of the domain. The same value as Arn.'
        )
        self.register_stack_output_config(esdomain.paco_ref_parts, 'DomainArn')

        troposphere.Output(
            title='DomainEndpoint',
            template=self.template,
            Value=troposphere.GetAtt(esdomain_resource, 'DomainEndpoint'),
            Description="The domain-specific endpoint that's used to submit index, search, and data upload requests to an Amazon ES domain.",
        )
        self.register_stack_output_config(esdomain.paco_ref_parts, 'DomainEndpoint')

        # Let's go home
        self.set_template()
