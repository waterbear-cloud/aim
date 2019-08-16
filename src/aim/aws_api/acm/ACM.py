import boto3
from botocore.config import Config
import tldextract
from . import aws_helpers
import time


class DNSValidatedACMCertClient():

    def __init__(self, account_ctx, domain, region):
        self.acm_client = account_ctx.get_aws_client('acm', aws_region=region)
        self.route_53_client = account_ctx.get_aws_client(client_name='route53',
                                                          client_config=Config(retries={'max_attempts': 10}))

        self.list_hosted_zones_paginator = self.route_53_client.get_paginator(
        'list_hosted_zones')
        self.route53_zones = self.list_hosted_zones_paginator.paginate().build_full_result()
        self.domain = domain

    def get_certificate_arn_from_response(self, response):
        """ Given an ACM Boto response,
            return the ACM Certificate ARN
        """
        return response.get('CertificateArn')

    def get_certificate_arn(self):
        cert_list = self.acm_client.list_certificates()
        if len(cert_list['CertificateSummaryList']) == 0:
            return None
        for cert_item in cert_list['CertificateSummaryList']:
            if cert_item['DomainName'] == self.domain:
                return cert_item['CertificateArn']
        return None

    def request_certificate(self, subject_alternative_names=[]):
        """ Given a list of (optional) subject alternative names,
            request a certificate and return the certificate ARN.
        """
        cert_arn = self.get_certificate_arn()
        if cert_arn == None:
            if len(subject_alternative_names) > 0:
                response = self.acm_client.request_certificate(
                    DomainName=self.domain,
                    ValidationMethod='DNS',
                    SubjectAlternativeNames=subject_alternative_names)
            else:
                response = self.acm_client.request_certificate(
                    DomainName=self.domain, ValidationMethod='DNS')

            if aws_helpers.response_succeeded(response):
                return self.get_certificate_arn_from_response(response)
            else:
                return None
        else:
            #print("Certificate for %s already exists" % (self.domain))
            return cert_arn

    def get_certificate_status(self, certificate_arn):
        return self.acm_client.describe_certificate(CertificateArn=certificate_arn)['Certificate']['Status']

    def wait_for_certificate_validation(self, certificate_arn, sleep_time=5, timeout=600):
        status = self.get_certificate_status(certificate_arn)
        elapsed_time = 0
        while status == 'PENDING_VALIDATION':
            print("Waiting for certificate validation: timeout in %d seconds" % (timeout-elapsed_time))
            if elapsed_time > timeout:
                raise Exception('Timeout ({}s) reached for certificate validation'.format(timeout))
            #print("{}: Waiting {}s for validation, {}s elapsed...".format(certificate_arn, sleep_time, elapsed_time))
            time.sleep(sleep_time)
            status = self.get_certificate_status(certificate_arn)
            elapsed_time += sleep_time

    def get_domain_validation_records(self, arn):
        """ Return the domain validation records from the describe_certificate
            call for our certificate
        """
        certificate_metadata = self.acm_client.describe_certificate(
            CertificateArn=arn)
        return certificate_metadata.get('Certificate', {}).get(
            'DomainValidationOptions', [])

    def get_hosted_zone_id(self, validation_dns_record):
        """ Return the HostedZoneId of the zone tied to the root domain
            of the domain the user wants to protect (e.g. given www.cnn.com, return cnn.com)
            if it exists in Route53. Else error.
        """

        def get_domain_from_host(validation_dns_record):
            """ Given an FQDN, return the domain
                portion of a host
            """
            domain_tld_info = tldextract.extract(validation_dns_record)
            #print("Domain TLD Info:")
            #print(domain_tld_info)
            return "%s.%s" % (domain_tld_info.domain, domain_tld_info.suffix)

        def domain_matches_hosted_zone(domain, zone):
            #print(zone.get('Name')+ " == " + domain)
            return zone.get('Name') == "%s." % (domain)

        def get_zone_id_from_id_string(zone_id_string):
            return zone_id_string.split('/')[-1]

        domain_tld_info = tldextract.extract(validation_dns_record)
        #print(domain_tld_info)
        hosted_zone_subdomain = domain_tld_info.subdomain
        while True:
            #print("Hosted zone subdomaiun: " + hosted_zone_subdomain)
            hosted_zone_subdomain_list = hosted_zone_subdomain.split(".",1)
            hosted_zone_domain = '.'.join( [domain_tld_info.domain,
                                            domain_tld_info.suffix] )

            if len(hosted_zone_subdomain_list) > 1:
                hosted_zone_subdomain = hosted_zone_subdomain.split(".", 1)[1]
                hosted_zone_domain = '.'.join( [hosted_zone_subdomain,
                                                domain_tld_info.domain,
                                                domain_tld_info.suffix] )


            #print("domain: " + hosted_zone_domain)
            for zone in self.route53_zones.get('HostedZones'):
                if domain_matches_hosted_zone(hosted_zone_domain, zone) == True:
                    return get_zone_id_from_id_string(zone.get('Id'))

        return None

    def get_resource_record_data(self, r):
        """ Given a ResourceRecord dictionary from an ACM certificate response,
            return the type, name and value of the record
        """
        return (r.get('Type'), r.get('Name'), r.get('Value'))

    def create_dns_record_set(self, record):
        """ Given a HostedZoneId and a list of domain validation records,
            create a DNS record set to send to Route 53
        """
        record_type, record_name, record_value = self.get_resource_record_data(
            record.get('ResourceRecord'))
        #print("Creating %s record for %s" % (record_type, record_name))

        return {
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': record_name,
                'Type': record_type,
                'ResourceRecords': [{
                    'Value': record_value
                }],
                'TTL': 300,
            }
        }

    def remove_duplicate_upsert_records(self, original_list):
        unique_list = []
        [unique_list.append(obj) for obj in original_list if obj not in unique_list]
        return unique_list

    def create_domain_validation_records(self, arn):
        """ Given an ACM certificate ARN,
            return the response
        """
        domain_validation_records = self.get_domain_validation_records(arn)

        changes = [
            self.create_dns_record_set(record)
            for record in domain_validation_records
        ]
        unique_changes = self.remove_duplicate_upsert_records(changes)
        for change in unique_changes:
            record_name = change.get('ResourceRecordSet').get('Name')
            hosted_zone_id = self.get_hosted_zone_id(record_name)
            #print("ACM Changing Hosted Zone Id: " + hosted_zone_id)
            #print(change)
            response = self.route_53_client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [change]
            })

            if not aws_helpers.response_succeeded(response):
                print("Failed to create Route53 record set: {}".format(response))
            #else:
            #    print("Successfully created Route 53 record set for {}".format(record_name))
