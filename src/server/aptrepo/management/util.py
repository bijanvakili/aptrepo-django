import logging
from django.core.management.base import CommandError
from server.aptrepo.models import Section

def parse_section_identifier(section_identifier):
    """
    Parsers a section identifier into a section ID
    
    section_identifier -- string in the form <distribution>:<section> which identifies a
                            unique section
    """
    try:
        (distribution_name, section_name) = section_identifier.split(':')
    except Exception:
        raise CommandError('Invalid section identifier: {0}'.format(section_identifier))
    
    try:
        section = Section.objects.get(name=section_name,
                                      distribution__name=distribution_name)
    except Exception:
        raise CommandError('Section does not exist: {0}'.format(section_identifier))

    return section.id


def init_cli_logger(command_options):
    
    logger = logging.getLogger('aptrepo.admin.cli')
    
    # if marked silent, filter any logging output except errors
    if command_options['verbosity'] == '0':
        logger.setLevel(logging.ERROR)
    # otherwise, increase logging verbosity
    elif command_options['verbosity'] == '2':
        logger.setLevel(logging.DEBUG)

    return logger
