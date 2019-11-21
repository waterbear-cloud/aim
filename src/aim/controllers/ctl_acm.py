import click
import os
import time
from aim.aws_api.acm import DNSValidatedACMCertClient
from aim.core.exception import StackException
from aim.core.exception import AimErrorCode
from aim.controllers.controllers import Controller


class ACMController(Controller):
    def __init__(self, aim_ctx):
        super().__init__(aim_ctx,
                         "Resource",
                         "ACM")

        self.cert_config_map = {}
        self.cert_config_list = []

        #self.aim_ctx.log("ACM Service: Configuration: %s" % (name))

    def init(self, command=None, model_obj=None):
        pass

    def validate(self):
        #if self.config.enabled() == False:
        #    print("ACM Service: validate: disabled")
        #    return
        pass

    def provision(self):
        """
        Creates a certificate if one does not exists, then adds DNS validation records
        the its Route53 hosted zone.
        """
        for acm_config in self.cert_config_list:
            cert_config = acm_config['config']
            if cert_config.is_enabled() == False:
                continue
            if cert_config.external_resource == True: # or cert_config.is_dns_enabled() == False:
                return
            if 'cert_arn_cache' in acm_config.keys():
                continue
            cert_domain = cert_config.domain_name
            acm_client = DNSValidatedACMCertClient(acm_config['account_ctx'], cert_domain, acm_config['region'])
            # Creates the certificate if it does not exists here.
            self.aim_ctx.log_action_col(
                'Provision', acm_config['account_ctx'].get_name(),
                'ACM', acm_config['region']+': '+cert_config.domain_name+': alt-names: {}'.format(cert_config.subject_alternative_names))
            cert_arn = acm_client.request_certificate(cert_config.subject_alternative_names)
            acm_config['cert_arn_cache'] = cert_arn
            validation_records = None
            while validation_records == None:
                validation_records = acm_client.get_domain_validation_records(cert_arn)
                if len(validation_records) == 0 or 'ResourceRecord' not in validation_records[0]:
                    print("Waiting for DNS Validation records...")
                    self.aim_ctx.log_action_col(
                        'Waiting', acm_config['account_ctx'].get_name(),
                        'ACM', acm_config['region']+': '+cert_config.domain_name)
                    time.sleep(1)
                    validation_records = None

            acm_client.create_domain_validation_records(cert_arn)


    def get_cert_config(self, group_id, cert_id):
        #print("Get Certificate Config: " + group_id + " " + cert_id)
        for config in self.cert_config_map[group_id]:
            if config['id'] == cert_id:
                return config
        return None

    def resolve_ref(self, ref):
        if ref.last_part == 'arn':
            group_id = '.'.join(ref.parts[:-1])
            cert_id = ref.parts[-2]
            res_config = self.get_cert_config(group_id, cert_id)
            if 'cert_arn_cache' in res_config.keys():
                return res_config['cert_arn_cache']
            acm_client = DNSValidatedACMCertClient(res_config['account_ctx'], res_config['config'].domain_name, ref.region)
            if acm_client:
                cert_arn = acm_client.get_certificate_arn()
                if cert_arn == None:
                    self.provision()
                    cert_arn = acm_client.get_certificate_arn()
                if res_config['config'].external_resource == False:
                    acm_client.wait_for_certificate_validation( cert_arn )
                # print("Certificate ARN: " + cert_domain + ": " + cert_arn)
                return cert_arn
            else:
                raise StackException(AimErrorCode.Unknown)
        raise StackException(AimErrorCode.Unknown)

    def add_certificate_config(self, account_ctx, region, group_id, cert_id, cert_config):
        # print("Add Certificate Config: " + group_id + " " + cert_id)
        if group_id not in self.cert_config_map.keys():
            self.cert_config_map[group_id] = []

        map_config = {
            'group_id': group_id,
            'id': cert_id,
            'config': cert_config,
            'account_ctx': account_ctx,
            'region': region
        }
        self.cert_config_map[group_id].append(map_config)
        self.cert_config_list.append(map_config)
        cert_config.resolve_ref_obj = self