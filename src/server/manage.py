#!/usr/bin/env python
import os
import sys
from django.core.management import execute_manager
from django.utils.translation import ugettext as _
try:
    import settings # Assumed to be in the same directory.
    if not os.path.exists(settings.APTREPO_ROOT):
        print >>sys.stderr, _('APTREPO_ROOT must be specified')
        sys.exit(1)
    
except ImportError:
    print >>sys.stderr, _("'settings.py' not found or invalid")
    sys.exit(1)

if __name__ == "__main__":
    execute_manager(settings)
