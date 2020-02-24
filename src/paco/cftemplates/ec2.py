from paco.cftemplates.cftemplates import StackTemplate
from paco.cftemplates.cftemplates import StackOutputParam
from paco.models.references import Reference


# ToDo: this template is old, early code and hasn't been tested in forever
# and it's API calls are really old school
class EC2(StackTemplate):
    def __init__(self, stack, paco_ctx, netenv_name, env_name, app_name):
        ec2_config = stack.resource
        super().__init__(stack, paco_ctx)
        self.set_aws_name('EC2', self.resource_group_name, self.resource.name)

        # Initialize Parameters
        instance_name = self.create_resource_name_join(
            [netenv_name, env_name, app_name, self.resource.name],
            '-',
            True
        )
        self.set_parameter('InstanceName', instance_name)
        self.set_parameter('AssociatePublicIpAddress', ec2_config.associate_public_ip_address)
        self.set_parameter('InstanceAMI', ec2_config.instance_ami)
        self.set_parameter('KeyName', ec2_config.instance_key_pair)

        # Segment SubnetList is a Segment stack Output based on availability zones
        segment_stack = self.env_ctx.get_segment_stack(ec2_config.segment)
        subnet_list_output_key = 'SubnetList1'
        self.set_parameter(StackOutputParam('SubnetId', segment_stack, subnet_list_output_key, self))

        # Security Group List
        # TODO: Use self.create_cfn_ref_list_param()
        sg_output_param = StackOutputParam('SecurityGroupIds', param_template=self)
        for sg_ref in ec2_config.security_groups:
            # TODO: Better name for self.get_stack_outputs_key_from_ref?
            security_group_stack = self.paco_ctx.get_ref(sg_ref)
            sg_output_key = self.get_stack_outputs_key_from_ref(Reference(sg_ref))
            sg_output_param.add_stack_output(security_group_stack, sg_output_key)
        self.set_parameter(sg_output_param)

        self.set_parameter('InstanceType', ec2_config.instance_type)
        self.set_parameter('InstanceIAMProfileName', ec2_config.instance_iam_profile)
        self.set_parameter('RootVolumeSizeGB', ec2_config.root_volume_size_gb)

        self.set_parameter('DisableApiTermination', ec2_config.disable_api_termination)
        self.set_parameter('PrivateIpAddress', ec2_config.private_ip_address)

        self.set_parameter('UserData', ec2_config.user_data)

        # Define the Template
        template_fmt = """
---
AWSTemplateFormatVersion: "2010-09-09"

Description: EC2 Instance

Parameters:

  InstanceAMI:
    Description: AMI to launch EC2 with.
    Type: String

  KeyName:
    Description: EC2 key pair name.
    Type: AWS::EC2::KeyPair::KeyName

  SubnetId:
    Description: The ID of the subnet where the instance will be launched.
    Type: AWS::EC2::Subnet::Id

  SecurityGroupIds:
    Description: List of Security Group IDs to attach to the instance.
    Type: List<AWS::EC2::SecurityGroup::Id>

  InstanceType:
    Description: EC2 instance type
    Type: String

  InstanceIAMProfileName:
    Description: The name of the IAM Profile to attach to the instance.
    Type: String

  RootVolumeSizeGB:
    Description: The size EBS volume to attach to the instance.
    Type: String

  DisableApiTermination:
    Description: Boolean indicating whether the instance can be terminated programatically.
    Type: String

  PrivateIpAddress:
    Description: Private IP address to assign to the instance.
    Type: String

  UserData:
    Description: User data script to run at instance launch.
    Type: String

  InstanceName:
    Description: The name of the Instance
    Type: String

  AssociatePublicIpAddress:
    Description: Boolean, if true will assign a Public IP address to the instance
    Type: String

Conditions:
  PrivateIpIsEnabled: !Not [!Equals [!Ref PrivateIpAddress, '']]
  ProfileIsEnabled: !Not [!Equals [!Ref InstanceIAMProfileName, '']]

Resources:

  Instance:
    Type: "AWS::EC2::Instance"
    Properties:
      BlockDeviceMappings:
          - DeviceName: /dev/xvda
            Ebs:
              VolumeSize: !Ref RootVolumeSizeGB
              VolumeType: "gp2"
      NetworkInterfaces:
        - AssociatePublicIpAddress: !Ref AssociatePublicIpAddress
          DeviceIndex: "0"
          GroupSet: !Ref SecurityGroupIds
          SubnetId: !Ref SubnetId
      DisableApiTermination: !Ref DisableApiTermination
      ImageId: !Ref InstanceAMI
      InstanceInitiatedShutdownBehavior: 'stop'
      IamInstanceProfile: !If [ProfileIsEnabled, !Ref InstanceIAMProfileName, !Ref 'AWS::NoValue']
      InstanceType: !Ref InstanceType
      KeyName: !Ref KeyName
      PrivateIpAddress:
        !If [PrivateIpIsEnabled, !Ref PrivateIpAddress, !Ref "AWS::NoValue"]
      Tags:
        - Key: Name
          Value: !Ref InstanceName
#      UserData:
#        Fn::Base64: !Ref UserData

#################### Outputs ###################################
Outputs:
  InstanceId:
    Value: !Ref Instance
"""
        self.register_stack_output_config(ec2_config.paco_ref_parts + '.id', 'InstanceId')

        self.set_template(template_fmt)

