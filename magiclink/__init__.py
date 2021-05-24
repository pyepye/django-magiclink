from django import VERSION

if VERSION[:2] < (3, 2):  # for Django < 3.2
    default_app_config = 'magiclink.apps.MagiclinkConfig'
