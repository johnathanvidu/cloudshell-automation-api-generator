import cloudshell_scripts_helpers as helpers
import os
import json
import string
from cloudshell.api.cloudshell_api import ReservationDescriptionInfo

CONNECTIVITY_DETAILS_TEMPLATE = '"tsAPIPort": "{cloudshell_api_port}",'\
	'"adminPass": "{password}", "adminUser": "{user}", "serverAddress":'\
	'"{server_address}"'

RESERVATIONDETAILS_TEMPLATE = '"environmentName":"{environment_name}",'\
    '"environmentPath":"{environment_path}",'\
	'"domain":"{domain}", "description":'\
	'"{description}","parameters":{parameters_template},"ownerUser":'\
	'"{owner_user}","ownerPass":"{owner_pass}","id":"{id}"'

RESOURCEDETAILS_TEMPLATE = '"name":"{name}","address":"{address}","model":"{model}",' \
                           '"family":"{family}","description":"{description}",'\
                           '"fullname":"{fullname}","attributes":{attributes}'

RESOURCE_ATTRIBUTES_TEMPLATE ='"{name}":"{value}"'

PARAMETERS_TEMPLATE = '"resourceRequirements":'\
	'[{requirement_template}],"globalInputs":[{global_template}],'\
	'"resourceAdditionalInfo":[{additional_info_template}]'

GLOBAL_PARAMETER_TEMPLATE= '"parameterName": "{name}", "value": "{value}"'

RESOURCE_REQUIREMENT_TEMPLATE = '"resourceName": "{resource_name}", "value": "{value}", "parameterName": "{name}"'

ADDITIONAL_INFO_TEMPLATE = '"resourceName": "{resource_name}", "value": "{value}", "parameterName": "{name}", "possibleValues" : "{possibleValues}"'


def is_dev_mode():
    return os.environ.get('qualiConnectivityContext') == None or \
           os.environ.get('DEVBOOTSTRAP') != None


def attach_to_cloudshell_as(user, password, domain, reservation_id,
                            server_address='localhost',
                            cloudshell_api_port='8028',
                            command_parameters={}, resource_name=None, service_name=None):
    """
    This helper is intended to make it easier to test scripts. When a script
    gets executed by CloudShell, the Execution Server sets up several variables
    as a context for the execution.
    This function simulates the same conditions so the script can be tested
    offline.
    :param str user: The user the driver should authenticate as
    :param str passwrd: Password for the specified user
    :param str reservation_id: The reservation the driver should attach to
    :param str server_address: The address of the CloudShell server
    (default to localhost)
    :param str cloudshell_api_port: The API port to use (default 8028)
    :param dict[str,str] command_parameters: user parameters passed to this command
    :param str resource_name: For resource commands only specify the name of the resource
    """
    _bootstrap_data(user, password, domain, reservation_id,
                    server_address, cloudshell_api_port,
                    command_parameters, resource_name, service_name)


def attach_to_cloudshell(filename='quali_config.json'):
    """
    This helper is intended to make it easier to test scripts. When a script
    gets executed by CloudShell, the Execution Server sets up several variables
    as a context for the execution.
    This function simulates the same conditions so the script can be tested
    offline.
    Using this overload, all information is retrieved from a JSON config file
    which should be of the following format:
    {
        "user" : "admin",
        "password" : "admin",
        "domain" : "Global",
        "server_address" : "localhost",
        "cloudshell_api_port" : "8028"
    }
    :param str filename: The configuration filename path
    """
    if is_dev_mode():
        try:
            with open("quali_config.json", "r") as myfile:
                data = myfile.read()
            info = json.loads(data)
            user = info['user']
            password = info['password']
            domain = info['domain']
            server_address = info['server_address']
            cloudshell_api_port = info['cloudshell_api_port']
            reservation_id = info['reservation_id']
            command_parameters = info['command_parameters']
            os.environ['DEVBOOTSTRAP'] = 'True'
            resource_name = info.get('resource_name')
            service_name = info.get('service_name')
            _bootstrap_data(user, password, domain, reservation_id,
                            server_address, cloudshell_api_port,
                            command_parameters, resource_name,service_name)

        except IOError:
            print 'No config file found at:', filename


def _bootstrap_data(user, password, domain, reservation_id,
                    server_address='localhost', cloudshell_api_port='8028',
                    command_parameters={}, resource_name=None, service_name=None):
    """
    This helper is intended to make it easier to test scripts. When a script
    gets executed by CloudShell, the Execution Server sets up several variables
    as a context for the execution.
    This function simulates the same conditions so the script can be tested
    offline.
    :param str user: The user the driver should authenticate as
    :param str passwrd: Password for the specified user
    :param str reservation_id: The reservation the driver should attach to
    :param str server_address: The address of the CloudShell server
    (default to localhost)
    :param str cloudshell_api_port: The API port to use (default 8028)
    :param dict[str,str] command_parameters: user parameters passed to this command
    :param str resource_name: For resource commands only specify the name of the resource
    """
    if is_dev_mode():
        # We assume that if the env. variable doesn't exist we need to bootstrap
        quali_connectivity = CONNECTIVITY_DETAILS_TEMPLATE.\
            format(cloudshell_api_port=cloudshell_api_port,
                   server_address=server_address, password=password,
                   user=user)

        # Creat an initial template for reservation details just to get more info
        reservation_details = RESERVATIONDETAILS_TEMPLATE.\
            format(id=reservation_id, domain='Global',
                   description='', environment_name='',
                   environment_path='', parameters_template='[]',
                   owner_user=user, owner_pass=password)

        os.environ['qualiConnectivityContext'] = '{' + quali_connectivity + '}'
        os.environ['reservationContext'] = '{' + reservation_details + '}'

        parameters_details = _extract_parameters_JSON(reservation_id)

        reservation_desc = helpers.get_api_session() \
                                        .GetReservationDetails(reservation_id) \
                                        .ReservationDescription

        reservation_details = RESERVATIONDETAILS_TEMPLATE.\
            format(id=reservation_id, domain=reservation_desc.DomainName,
                   description=reservation_desc.Description,
                   parameters_template='{' + parameters_details + '}',
                   environmment_path=reservation_desc.Name,
                   environment_name=reservation_desc.Name,
                   owner_user=user, owner_pass=password)

        # Update the reservation details again with the full info
        os.environ['reservationContext'] = '{' + reservation_details + '}'
        for parameter in command_parameters:
            os.environ[parameter.upper()] = command_parameters[parameter]
        if resource_name is not None:
            os.environ['resourceContext'] = \
                _get_resource_context(resource_name)
        if service_name is not None:
            os.environ['resourceContext'] = \
                _get_service_context(reservation_desc,service_name)


def _get_resource_context(resource_name):
    r = helpers.get_api_session().GetResourceDetails(resource_name)
    attributes = []
    for attribute in r.ResourceAttributes:
        attribute_json = RESOURCE_ATTRIBUTES_TEMPLATE.format(
            name=attribute.Name,
            value=attribute.Value)
        attributes.append(attribute_json)
    resource_details = RESOURCEDETAILS_TEMPLATE.\
        format(name=r.Name, address=r.Address,
               model=r.ResourceModelName, family=r.ResourceFamilyName,
               description=r.Description, fullname=r.Name,
               attributes='{'+string.join(attributes, sep=',') + '}')
    return '{' + resource_details + '}'


def _get_first_matching_service(services, name):
    if services:
        for service in services:
            if service.Alias == name:
                return service
    return None


def _get_service_context(reservation_description, service_name):
    """:param ReservationDescriptionInfo reservation_description: """
    """:param str service_name: """

    service = _get_first_matching_service(reservation_description.Services,service_name)
    attributes = []
    for attribute in service.Attributes:
        attribute_json = RESOURCE_ATTRIBUTES_TEMPLATE.format(
            name=attribute.Name,
            value=attribute.Value)
        attributes.append(attribute_json)
    resource_details = RESOURCEDETAILS_TEMPLATE.\
        format(name=service.Alias, address="",
               model=service.ServiceName, family="",
               description="", fullname=service.Alias,
               attributes='{'+string.join(attributes, sep=',') + '}')
    return '{' + resource_details + '}'


def _set_env_variable(variable_name, value):
    os.environ[variable_name]


def _extract_parameters_JSON(reservation_id):
    inputs_desc = helpers.get_api_session() \
        .GetReservationInputs(reservation_id)
    global_inputs_JSON = _extract_global_inputs_JSON(inputs_desc)
    required_inputs_JSON = _extract_required_inputs_JSON(inputs_desc)
    additional_inputs_JSON = _extract_addition_inputs_JSON(inputs_desc)
    return PARAMETERS_TEMPLATE.format(
        requirement_template=required_inputs_JSON,
        additional_info_template=additional_inputs_JSON,
        global_template=global_inputs_JSON)


def _extract_global_inputs_JSON(inputs_desc):
    global_inputs = []
    for global_input in inputs_desc.GlobalInputs:
        global_input_JSON = GLOBAL_PARAMETER_TEMPLATE.format(
            name=global_input.ParamName,
            value=global_input.Value)
        global_inputs.append('{' + global_input_JSON + '}')
    return string.join(global_inputs, ',')


def _extract_required_inputs_JSON(inputs_desc):
    required_inputs = []
    for required_input in inputs_desc.RequiredInputs:
        required_input_JSON = RESOURCE_REQUIREMENT_TEMPLATE.format(
            name=required_input.ParamName,
            value=required_input.Value,
            resource_name=required_input.ResourceName)
        required_inputs.append('{' + required_input_JSON + '}')
    return string.join(required_inputs, ',')


def _extract_addition_inputs_JSON(inputs_desc):
    additional_inputs = []
    for additional_input in inputs_desc.AdditionalInfoInputs:
        additional_input_JSON = ADDITIONAL_INFO_TEMPLATE.format(
            name=additional_input.ParamName,
            value=additional_input.Value,
            resource_name=additional_input.ResourceName,
            possibleValues=additional_input.PossibleValues)
        additional_inputs.append('{' + additional_input_JSON + '}')
    return string.join(additional_inputs, ',')
