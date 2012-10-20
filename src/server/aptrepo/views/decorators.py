from functools import wraps
import httplib
import logging
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.http import HttpResponse
from server.aptrepo.util import AuthorizationException


def handle_exception(request_handler_func):
    """
    Decorator function for handling exceptions and converting them
    to the appropriate response for the web client
    """
    @wraps(request_handler_func)
    def wrapper_handler(*args, **kwargs):
        logger = logging.getLogger(settings.DEFAULT_LOGGER)

        try:
            return request_handler_func(*args, **kwargs)
        except ObjectDoesNotExist as e:
            logger.info(e)
            return HttpResponse(str(e), 
                                content_type='text/plain', 
                                status=httplib.NOT_FOUND)
        except AuthorizationException as e:
            logger.info(e)
            return HttpResponse(str(e), 
                                content_type='text/plain', 
                                status=httplib.UNAUTHORIZED)
        except Exception as e:
            logger.exception(e)
            if settings.DEBUG:
                raise e
            else:
                return HttpResponse(str(e), 
                                    content_type='text/plain', 
                                    status=httplib.INTERNAL_SERVER_ERROR)
    
    return wrapper_handler
