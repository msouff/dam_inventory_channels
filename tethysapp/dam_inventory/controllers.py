from django.shortcuts import render, reverse, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from tethys_sdk.gizmos import MapView, Button, TextInput, DatePicker, SelectInput, DataTableView, MVDraw, MVView, MVLayer
from tethys_sdk.permissions import permission_required, has_permission

from .model import add_new_dam, get_all_dams, Dam, assign_hydrograph_to_dam
from .app import DamInventory as app
from .helpers import create_hydrograph

from django.utils.safestring import mark_safe
import json
from channels.generic.websocket import AsyncWebsocketConsumer


@login_required()
def home(request):
    """
    Controller for the app home page.
    """
    # Get list of dams and create dams MVLayer:
    dams = get_all_dams()
    features = []
    lat_list = []
    lng_list = []

    for dam in dams:
        lat_list.append(dam.latitude)
        lng_list.append(dam.longitude)

        dam_feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [dam.longitude, dam.latitude],

            },
            'properties': {
                'id': dam.id,
                'name': dam.name,
                'owner': dam.owner,
                'river': dam.river,
                'date_built': dam.date_built
            }
        }
        features.append(dam_feature)

    # Define GeoJSON FeatureCollection
    dams_feature_collection = {
        'type': 'FeatureCollection',
        'crs': {
            'type': 'name',
            'properties': {
                'name': 'EPSG:4326'
            }
        },
        'features': features
    }

    # Create a Map View Layer
    dams_layer = MVLayer(
        source='GeoJSON',
        options=dams_feature_collection,
        legend_title='Dams',
        layer_options={
            'style': {
                'image': {
                    'circle': {
                        'radius': 10,
                        'fill': {'color':  '#d84e1f'},
                        'stroke': {'color': '#ffffff', 'width': 1},
                    }
                }
            }
        },
        feature_selection=True
    )

    # Define view centered on dam locations
    try:
        view_center = [sum(lng_list) / float(len(lng_list)), sum(lat_list) / float(len(lat_list))]
    except ZeroDivisionError:
        view_center = [-98.6, 39.8]

    view_options = MVView(
        projection='EPSG:4326',
        center=view_center,
        zoom=4.5,
        maxZoom=18,
        minZoom=2
    )

    dam_inventory_map = MapView(
        height='100%',
        width='100%',
        layers=[dams_layer],
        basemap='OpenStreetMap',
        view=view_options
    )

    add_dam_button = Button(
        display_text='Add Dam',
        name='add-dam-button',
        icon='glyphicon glyphicon-plus',
        style='success',
        href=reverse('dam_inventory:add_dam')
    )

    context = {
        'dam_inventory_map': dam_inventory_map,
        'add_dam_button': add_dam_button,
        'can_add_dams': has_permission(request, 'add_dams')
    }

    return render(request, 'dam_inventory/home.html', context)


@permission_required('add_dams')
def add_dam(request):
    """
    Controller for the Add Dam page.
    """
    # Default Values
    location = ''
    name = ''
    owner = 'Reclamation'
    river = ''
    date_built = ''

    # Errors
    location_error = ''
    name_error = ''
    owner_error = ''
    river_error = ''
    date_error = ''

    # Handle form submission
    if request.POST and 'add-button' in request.POST:
        # Get values
        has_errors = False
        location = request.POST.get('geometry', None)
        name = request.POST.get('name', None)
        owner = request.POST.get('owner', None)
        river = request.POST.get('river', None)
        date_built = request.POST.get('date-built', None)

        # Validate
        if not location:
            has_errors = True
            location_error = 'Location is required.'

        if not name:
            has_errors = True
            name_error = 'Name is required.'

        if not owner:
            has_errors = True
            owner_error = 'Owner is required.'

        if not river:
            has_errors = True
            river_error = 'River is required.'

        if not date_built:
            has_errors = True
            date_error = 'Date Built is required.'

        if not has_errors:
            # Get value of max_dams custom setting
            max_dams = app.get_custom_setting('max_dams')

            # Query database for count of dams
            Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
            session = Session()
            num_dams = session.query(Dam).count()

            # Only add the dam if we have not exceed max_dams
            if num_dams < max_dams:
                add_new_dam(location=location, name=name, owner=owner, river=river, date_built=date_built)
            else:
                messages.warning(request, 'Unable to add dam "{0}", because the inventory is full.'.format(name))
            
            return redirect(reverse('dam_inventory:home'))

        messages.error(request, "Please fix errors.")

    # Define form gizmos
    initial_view = MVView(
        projection='EPSG:4326',
        center=[-98.6, 39.8],
        zoom=3.5
    )

    drawing_options = MVDraw(
        controls=['Modify', 'Delete', 'Move', 'Point'],
        initial='Point',
        output_format='GeoJSON',
        point_color='#FF0000'
    )

    location_input = MapView(
        height='300px',
        width='100%',
        basemap='OpenStreetMap',
        draw=drawing_options,
        view=initial_view
    )

    name_input = TextInput(
        display_text='Name',
        name='name',
        initial=name,
        error=name_error
    )

    owner_input = SelectInput(
        display_text='Owner',
        name='owner',
        multiple=False,
        options=[('Reclamation', 'Reclamation'), ('Army Corp', 'Army Corp'), ('Other', 'Other')],
        initial=owner,
        error=owner_error
    )

    river_input = TextInput(
        display_text='River',
        name='river',
        placeholder='e.g.: Mississippi River',
        initial=river,
        error=river_error
    )

    date_built = DatePicker(
        name='date-built',
        display_text='Date Built',
        autoclose=True,
        format='MM d, yyyy',
        start_view='decade',
        today_button=True,
        initial=date_built,
        error=date_error
    )

    add_button = Button(
        display_text='Add',
        name='add-button',
        icon='glyphicon glyphicon-plus',
        style='success',
        attributes={'form': 'add-dam-form'},
        submit=True
    )

    cancel_button = Button(
        display_text='Cancel',
        name='cancel-button',
        href=reverse('dam_inventory:home')
    )

    context = {
        'location_input': location_input,
        'location_error': location_error,
        'name_input': name_input,
        'owner_input': owner_input,
        'river_input': river_input,
        'date_built_input': date_built,
        'add_button': add_button,
        'cancel_button': cancel_button,
        'can_add_dams': has_permission(request, 'add_dams')
    }

    return render(request, 'dam_inventory/add_dam.html', context)


@login_required()
def list_dams(request):
    """
    Show all dams in a table view.
    """
    dams = get_all_dams()
    table_rows = []

    for dam in dams:
        table_rows.append(
            (
                dam.name, dam.owner,
                dam.river, dam.date_built
            )
        )

    dams_table = DataTableView(
        column_names=('Name', 'Owner', 'River', 'Date Built', 'Hydrograph'),
        rows=table_rows,
        searching=False,
        orderClasses=False,
        lengthMenu=[ [10, 25, 50, -1], [10, 25, 50, "All"] ],
    )

    context = {
        'dams_table': dams_table,
        'can_add_dams': has_permission(request, 'add_dams')
    }

    return render(request, 'dam_inventory/list_dams.html', context)


@login_required()
def assign_hydrograph(request):
    """
    Controller for the Add Hydrograph page.
    """
    # Get dams from database
    Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
    session = Session()
    all_dams = session.query(Dam).all()

    # Defaults
    dam_select_options = [(dam.name, dam.id) for dam in all_dams]
    selected_dam = None
    hydrograph_file = None

    # Errors
    dam_select_errors = ''
    hydrograph_file_error = ''

    # Case where the form has been submitted
    if request.POST and 'add-button' in request.POST:
        # Get Values
        has_errors = False
        selected_dam = request.POST.get('dam-select', None)

        if not selected_dam:
            has_errors = True
            dam_select_errors = 'Dam is Required.'

        # Get File
        if request.FILES and 'hydrograph-file' in request.FILES:
            # Get a list of the files
            hydrograph_file = request.FILES.getlist('hydrograph-file')

        if not hydrograph_file and len(hydrograph_file) > 0:
            has_errors = True
            hydrograph_file_error = 'Hydrograph File is Required.'

        if not has_errors:
            # Process file here
            success = assign_hydrograph_to_dam(selected_dam, hydrograph_file[0])

            # Provide feedback to user
            if success:
                messages.info(request, 'Successfully assigned hydrograph.')
            else:
                messages.info(request, 'Unable to assign hydrograph. Please try again.')
            return redirect(reverse('dam_inventory:home'))

        messages.error(request, "Please fix errors.")

    dam_select_input = SelectInput(
        display_text='Dam',
        name='dam-select',
        multiple=False,
        options=dam_select_options,
        initial=selected_dam,
        error=dam_select_errors
    )

    add_button = Button(
        display_text='Add',
        name='add-button',
        icon='glyphicon glyphicon-plus',
        style='success',
        attributes={'form': 'add-hydrograph-form'},
        submit=True
    )

    cancel_button = Button(
        display_text='Cancel',
        name='cancel-button',
        href=reverse('dam_inventory:home')
    )

    context = {
        'dam_select_input': dam_select_input,
        'hydrograph_file_error': hydrograph_file_error,
        'add_button': add_button,
        'cancel_button': cancel_button,
        'can_add_dams': has_permission(request, 'add_dams')
    }

    session.close()

    return render(request, 'dam_inventory/assign_hydrograph.html', context)


@login_required()
def hydrograph(request, hydrograph_id):
    """
    Controller for the Hydrograph Page.
    """
    hydrograph_plot = create_hydrograph(hydrograph_id)

    context = {
        'hydrograph_plot': hydrograph_plot,
        'can_add_dams': has_permission(request, 'add_dams')
    }
    return render(request, 'dam_inventory/hydrograph.html', context)


@login_required()
def hydrograph_ajax(request, dam_id):
    """
    Controller for the Hydrograph Page.
    """
    # Get dams from database
    Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
    session = Session()
    dam = session.query(Dam).get(int(dam_id))

    if dam.hydrograph:
        hydrograph_plot = create_hydrograph(dam.hydrograph.id, height='300px')
    else:
        hydrograph_plot = None

    context = {
        'hydrograph_plot': hydrograph_plot,
    }

    session.close()
    return render(request, 'dam_inventory/hydrograph_ajax.html', context)


@login_required()
def index(request):
    return render(request, 'dam_inventory/index.html', {})


@login_required()
def room(request, room_name):
    return render(request, 'dam_inventory/room.html', {
        'room_name_json': mark_safe(json.dumps(room_name))
    })


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'chat_%s' % self.room_name

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))
