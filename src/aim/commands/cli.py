import click
import pkg_resources
from aim.commands.cmd_provision import provision_command
from aim.commands.cmd_init import init_group
from aim.commands.cmd_delete import delete_command
from aim.commands.cmd_describe import describe_command
from aim.commands.cmd_validate import validate_command
from aim.commands.cmd_shell import shell_command
from aim.commands.helpers import pass_aim_context


@click.group()
@click.version_option(
    version=pkg_resources.require("aim")[0].version,
    prog_name="AIM: Application Infrastructure Manager"
)
@pass_aim_context
def cli(ctx):
    """AIM: Application Infrastructure Manager"""
    pass

cli.add_command(init_group)
cli.add_command(validate_command)
cli.add_command(provision_command)
cli.add_command(delete_command)
#cli.add_command(describe_command)
#cli.add_command(shell_command)
