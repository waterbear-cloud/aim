from paco import utils
from paco.cftemplates.cftemplates import StackTemplate
from paco.models.references import Reference, is_ref, resolve_ref
import troposphere
import troposphere.cloudfront
import troposphere.route53


class CloudFront(StackTemplate):
    def __init__(self, stack, paco_ctx, factory_name):
        cloudfront_config = stack.resource
        config_ref = stack.stack_ref
        super().__init__(stack, paco_ctx)
        self.set_aws_name('CloudFront', self.resource_group_name, self.resource_name, factory_name)
        origin_access_id_enabled = False

        self.init_template('CloudFront Distribution')
        template = self.template

        target_origin_param = self.create_cfn_parameter(
            param_type='String',
            name='TargetOrigin',
            description='Target Origin',
            value=cloudfront_config.default_cache_behavior.target_origin,
        )

        distribution_config_dict = {
            'Enabled': cloudfront_config.is_enabled(),
            'DefaultRootObject': cloudfront_config.default_root_object,
            'HttpVersion': 'http1.1',
            'DefaultCacheBehavior': {
                'AllowedMethods': cloudfront_config.default_cache_behavior.allowed_methods,
                'DefaultTTL': cloudfront_config.default_cache_behavior.default_ttl,
                'TargetOriginId': troposphere.Ref(target_origin_param),
                'ViewerProtocolPolicy': cloudfront_config.default_cache_behavior.viewer_protocol_policy
            },
            'PriceClass': 'PriceClass_'+cloudfront_config.price_class,
            'ViewerCertificate': {
                'AcmCertificateArn': self.paco_ctx.get_ref('paco.ref ' + self.stack.stack_ref + '.viewer_certificate.arn'),
                'SslSupportMethod': cloudfront_config.viewer_certificate.ssl_supported_method,
                'MinimumProtocolVersion': cloudfront_config.viewer_certificate.minimum_protocol_version
            }
        }
        if cloudfront_config.default_cache_behavior.min_ttl != -1:
            distribution_config_dict['DefaultCacheBehavior']['MinTTL'] = cloudfront_config.default_cache_behavior.min_ttl
        if cloudfront_config.default_cache_behavior.max_ttl != -1:
            distribution_config_dict['DefaultCacheBehavior']['MaxTTL'] = cloudfront_config.default_cache_behavior.max_ttl

        # Domain Alises and Record Sets
        aliases_list = []
        aliases_param_map = {}
        for alias in cloudfront_config.domain_aliases:
            alias_hash = utils.md5sum(str_data=alias.domain_name)
            domain_name_param = 'DomainAlias' + alias_hash
            alias_param = self.create_cfn_parameter(
                param_type='String',
                name=domain_name_param,
                description='Domain Alias CNAME',
                value=alias.domain_name
            )
            aliases_list.append(troposphere.Ref(alias_param))
            aliases_param_map[alias.domain_name] = alias_param

        distribution_config_dict['Aliases'] = aliases_list

        # DefaultcacheBehavior
        # Forward Values
        forwarded_values_config = cloudfront_config.default_cache_behavior.forwarded_values
        forwarded_values_dict = {
            'Cookies': {
                'Forward': 'none',
            },
            'QueryString': str(forwarded_values_config.query_string)
        }
        # Cookies
        if cloudfront_config.s3_origin_exists() == False:
            forwarded_values_dict['Cookies']['Forward'] = forwarded_values_config.cookies.forward
        if len(forwarded_values_config.cookies.whitelisted_names) > 0:
            forwarded_values_dict['Cookies']['WhitelistedNames'] = forwarded_values_config.cookies.whitelisted_names
        # Headers
        if cloudfront_config.s3_origin_exists() == False:
            forwarded_values_dict['Headers'] = cloudfront_config.default_cache_behavior.forwarded_values.headers
        distribution_config_dict['DefaultCacheBehavior']['ForwardedValues'] = forwarded_values_dict

        # Cache Behaviors
        if len(cloudfront_config.cache_behaviors) > 0:
            cache_behaviors_list = []
            target_origin_param_map = {}
            for cache_behavior in cloudfront_config.cache_behaviors:
                target_origin_hash = utils.md5sum(str_data=cache_behavior.target_origin)
                if target_origin_hash not in target_origin_param_map.keys():
                    cb_target_origin_param = self.create_cfn_parameter(
                        param_type='String',
                        name=self.create_cfn_logical_id('TargetOriginCacheBehavior'+target_origin_hash),
                        description='Target Origin',
                        value=cache_behavior.target_origin,
                    )
                    target_origin_param_map[target_origin_hash] = cb_target_origin_param
                else:
                    cb_target_origin_param = target_origin_param_map[target_origin_hash]

                cache_behavior_dict = {
                    'PathPattern': cache_behavior.path_pattern,
                    'AllowedMethods': cache_behavior.allowed_methods,
                    'DefaultTTL': cache_behavior.default_ttl,
                    'TargetOriginId': troposphere.Ref(cb_target_origin_param),
                    'ViewerProtocolPolicy': cache_behavior.viewer_protocol_policy
                }
                cb_forwarded_values_config = cache_behavior.forwarded_values
                cb_forwarded_values_dict = {
                    'Cookies': {
                        'Forward': 'none',
                    },
                    'QueryString': str(cb_forwarded_values_config.query_string)
                }
                # Cookies
                cb_forwarded_values_dict['Cookies']['Forward'] = cb_forwarded_values_config.cookies.forward
                if len(cb_forwarded_values_config.cookies.whitelisted_names) > 0:
                    cb_forwarded_values_dict['Cookies']['WhitelistedNames'] = cb_forwarded_values_config.cookies.whitelisted_names
                # Headers
                if cloudfront_config.s3_origin_exists() == False:
                    cb_forwarded_values_dict['Headers'] = cache_behavior.forwarded_values.headers
                cache_behavior_dict['ForwardedValues'] = cb_forwarded_values_dict
                cache_behaviors_list.append(cache_behavior_dict)

            distribution_config_dict['CacheBehaviors'] = cache_behaviors_list

        # Origin Access Identity
        if cloudfront_config.s3_origin_exists() == True:
            origin_id_res = troposphere.cloudfront.CloudFrontOriginAccessIdentity(
                title = 'CloudFrontOriginAccessIdentity',
                template = template,
                CloudFrontOriginAccessIdentityConfig = troposphere.cloudfront.CloudFrontOriginAccessIdentityConfig(
                    Comment = troposphere.Ref('AWS::StackName')
                )
            )
            troposphere.Output(
                title = 'CloudFrontOriginAccessIdentity',
                template = template,
                Value = troposphere.Ref(origin_id_res)
            )

        # Origins
        origins_list = []
        for origin_name, origin in cloudfront_config.origins.items():
            if origin.s3_bucket != None:
                domain_hash = utils.md5sum(str_data=origin.s3_bucket)
                origin_domain_name = self.paco_ctx.get_ref(origin.s3_bucket+'.url')
            else:
                domain_hash = utils.md5sum(str_data=origin.domain_name)
                origin_domain_name = origin.domain_name
            origin_dict = {
                'Id': origin_name,
                'DomainName': origin_domain_name
            }
            if origin.s3_bucket == None:
                origin_dict['CustomOriginConfig'] = {
                    'HTTPSPort': origin.custom_origin_config.https_port,
                    'OriginKeepaliveTimeout': origin.custom_origin_config.keepalive_timeout,
                    'OriginProtocolPolicy': origin.custom_origin_config.protocol_policy,
                    'OriginReadTimeout': origin.custom_origin_config.read_timeout,
                    'OriginSSLProtocols': origin.custom_origin_config.ssl_protocols
                }
                if origin.custom_origin_config.http_port:
                    origin_dict['CustomOriginConfig']['HTTPPort'] = str(origin.custom_origin_config.http_port)
            else:
                s3_config = self.paco_ctx.get_ref(origin.s3_bucket)
                origin_dict['S3OriginConfig'] = {}
                if s3_config.cloudfront_origin == False:
                    origin_dict['S3OriginConfig']['OriginAccessIdentity'] = ''
                else:
                    origin_access_id_enabled = True
                    param_name = "OriginAccessIdentiy"+domain_hash
                    access_id_ref = origin.s3_bucket+'.origin_id'
                    s3_cf_origin_id_param = self.create_cfn_parameter(
                      param_type='String',
                      name=param_name,
                      description='Origin Access Identity',
                      value=access_id_ref,
                    )
                    origin_dict['S3OriginConfig']['OriginAccessIdentity'] = troposphere.Sub(
                        'origin-access-identity/cloudfront/${OriginAccessId}',
                        {'OriginAccessId': troposphere.Ref(s3_cf_origin_id_param)}
                    )
            origins_list.append(origin_dict)
        distribution_config_dict['Origins'] = origins_list

        # Custom Error
        error_resp_list = []
        for error_resp in cloudfront_config.custom_error_responses:
            error_resp_dict = {
                'ErrorCachingMinTTL': error_resp.error_caching_min_ttl,
                'ErrorCode': error_resp.error_code,
                'ResponseCode': error_resp.response_code,
                'ResponsePagePath': error_resp.response_page_path
            }
            error_resp_list.append(error_resp_dict)
        if len(error_resp_list) > 0:
            distribution_config_dict['CustomErrorResponses'] = error_resp_list

        # Web ACL
        if cloudfront_config.webacl_id != None:
            webacl_id_param = self.create_cfn_parameter(
              param_type='String',
              name='WebAclId',
              description='WAF Web Acl ID',
              value=cloudfront_config.webacl_id
            )
            distribution_config_dict['WebACLId'] = troposphere.Ref(webacl_id_param)

        distribution_dict = {
            'DistributionConfig': distribution_config_dict
        }
        distribution_res = troposphere.cloudfront.Distribution.from_dict(
            'Distribution', distribution_dict )

        if self.paco_ctx.legacy_flag('route53_record_set_2019_10_16') == True:
            if cloudfront_config.is_dns_enabled() == True:
                for alias in cloudfront_config.domain_aliases:
                    alias_hash = utils.md5sum(str_data=alias.domain_name)
                    zone_param_name = 'AliasHostedZoneId' + alias_hash
                    alias_zone_id_param = self.create_cfn_parameter(
                        param_type='String',
                        name=zone_param_name,
                        description='Domain Alias Hosted Zone Id',
                        value=alias.hosted_zone+'.id',
                    )
                    record_set_res = troposphere.route53.RecordSetType(
                        title = self.create_cfn_logical_id_join(['RecordSet', alias_hash]),
                        template = template,
                        HostedZoneId = troposphere.Ref(alias_zone_id_param),
                        Name = troposphere.Ref(aliases_param_map[alias.domain_name]),
                        Type = 'A',
                        AliasTarget = troposphere.route53.AliasTarget(
                            DNSName = troposphere.GetAtt(distribution_res, 'DomainName'),
                            HostedZoneId = 'Z2FDTNDATAQYW2'
                        )
                    )
                    record_set_res.DependsOn = distribution_res

        self.create_output(
            title='CloudFrontURL',
            value=troposphere.GetAtt('Distribution', 'DomainName'),
            ref=self.config_ref + '.domain_name'
        )
        self.create_output(
            title='CloudFrontId',
            value=troposphere.Ref(distribution_res),
            ref=self.config_ref + '.id'
        )

        template.add_resource(distribution_res)

        if origin_access_id_enabled:
          self.stack.wait_for_delete = True

        if self.paco_ctx.legacy_flag('route53_record_set_2019_10_16') == False:
            route53_ctl = self.paco_ctx.get_controller('route53')
            if cloudfront_config.is_dns_enabled() == True:
                for alias in cloudfront_config.domain_aliases:
                    route53_ctl.add_record_set(
                        self.account_ctx,
                        self.aws_region,
                        cloudfront_config,
                        enabled=cloudfront_config.is_enabled(),
                        dns=alias,
                        record_set_type='Alias',
                        alias_dns_name = 'paco.ref ' + self.stack.stack_ref + '.domain_name',
                        alias_hosted_zone_id = 'Z2FDTNDATAQYW2',
                        stack_group=self.stack.stack_group,
                        config_ref=config_ref+'.record_set'
                    )
