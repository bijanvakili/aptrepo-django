import os
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from server.aptrepo.views import get_repository_controller
from server.aptrepo.management.util import parse_section_identifier, init_cli_logger

class Command(BaseCommand):
    """
    'import' admin command
    """
    args = _('<distribution>:<section> <dir> [<dir> ...]')
    help = _('Imports package files from a local directory into the repository')
    option_list = (
        make_option('--recursive',
            action='store_true',
            dest='recursive',
            default=False,
            help=_('Check all subdirectories for packages')),
        make_option('--failfast',
            action='store_false',
            dest='ignore_errors',
            default=True,
            help=_('Abort if a single package fails to be imported')),
        make_option('--dry-run',
            action='store_true',
            dest='readonly',
            default=False,
            help=_('Do not persist any pruning actions')),
        ) + BaseCommand.option_list 

    def handle(self, *args, **options):

        logger = init_cli_logger(options)

        try:
            # parse and verify the parameters
            if len(args) < 2:
                raise CommandError(_('Invalid command line'))

            section_id = parse_section_identifier(args[0])
            dirs = args[1:]
            for dir in dirs:
                if not os.path.exists(dir):
                    raise CommandError(
                        _('Directory does not exist: {0}').format(dir)
                    )

            # import packages from the specified directories
            repository = get_repository_controller(logger, sys_user=True)
            for dir in dirs:
                repository.import_dir(section_id=section_id, dir_path=dir,
                                      dry_run=options['readonly'], 
                                      recursive=options['recursive'],
                                      ignore_errors=options['ignore_errors'])

        except Exception as e:
            raise CommandError(e)
    