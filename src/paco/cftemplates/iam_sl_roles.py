from paco.cftemplates.cftemplates import StackTemplate
import troposphere.iam


class IAMSLRoles(StackTemplate):
    def __init__(self, stack, paco_ctx, servicename):
        normalized_servicename = servicename.replace('.','')
        config_ref = 'resource.iam.servicelinkedrole' + '.' + normalized_servicename
        super().__init__(
            paco_ctx,
            account_ctx,
            aws_region,
            config_ref,
            iam_capabilities=["CAPABILITY_NAMED_IAM"],
            stack_group=stack_group,
        )
        self.set_aws_name('SLRole', normalized_servicename)

        # Troposphere Template Generation
        self.init_template('ServiceLinked Role: {}'.format(servicename))

        # Resource
        sl_role = troposphere.iam.ServiceLinkedRole(
            'ESServiceLinkedRole',
            template=self.template,
            AWSServiceName='es.amazonaws.com',
            Description='Role for ES to access resources in my VPC',
        )

        # All Done
        self.set_template()
