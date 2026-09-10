"""
WSGI config for Kaapool project.
"""

import os
import sys

# Ensure base_dir and apps_dir are on sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
apps_dir = os.path.join(base_dir, 'apps')
if apps_dir not in sys.path:
    sys.path.insert(0, apps_dir)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
