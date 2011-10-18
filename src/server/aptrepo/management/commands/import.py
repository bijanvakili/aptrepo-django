import os
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from server.aptrepo.views import get_repository_controller
from server.aptrepo.management.util import parse_section_identifier, init_cli_logger

class Command(BaseCommand):
    """
    'import' admin command
    """
    args = '<distribution>:<section> <dir> [<dir> ...]'
    help = 'Imports package files from local file system into the repository'
    option_list = (
        make_option('--recursive',
            action='store_true',
            dest='recursive',
            default=False,
            help='Check all subdirectories for packages'),
        make_option('--failfast',
            action='store_false',
            dest='ignore_errors',
            default=True,
            help='Abort if a single package fails to be imported'),
        make_option('--dry-run',
            action='store_true',
            dest='readonly',
            default=False,
            help='Do not persist any pruning actions'),
        ) + BaseCommand.option_list 

    def handle(self, *args, **options):

        logger = init_cli_logger(options)

        try:
            # parse and verify the parameters
            if len(args) < 2:
                raise CommandError('Invalid command line')

            section_id = parse_section_identifier(args[0])
            dirs = args[1:]
            for dir in dirs:
                if not os.path.exists(dir):
                    raise CommandError('Directory does not exist: ' + dir)

            # import packages from the specified directories
            repository = get_repository_controller(logger)
            for dir in dirs:
                repository.import_dir(section_id=section_id, dir_path=dir,
                                      dry_run=options['readonly'], 
                                      recursive=options['recursive'],
                                      ignore_errors=options['ignore_errors'])

        except Exception as e:
            raise CommandError(e)
    