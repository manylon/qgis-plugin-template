# -*- coding: utf-8 -*-
def classFactory(iface):
    """Load Plugin class from file.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .my_plugin import MyPlugin

    return MyPlugin()
