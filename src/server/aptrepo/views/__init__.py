
def get_repository_controller(logger=None, request=None, sys_user=False):
    """
    Returns an instance to the repository controller
    
    logger - (optional) overrides the default logger
    """
    import repository
    return repository.Repository(logger=logger, request=request, sys_user=sys_user)
