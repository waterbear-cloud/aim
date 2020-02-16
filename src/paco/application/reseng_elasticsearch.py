from paco import cftemplates
from paco.application.res_engine import ResourceEngine

class ElasticsearchDomainResourceEngine(ResourceEngine):

    def init_resource(self):

        # Create ServiceLinked Role
        if self.resource.segment != None:
            # Check if this Role has been already created
            iam_ctl = self.paco_ctx.get_controller('IAM')
            iam_ctl.add_service_linked_role(
                self.paco_ctx,
                self.account_ctx,
                self.aws_region,
                self.stack_group,
                self.resource,
                'es.amazonaws.com'
            )

        # Elasticsearch Domain CloudFormation
        cftemplates.ElasticsearchDomain(
            self.paco_ctx,
            self.account_ctx,
            self.aws_region,
            self.stack_group,
            self.stack_tags,
            self.env_ctx,
            self.grp_id,
            self.res_id,
            self.resource,
        )
