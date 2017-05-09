from tethys_sdk.base import TethysAppBase, url_map_maker


class DamInventory(TethysAppBase):
    """
    Tethys app class for Dam Inventory.
    """

    name = 'Dam Inventory'
    index = 'dam_inventory:home'
    icon = 'dam_inventory/images/icon.gif'
    package = 'dam_inventory'
    root_url = 'dam-inventory'
    color = '#e67e22'
    description = ''
    tags = ''
    enable_feedback = False
    feedback_emails = []


    def url_maps(self):
        """
        Add controllers
        """
        UrlMap = url_map_maker(self.root_url)

        url_maps = (
            UrlMap(
                name='home',
                url='dam-inventory',
                controller='dam_inventory.controllers.home'
            ),
            UrlMap(
                name='add_dam',
                url='dam-inventory/add-dam',
                controller='dam_inventory.controllers.add_dam'
            )
        )

        return url_maps