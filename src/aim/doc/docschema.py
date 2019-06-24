"""
Loads aim.models.schemas and generates the doc file at ./doc/aim-config.rst
from the schema definition.
"""

import os.path
import zope.schema
from aim.models import schemas

aim_config_template = """
.. _aim-config:

AIM Configuration Overview
==========================

AIM configuration is intended to be a complete declarative description of an Infrastructure-as-Code
cloud project. These files semantically describe cloud resources and logical groupings of those
resources. The contents of these files describe accounts, networks, environments, applications,
services, and monitoring configuration.

The AIM configuration files are parsed into a Python object model by the library
``aim.models``. This object model is used by AIM Orchestration to provision
AWS resources using CloudFormation. However, the object model is a standalone
Python package and can be used to work with cloud infrastructure semantically
with other tooling.


File format overview
--------------------

AIM configuration is a directory of files and sub-directories that
make up an AIM project. All of the files are in YAML_ format.

In the top-level directory are sub-directories that contain YAML
files each with a different format. This directories are:

  * ``Accounts/``: Each file in this directory is an AWS account.

  * ``NetworkEnvironments/``: This is the main show. Each file in this
    directory defines a complete set of networks, applications and environments.
    These can be provisioned into any of the accounts.

  * ``MonitorConfig/``: These contain alarm and log source information.

  * ``Services/``: These contain global or shared resources, such as
    S3 Buckets, IAM Users, EC2 Keypairs.

Also at the top level is a ``project.yaml`` file. Currently this file just
contains ``name:`` and ``title:`` attributes, but may be later extended to
contain useful global project configuration.

The YAML files are organized as nested key-value dictionaries. In each sub-directory,
key names map to relevant AIM schemas. An AIM schema is a set of fields that describe
the field name, type and constraints.

An example of how this hierarchy looks, in a NetworksEnvironent file, a key name ``network:``
must have attributes that match the Network schema. Within the Network schema there must be
an attribute named ``vpc:`` which contains attributes for the VPC schema. That looks like this:

.. code-block:: yaml

    network:
        enabled: true
        region: us-west-2
        availability_zones: 2
        vpc:
            enable_dns_hostnames: true
            enable_dns_support: true
            enable_internet_gateway: true

Some key names map to AIM schemas that are containers. For containers, every key must contain
a set of key/value pairs that map to the AIM schema that container is for.
Every AIM schema in a container has a special ``name`` attribute, this attribute is derived
from the key name used in the container.

For example, the NetworkEnvironments has a key name ``environments:`` that maps
to an Environments container object. Environments containers contain Environment objects.

.. code-block:: yaml

    environments:
        dev:
            title: Development
        staging:
            title: Staging
        prod:
            title: Production

When this is parsed, there would be three Environment objects:

.. code-block:: text

    Environment:
        name: dev
        title: Development
    Environment:
        name: staging
        title: Staging
    Environment:
        name: prod
        title: Production

.. Attention:: Key naming warning: As the key names you choose will be used in the names of
    resources provisioned in AWS, they should be as short and simple as possible. If you wanted
    rename keys, you need to first delete all of your AWS resources under their old key names,
    then recreate them with their new name. Try to give everything short, reasonable names.

Key names have the following restrictions:

  * Can contain only letters, numbers, hyphens and underscores.

  * First character must be a letter.

  * Cannot end with a hyphen or contain two consecutive hyphens.

Certain AWS resources have additional naming limitations, namely S3 bucket names
can not contain uppercase letters and certain resources have a name length of 64 characters.

The ``title`` field is available in almost all AIM schemas. This is intended to be
a human readable name. This field can contain any character except newline.
The ``title`` field can also be added as a Tag to resources, so any characters
beyond 255 characters would be truncated.

References
----------

Some values can be special references. These will allow you to reference other values in
your AIM Configuration.

 * ``netenv.ref``: NetworkEnvironment reference

 * ``service.ref``: Service reference

 * ``config.ref``: Config reference


YAML Gotchas
------------

YAML allows unquoted scalar values. For the account_id field you could write:


.. code-block:: yaml

    account_id: 00223456789

However, when this field is read by the YAML parser, it will attempt to convert this to an integer.
Instead of the string '00223456789', the field will be an integer of 223456789.

You can quote scalar values in YAML with single quotes or double quotes:

.. code-block:: yaml

    account_id: '00223456789' # single quotes can contain double quote characters
    account_id: "00223456789" # double quotes can contain single quote characters

.. _YAML: https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html

Accounts
========

AWS account information is kept in the ``Accounts/`` directory.
Each file in this directory will define one AWS account, the filename
will be the ``name`` of the account, with a .yml or .yaml extension.

{account}

{adminiamuser}

NetworkEnvironments
===================

NetworkEnvironments are the center of the show. Each file in the
``NetworkEnvironments`` directory can contain information about
networks, applications and environments. These files define how
applications are deployed into networks, what kind of monitoring
and logging the applications have, and which environments they are in.

These files are hierarchical. They can nest many levels deep. At each
node in the hierarchy a different config type is required. At the top level
there must be three key names, ``network:``, ``applications:`` and ``environments:``.
The ``network:`` must contain a key/value pairs that match a NetworkEnvironment AIM schema.
The ``applications:`` and ``environments:`` are containers that hold Application
and Environment AIM schemas.

.. code-block:: yaml

    network:
        availability_zones: 2
        enabled: true
        region: us-west-2
        # more network YAML here ...

    applications:
        my-aim-app:
            managed_updates: true
            # more application YAML here ...
        reporting-app:
            managed_updates: false
            # more application YAML here ...

    environments:
        dev:
            title: Development Environment
            # more environment YAML here ...
        prod:
            title: Production Environment
            # more environment YAML here ...

The network and applications configuration is intended to describe a complete default configuration - this configuration
does not get direclty provisioned to the cloud though - think of it as templated configuration. Environments are where
cloud resources are declared to be provisioned. Environments stamp the default network configuration and declare it should
be provisioned into specific account. Applications are then named in Environments, to indicate that the default application
configuration should be copied into that environment's network.

In environments, any of the default configuration can be overridden. This could be used for running a smaller instance size
in the dev environment than the production environment, applying detailed monitoring metrics to a production environment,
or specifying a different git branch name for a CI/CD for each environment.

Network
=======

The network config type defines a complete logical network: VPCs, Subnets, Route Tables, Network Gateways. The applications
defined later in this file will be deployed into networks that are built from this network template.

Networks have the following hierarchy:

.. code-block:: yaml

    network:
        # general config here ...
        vpc:
            # VPC config here ...
            nat_gateway:
                # NAT gateways container
            vpn_gateway:
                # VPN gateways container
            private_hosted_zone:
                # private hosted zone config here ...
            security_groups:
                # security groups here ...

.. Attention:: SecurityGroups is a special two level container. The first key will match the name of an application defined
    in the ``applications:`` section. The second key must match the name of a resource defined in the application.
    In addition, a SecurityGroup has egress and ingress rules that are a list of rules.

    The following example has two SecurityGroups for the application named ``my-web-app``: ``lb`` which will apply to the load
    balancer and ``webapp`` which will apply to the web server AutoScalingGroup.

    .. code-block:: yaml

        network:
            vpc:
                security_groups:
                    my-web-app:
                        lb:
                            egress:
                                - cidr_ip: 0.0.0.0/0
                                  name: ANY
                                  protocol: "-1"
                            ingress:
                                - cidr_ip: 128.128.255.255/32
                                  from_port: 443
                                  name: HTTPS
                                  protocol: tcp
                                  to_port: 443
                                - cidr_ip: 128.128.255.255/32
                                  from_port: 80
                                  name: HTTP
                                  protocol: tcp
                                  to_port: 80
                        webapp:
                            egress:
                                - cidr_ip: 0.0.0.0/0
                                  name: ANY
                                  protocol: "-1"
                            ingress:
                                - from_port: 80
                                  name: HTTP
                                  protocol: tcp
                                  source_security_group_id: netenv.ref aimdemo.network.vpc.security_groups.app.lb.id
                                  to_port: 80

{network}

{vpc}

{natgateway}

{vpngateway}

{privatehostedzone}

{segment}

{securitygroup}

{egressrule}

{ingressrule}

Applications
============

Applications define a collection of AWS resources that work together to support a workload.

Applications specify the sets of AWS resources needed for an application workload.
Applications contain a mandatory ``groups:`` field which is container of ResrouceGroup objects.
Every AWS resource for an application must be contained in a ResrouceGroup with a unique name, and every
ResourceGroup has a Resources container where each Resource is given a unique name.

In the example below, the ``groups:`` contain keys named ``cicd``, ``website`` and ``bastion``.
In turn, each ResourceGroup contains ``resources:`` with names such as ``cpbd``, ``cert`` and ``alb``.

.. code-block:: yaml

    applications:
        my-aim-app:
            enabled: true
            groups:
                cicd:
                    type: Deployment
                    resources:
                        cpbd:
                            # CodePipeline and CodeBuild CI/CD
                            type: CodePipeBuildDeploy
                            # configuration goes here ...
                website:
                    type: Application
                    resources:
                        cert:
                            type: ACM
                            # configuration goes here ...
                        alb:
                            # Application Load Balancer (ALB)
                            type: LBApplication
                            # configuration goes here ...
                        webapp:
                            # AutoScalingGroup (ASG) of web server instances
                            type: ASG
                            # configuration goes here ...
                bastion:
                    type: Bastion
                    resources:
                        instance:
                            # AutoScalingGroup (ASG) with only 1 instance (self-healing ASG)
                            type: ASG
                            # configuration goes here ...


{applications}

{application}

{resourcegroups}

{resourcegroup}

{resources}

{resource}


Environments
============

Environments define how the real AWS resources will be provisioned.
As environments copy the defaults from ``network`` and ``applications`` config,
they can define complex cloud deployments very succinctly.

The top level environments are simply a name and a title. They are logical
groups of actual environments.

.. code-block:: yaml

    environments:

        dev:
            title: Development

        staging:
            title: Staging and QA

        prod:
            title: Production


Environments contain EnvironmentRegions. The name of an EnvironmentRegion must match
a valid AWS region name, or the special ``default`` name, which is used to override
network and application config for a whole environment, regardless of region.

The following example enables the applications named ``marketing-app`` and
``sales-app`` into all dev environments by default. In ``us-west-2`` this is
overridden and only the ``sales-app`` would be deployed there.

.. code-block:: yaml

    environments:

        dev:
            title: Development
            default:
                applications:
                    marketing-app:
                        enabled: true
                    sales-app:
                        enabled: true
            us-west-2:
                applications:
                    marketing-app:
                        enabled: false
            ca-central-1:
                enabled: true

{environments}

{environment}

{environmentregion}

Services
========

Services need to be documented.

MonitorConfig
=============

This directory can contain two files: ``alarmsets.yaml`` and ``logsets.yaml``. These files
contain CloudWatch Alarm and CloudWatch Agent Log Source configuration. These alarms and log sources
are grouped into named sets, and sets of alarms and logs can be applied to resources.

Currently only support for CloudWatch, but it is intended in the future to support other alarm and log sets.

AlarmSets are first named by AWS Resource Type, then by the name of the AlarmSet. Each name in an AlarmSet is
an Alarm.


.. code-block:: yaml

    # AutoScalingGroup alarms
    ASG:
        launch-health:
            GroupPendingInstances-Low:
                # alarm config here ...
            GroupPendingInstances-Critical:
                # alarm config here ...

    # Application LoadBalancer alarms
    LBApplication:
        instance-health:
            HealthyHostCount-Critical:
                # alarm config here ...
        response-latency:
            TargetResponseTimeP95-Low:
                # alarm config here ...
            HTTPCode_Target_4XX_Count-Low:
                # alarm config here ...

{alarm}

{logsource}

"""

def convert_schema_to_list_table(schema):
    output = [
"""
{name}
{divider}

.. _{name}:

.. list-table::
    :widths: 15 8 4 12 15 30
    :header-rows: 1

    * - Field name
      - Type
      - Req?
      - Default
      - Constraints
      - Purpose
""".format(**{
        'name': schema.__name__[1:],
        'divider': len(schema.__name__) * '-'
    })]
    table_row_template = '    * - {name}\n' + \
    '      - {type}\n' + \
    '      - {required}\n' + \
    '      - {default}\n' + \
    '      - {constraints}\n'  + \
    '      - {purpose}\n'

    for fieldname in sorted(zope.schema.getFields(schema).keys()):
        field = schema[fieldname]
        if field.required:
            req_icon = '.. fa:: check'
        else:
            req_icon = '.. fa:: times'

        data_type = field.__class__.__name__
        if data_type in ('TextLine', 'Text'):
            data_type = 'String'
        elif data_type == 'Bool':
            data_type = 'Boolean'
        elif data_type == 'Object':
            data_type = '{}_ AIM schema'.format(field.schema.__name__[1:])
        elif data_type == 'Dict':
            if field.value_type:
                data_type = 'Container of {}_ AIM schemas'.format(field.value_type.schema.__name__[1:])
            else:
                data_type = 'Dict'
        elif data_type == 'List':
            if field.value_type and not zope.schema.interfaces.ITextLine.providedBy(field.value_type):
                data_type = 'List of {}_ AIM schemas'.format(field.value_type.schema.__name__[1:])
            else:
                data_type = 'List of Strings'

        # don't display the name field, it is derived from the key
        name = field.getName()
        if name != 'name' or not schema.extends(schemas.INamed):
            output.append(
                table_row_template.format(
                    **{
                        'name': name,
                        'type': data_type,
                        'required': req_icon,
                        'default': field.default,
                        'purpose': field.title,
                        'constraints': field.description,
                    }
                )
            )
    return ''.join(output)


def aim_schema_generate():
    aim_doc = os.path.abspath(os.path.dirname(__file__)).split(os.sep)[:-3]
    aim_doc.append('docs')
    aim_doc.append('aim-config.rst')
    aim_config_doc = os.sep.join(aim_doc)

    with open(aim_config_doc, 'w') as f:
        f.write(
            aim_config_template.format(
                **{'account': convert_schema_to_list_table(schemas.IAccount),
                   'network': convert_schema_to_list_table(schemas.INetwork),
                   'vpc': convert_schema_to_list_table(schemas.IVPC),
                   'natgateway': convert_schema_to_list_table(schemas.INATGateway),
                   'vpngateway': convert_schema_to_list_table(schemas.IVPNGateway),
                   'privatehostedzone': convert_schema_to_list_table(schemas.IPrivateHostedZone),
                   'applications': convert_schema_to_list_table(schemas.IApplicationEngines),
                   'application': convert_schema_to_list_table(schemas.IApplication),
                   'environments': convert_schema_to_list_table(schemas.INetworkEnvironments),
                   'environment': convert_schema_to_list_table(schemas.IEnvironment),
                   'environmentregion': convert_schema_to_list_table(schemas.IEnvironmentRegion),
                   'resourcegroups': convert_schema_to_list_table(schemas.IResourceGroups),
                   'resourcegroup': convert_schema_to_list_table(schemas.IResourceGroup),
                   'resources': convert_schema_to_list_table(schemas.IResources),
                   'resource': convert_schema_to_list_table(schemas.IResource),
                   'alarmset': convert_schema_to_list_table(schemas.IAlarmSet),
                   'alarm': convert_schema_to_list_table(schemas.ICloudWatchAlarm),
                   'logsource': convert_schema_to_list_table(schemas.ICWAgentLogSource),
                   'adminiamuser': convert_schema_to_list_table(schemas.IAdminIAMUser),
                   'segment': convert_schema_to_list_table(schemas.ISegment),
                   'securitygroup': convert_schema_to_list_table(schemas.ISecurityGroup),
                   'egressrule': convert_schema_to_list_table(schemas.IEgressRule),
                   'ingressrule': convert_schema_to_list_table(schemas.IIngressRule),
                }
            )
        )
    print('Wrote to {}'.format(aim_config_doc))
