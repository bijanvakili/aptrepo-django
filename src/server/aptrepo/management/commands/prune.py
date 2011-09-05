import logging
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from server.aptrepo.repository import Repository
from server.aptrepo.models import PackageInstance, Section

class Command(BaseCommand):
    args = '<distribution:section distribution:section ...>'
    help = 'Removes old package versions from the specific sections in the repository'
    option_list = (
        make_option('--dry-run',
            action='store_true',
            dest='readonly',
            default=False,
            help='Do not persist any pruning actions'),
        ) + BaseCommand.option_list 

    def handle(self, *args, **options):
        
        logger = logging.getLogger('aptrepo.prune')
        
        # if marked silent, filter any logging output except errors
        if options['verbosity'] == '0':
            logger.setLevel(logging.ERROR)
        elif options['verbosity'] == '2':
            logger.setLevel(logging.DEBUG)
        
        try:
            # parse section list
            section_id_list = []
            if len(args) == 0:
                section_id_list = Section.objects.all().values_list(
                    'id', flat=True).order_by('distribution__name', 'name')
            else:
                for arg in args:
                    try:
                        (distribution_name, section_name) = arg.split(':')
                    except Exception:
                        raise CommandError('Invalid section identifier: {0}'.format(arg))
                    
                    try:
                        section = Section.objects.get(name=section_name,
                                                      distribution__name=distribution_name)
                        section_id_list.append(section.id)
                    except Exception:
                        raise CommandError('Section does not exist: {0}'.format(arg))
                        

            # prune the section list            
            repository = Repository()
            repository.prune_sections(section_id_list, dry_run=options['readonly'])
            
        except Exception as e:
            raise CommandError(e)
