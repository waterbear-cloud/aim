from paco.cftemplates.cftemplates import StackTemplate


class KMS(StackTemplate):
    def __init__(self, stack, paco_ctx, kms_config_dict):
        kms_config_ref = stack.stack_ref
        super().__init__(stack, paco_ctx, iam_capabilities=["CAPABILITY_NAMED_IAM"])
        self.set_aws_name('KMS', self.resource_group_name, self.resource.name)

        # Define the Template
        template_fmt = """
AWSTemplateFormatVersion: '2010-09-09'

Description: KMS Customer Managed Key

#Parameters:

Resources:
  CMK:
    Type: AWS::KMS::Key
    Properties:
      Description: Paco Generic KMS Customer Managed Key
      EnableKeyRotation: true
      KeyPolicy:
        Version: "2012-10-17"
        Id: !Ref AWS::StackName
        Statement:
          - Sid: Allows admin of the key
            Effect: Allow
            Principal:
              AWS:
                - !Sub 'arn:aws:iam::${{AWS::AccountId}}:root'
            Action:
              - "kms:Create*"
              - "kms:Describe*"
              - "kms:Enable*"
              - "kms:List*"
              - "kms:Put*"
              - "kms:Update*"
              - "kms:Revoke*"
              - "kms:Disable*"
              - "kms:Get*"
              - "kms:Delete*"
              - "kms:ScheduleKeyDeletion"
              - "kms:CancelKeyDeletion"
            Resource: "*"
          - Sid: Allow use of the key for CryptoGraphy Lambda
            Effect: Allow
            Principal: {0[key_policy_principal]:s}
            Action:
              - kms:Encrypt
              - kms:Decrypt
              - kms:ReEncrypt*
              - kms:GenerateDataKey*
              - kms:DescribeKey
            Resource: "*"

#  KMSAlias:
#    Type: AWS::KMS::Alias
#    Properties:
#      AliasName: alias/codepipeline-crossaccounts
#      TargetKeyId: !Ref CMK

Outputs:
  CMKArn:
    Value: !GetAtt CMK.Arn

  CMKId:
    Value: !Ref CMK

"""
        principal_yaml = """
              AWS:"""
        for aws_principal in kms_config_dict['crypto_principal']['aws']:
            principal_yaml += """
                - '{0}'""".format(aws_principal)

        template_table = {
            'key_policy_principal': principal_yaml
        }

        self.register_stack_output_config(kms_config_ref+'.arn', 'CMKArn')
        self.register_stack_output_config(kms_config_ref+'.id', 'CMKId')

        self.set_template(template_fmt.format(template_table))

