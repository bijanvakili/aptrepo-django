from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from server.aptrepo.views import get_repository_controller
from server.aptrepo.models import Section
from server.aptrepo.management.util import parse_section_identifier, init_cli_logger

class Command(BaseCommand):
    """
    'prune' admin command
    """
    args = '[distribution:section ...]'
    help = 'Removes old package versions from the specific sections in the repository'
    option_list = (
        make_option('--dry-run',
            action='store_true',
            dest='readonly',
            default=False,
            help='Do not persist any pruning actions'),
        ) + BaseCommand.option_list 

    def handle(self, *args, **options):
        
        logger = init_cli_logger(options)
        
        try:
            # parse section list
            section_id_list = []
            if len(args) == 0:
                section_id_list = Section.objects.all().values_list(
                    'id', flat=True).order_by('distribution__name', 'name')
            else:
                for arg in args:
                    section_id = parse_section_identifier(arg)
                    section_id_list.append(section_id)

            # prune the section list            
            repository = get_repository_controller(logger)
            repository.prune_sections(section_id_list, dry_run=options['readonly'])
            
        except Exception as e:
            raise CommandError(e)
