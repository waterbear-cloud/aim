"""
Loads aim.models.schemas and generates the doc file at ./doc/aim-config.rst
from the schema definition.
"""

import os.path
import zope.schema
from aim.models import schemas

aim_config_template = """
.. _aim-config:

What is AIM Configuration?
==========================

AIM configuration is intended to be a complete description of an cloud Infrastructure-as-Code
project. These files semantically describe cloud resources and logical groupings of those
resources. The contents of these files describe accounts, networks,
environments, applications, services, and monitoring configuration.

The AIM configuration files are parsed into a Python object model by the library
``aim.models``. This object model is used by AIM Orchestration to provision
AWS resources using CloudFormation. However, the object model is a standalone
Python package and can be used to work with cloud infrastructure semantically for
other uses.


File format overview
--------------------

AIM configuration is a directory of files and sub-directories that
make up an AIM project. All of the files are in YAML_ format.

In the top-level directory are sub-directories that contain YAML
files each with a different format. This directories are:

  * ``Accounts/``: Each file in this directory is an AWS account.

  * ``NetworkEnvironments/``: This is the main show, each file in this
    directory defines a complete set of networks, applications and environments.
    These can be provisioned into any of the accounts.

  * ``MonitorConfig/``: These contain alarms and log source information.
    These alarms and log sources can be used in NetworkEnvironments.

  * ``Services/``: These contain global or shared resources, such as
    S3 Buckets, IAM Users, EC2 Keypairs.

Also at the top level is a ``project.yaml`` file. Currently this file just
contains ``name:`` and ``title:`` attributes.

Most of the YAML files are hierarchical dictionaries. Depending on where
the dictionary key name is within this hierarchy, it will map to an AIM schema.
An AIM schema is a collection of fields. Every field has a name, data type and constraints,
you can think of AIM schemas like SQL table descriptions.

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

Some key names are containers. For containers, every key name must contain attributes
that map to an AIM schema. Objects in containers have a special ``name`` attribute,
this attribute isn't set normally but is instead derived from the key name.

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


Container names are special in the configuration, as they can be concatenated together
to generate CloudFormation and AWS resource names. Since they are used this way,
container names have the following restrictions on them:

  * Can contain only letters, numbers, hyphens and underscores.

  * First character must be a letter.

  * Cannot end with a hyphen or contain two consecutive hyphens.

Certain AWS resources have additional naming limitations, namely S3 bucket names
can not contain uppercase letters and certain resources have a name length of 64 characters.

As the AIM Engine generates names by joining together keys in the hiearchy, it is recommended
to keep names as short and sweet as possible.

If you want to have longer, more human readable names, many schemas have a ``title``
field. This field can contain any character except newline. It is used purely for
display, this field may be added as a Tag to resources, so any characters beyond 255
will be truncated there.


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

NetworkEnvironments
===================

NetworkEnvironments are the center of the show. Each file in the
``NetworkEnvironments`` directory can contain information about
networks, applications and environments. These files define how
applications are deployed into networks, what kind of monitoring
and logging the applications have, and which environments they are in.

These files are hierarchical. They can nest many levels deep. At each
node in the hierarchy a different config type is required.

At the top level are three config types: network, applications and environments.

These are simply YAML keys that must be named ``network:``, ``applications:`` and ``environments``:

.. code-block:: yaml

    # my-apps.yaml

    network:
        # network YAML here ...

    applications:
        # applications YAML here ...

    environments:
        # environments YAML here ...

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

{network}

VPC
---

Every network has a ``vpc`` attribute with a VPC config type:

{vpc}

Gateways
--------

There can be NAT Gateways and VPN Gateways.

The ``natgateway`` has this config type:

{natgateway}

The ``vpngateway`` has this config type:

{vpngateway}

{privatehostedzone}

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
                            type: CodePipeBuildDeploy # CodePipeline and CodeBuild CI/CD
                            # configuration goes here ...
                website:
                    type: Application
                    resources:
                        cert:
                            type: ACM
                            # configuration goes here ...
                        alb:
                            type: LBApplication # Application Load Balancer (ALB)
                            # configuration goes here ...
                        webapp:
                            type: ASG # AutoScalingGroup (ASG) of web server instances
                            # configuration goes here ...
                bastion:
                    type: Bastion
                    resources:
                        instance:
                            type: ASG # AutoScalingGroup (ASG) with only 1 instance (self-healing ASG)
                            # configuration goes here ...


Key naming warning: As the key names you choose will be used in the names of resources provisioned
in AWS, they should be as short and simple as possible. If you want to later rename things,
you need to first delete all of your AWS resources under their old name, then recreate them
in a new name. As renaming is not always easy, try to give everything short, reasonable names.
There are ``title:`` fields where you can use human-readable names that can be changed without
breaking anything.

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

"""

def convert_schema_to_list_table(schema):
    output = [
"""
{name}
{divider}

.. _{name}:

.. list-table::
    :widths: 15 8 6 12 30
    :header-rows: 1

    * - Field name
      - Type
      - Required?
      - Default
      - Purpose
""".format(**{
        'name': schema.__name__[1:],
        'divider': len(schema.__name__) * '-'
    })]
    table_row_template = '    * - {name}\n' + \
    '      - {type}\n' + \
    '      - {required}\n' + \
    '      - {default}\n' + \
    '      - {desc}\n'
    for fieldname in sorted(zope.schema.getFields(schema).keys()):
        field = schema[fieldname]
        desc = field.title
        if field.required:
            req_icon = '.. fa:: check'
        else:
            req_icon = '.. fa:: times'
        if field.description:
            desc = desc + ': ' + field.description

        data_type = field.__class__.__name__
        if data_type in ('TextLine', 'Text'):
            data_type = 'String'
        if data_type == 'Bool':
            data_type = 'Boolean'
        if data_type == 'Object':
            data_type = 'Object of type {}_'.format(field.schema.__name__[1:])

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
                        'desc': desc
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
                }
            )
        )
    print('Wrote to {}'.format(aim_config_doc))
