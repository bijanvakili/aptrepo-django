
def get_repository_controller(logger=None):
    """
    Returns an instance to the repository controller
    
    logger - (optional) overrides the default logger
    """
    import repository
    return repository.Repository(logger=logger)
