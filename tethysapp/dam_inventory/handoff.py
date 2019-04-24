import os
import requests
from .app import DamInventory


def csv_internal(request, path_to_csv):
    """
    Handoff handler for csv files.
    """
    # Get a filename in the current user's workspace
    user_workspace = DamInventory.get_user_workspace(request.user)

    # Create symbolic link to the csv in the user's workspace
    src = path_to_csv
    dst = os.path.join(user_workspace.path, 'hydrograph.csv')

    try:
        os.symlink(src, dst)
    except OSError:
        pass

    return 'dam_inventory:home'
