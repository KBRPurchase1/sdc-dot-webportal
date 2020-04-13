import boto3
from . import chalice_config_reader

LOG_FORMAT = "$context.identity.sourceIp $context.identity.caller $context.identity.user [$context.requestTime] \"$context.httpMethod $context.resourcePath $context.protocol\" $context.status $context.responseLength $context.requestId"


def normalize_gateway(environment):
    rest_api_config = chalice_config_reader.find_deployed_config('rest_api', environment)
    rest_api_id = rest_api_config['rest_api_id']
    chalice_config = chalice_config_reader.chalice_config()
    stage_name = chalice_config['stages'][environment]['api_gateway_stage']

    gateway_client = api_gateway_client()
    webportal_name = f'{environment}-webportal'
    gateway_client.update_rest_api(restApiId=rest_api_id,
                                   patchOperations=api_gateway_patch_operations(webportal_name))
    gateway_client.update_stage(restApiId=rest_api_id, stageName=stage_name,
                                patchOperations=stage_patch_operations(rest_api_id, stage_name))
    gateway_client.tag_resource(resourceArn=f'arn:aws:apigateway:{get_region()}::/restapis/{rest_api_id}',
                                tags={"Environment": environment, "Project": "SDC-Platform", "Team": "sdc-platform"})


def api_gateway_patch_operations(webportal_name):
    return [{'op': 'replace', 'path': '/name', 'value': webportal_name},
            {'op': 'replace', 'path': '/description', 'value': webportal_name},
            ]


def stage_patch_operations(rest_api_id, stage_name):
    return [{'op': 'replace', 'path': '/accessLogSettings/destinationArn',
             'value': get_log_setting_destination_arn(rest_api_id, stage_name)},
            {'op': 'replace', 'path': '/accessLogSettings/format', 'value': LOG_FORMAT}]


def get_log_setting_destination_arn(rest_api_id, stage_name):
    return f'arn:aws:logs:{get_region()}:{get_account_number()}:log-group:/aws/apigateway/{rest_api_id}/{stage_name}'


def get_region():
    return boto3.Session(profile_name='sdc').region_name


def api_gateway_client():
    session = boto3.Session(profile_name='sdc')
    return session.client('apigateway')


def get_account_number():
    session = boto3.Session(profile_name='sdc')
    return session.client('sts').get_caller_identity().get('Account')