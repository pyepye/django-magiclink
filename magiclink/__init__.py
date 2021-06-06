from django import get_version
from packaging import version

"""
To stop waring:
    RemovedInDjango41Warning: 'magiclink' defines
    default_app_config = 'magiclink.apps.MagiclinkConfig'. Django now detects
    this configuration automatically. You can remove default_app_config.
"""
if version.parse(get_version()) < version.parse('3.2'):  # pragma: no cover
    default_app_config = 'magiclink.apps.MagiclinkConfig'
