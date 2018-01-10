from chalice import Chalice, Response
import boto3
import json, ast
import logging
from botocore.exceptions import ClientError
from chalice import BadRequestError, NotFoundError, ChaliceViewError, ForbiddenError
from chalice import CognitoUserPoolAuthorizer
import urllib2
import hashlib
from chalice import CORSConfig
cors_config = CORSConfig(
    allow_origin='*',
    allow_headers=['Content-Type','X-Amz-Date','Authorization','X-Api-Key','X-Amz-Security-Token','Access-Control-Allow-Origin'],
    max_age=600,
    expose_headers=['Content-Type','X-Amz-Date','Authorization','X-Api-Key','X-Amz-Security-Token','Access-Control-Allow-Origin'],
    allow_credentials=True
)


TABLENAME = 'prod-UserStacksTable'
TABLENAME_DATASET = 'prod-AvailableDataset'
APPSTREAM_S3_BUCKET_NAME = 'appstream2-36fb080bb8-us-east-1-911061262852'
APPSTREAM_DATASET_FOLDER_NAME = 'datasets/'
APPSTREAM_ALGORITHM_FOLDER_NAME = 'algorithm/'
APPSTREAM_DATASET_PATH = 'user/custom/'
DATA_DICT_S3_BUCKET_NAME = 'prod-dot-sdc-curated-911061262852-us-east-1'
DATA_DICT_PATH = 'data-dictionaries/'
RECEIVER = 'support@securedatacommons.com'
PROVIDER_ARNS = 'arn:aws:cognito-idp:us-east-1:911061262852:userpool/us-east-1_uAgXIUy4Q'

app = Chalice(app_name='webportal')
logger = logging.getLogger()
dynamodb_client = boto3.resource('dynamodb')
appstream_client = boto3.client('appstream')

def get_user_details(id_token):
    try:
        apigateway = boto3.client('apigateway')    
        response = apigateway.test_invoke_authorizer(
        restApiId='u2zksemc1h',
        authorizerId='ne1w0w',
        headers={
            'Authorization': id_token
        })
        roles_response=response['claims']['family_name']
        email=response['claims']['email']
        full_username=response['claims']['cognito:username'].split('\\')[1]
        roles_list_formatted = ast.literal_eval(json.dumps(roles_response))
        role_list= roles_list_formatted.split(",")
        
        roles=[]
        for r in role_list:
            if ":role/" in r:
                roles.append(r.split(":role/")[1])

        
        return { 'role' : roles , 'email': email, 'username': full_username }
    except BaseException as be:
        logging.exception("Error: Failed to get role from token" + str(be) )
        raise ChaliceViewError("Internal error at server side") 

def get_datasets():  

    table = dynamodb_client.Table(TABLENAME_DATASET)

    response = table.scan(TableName=TABLENAME_DATASET)

    return { 'datasets' : response }


authorizer = CognitoUserPoolAuthorizer(
    'test_cognito', provider_arns=[PROVIDER_ARNS])

@app.route('/user', authorizer=authorizer, cors=cors_config)
def get_user_info():

    user_info={} 
    roles=[]
    try:
        id_token = app.current_request.headers['authorization']
        info_dict=get_user_details(id_token)
        user_info['role']=info_dict['role']
        user_info['email']=info_dict['email']
        user_info['username']=info_dict['username']
        user_info['datasets']=get_datasets()['datasets']['Items']
        
      
    except BaseException as be:
        logging.exception("Error: Failed to get role from token" + str(be) )
        raise ChaliceViewError("Internal error at server side") 
    table = dynamodb_client.Table(TABLENAME)

    # stack_names=set()
        
    # Extract the stack names associated with the roles passed        

    # Get the item with role name
    try:
        response_table = table.get_item(Key={'username': user_info['username'] })
    except BaseException as be:
        logging.exception("Error: Could not perform get_item() on requested table.Verify requested table exist." + str(be) )
        raise ChaliceViewError("Internal error at server side")                

    # Convert unicode to ascii
    try:                
        user_info['stacks']=ast.literal_eval(json.dumps(response_table['Item']['stacks']))
    except KeyError as ke:
        logging.exception("Error: Could not fetch the item for user: " + user_info['username'])
        raise NotFoundError("Unknown role '%s'" % (user_info['userinfo']))
    except BaseException as be:
        logging.exception("Error: Could not perform get_item() on requested table.Verify requested table exist." + str(be) )
        raise ChaliceViewError("Internal error at server side")                           

    return Response(body=user_info,
                    status_code=200,
                    headers={'Content-Type': 'text/plain'})              


@app.route('/streamingurl', methods=['POST'], authorizer=authorizer, cors=cors_config)
def get_streaming_url():          
    params = app.current_request.query_params
    if not params or "stack_name" not in params or "fleet_name" not in params or "username" not in params :
        logger.error("The query parameters 'stack_name' or 'fleet_name' or 'username' is missing")
        raise BadRequestError("The query parameters 'stack_name' or 'fleet_name' or 'username' is missing")


    try:
        hash_object_user_id = hashlib.sha256(params['username'])
        hex_dig_user_id = hash_object_user_id.hexdigest()
    except BaseException as be:
        logger.exception("Failed to create sha256 hash for userid: %s" % params['username'])
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")

    try:
        client_s3 = boto3.client('s3')
        response = client_s3.put_object(
                Bucket=APPSTREAM_S3_BUCKET_NAME,
                Body='',
                Key=APPSTREAM_DATASET_PATH+hex_dig_user_id+'/'+APPSTREAM_DATASET_FOLDER_NAME
                )
    except ClientError as ce:
        logger.exception("Failed to create datasets folder of user %s" % params['username'])
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")

    try:
        client_s3 = boto3.client('s3')
        response = client_s3.put_object(
                Bucket=APPSTREAM_S3_BUCKET_NAME,
                Body='',
                Key=APPSTREAM_DATASET_PATH+hex_dig_user_id+'/'+APPSTREAM_ALGORITHM_FOLDER_NAME
                )
    except ClientError as ce:
        logger.exception("Failed to create algorithm folder of user %s" % params['username'])
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")        
 
    # Create the appstream url.
    try:
        response = appstream_client.create_streaming_url(FleetName=params['fleet_name'], StackName=params['stack_name'],
                                                         UserId=params['username'])
        #return {'url': response['StreamingURL']}

        return Response(body=response['StreamingURL'],
                status_code=200,
                headers={'Content-Type': 'text/plain'})
    except KeyError as ke:
        logger.exception('received malformed mapping data from dynamodb. %s' % mapping)
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")
    except ClientError as ce:
        logger.exception("Creation of streaming url failed for [user=%s, Fleet=%s, stack=%s]" % (
        user_id, found['fleet_name'], found['stack_name']))
        raise ChaliceViewError("Error creating streaming url")             

@app.route('/send_email', methods=['POST'], authorizer=authorizer, cors=cors_config)
def send_email():
    ses_client = boto3.client('ses')

    params = app.current_request.query_params
    if not params or "sender" not in params or "message" not in params:
        logger.error("The query parameters 'sender' or 'message' is missing")
        raise BadRequestError("The query parameters 'sender' or 'message' is missing")
    #sender = params['sender']
    sender = RECEIVER
    message = params['message']

    try:
        response = ses_client.send_email(
            Destination={
                'BccAddresses': [
                ],
                'CcAddresses': [
                ],
                'ToAddresses': [
                    RECEIVER
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': 'UTF-8',
                        'Data': message,
                    },
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': 'This is the message body in text format.',
                    },
                },
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': 'Request email',
                },
            },
            Source=sender
        )
    except BaseException as ke:
        logging.exception("Failed to send email "+ str(ke) )
        raise NotFoundError("Failed to send email")

@app.route('/user_data', authorizer=authorizer, cors=cors_config)
def get_my_datasets():      
    content = set()
    user_id = ''
    try:
        id_token = app.current_request.headers['authorization']
        info_dict=get_user_details(id_token)
        user_id=info_dict['username']     
    except BaseException as be:
        logging.exception("Error: Failed to get user_id/email from token" + str(be) )
        raise ChaliceViewError("Internal error at server side")

    try:
        hash_object_user_id = hashlib.sha256(user_id)
        hex_dig_user_id = hash_object_user_id.hexdigest()
    except BaseException as be:
        logger.exception("Failed to create sha256 hash for userid: %s" % user_id)
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")

    try:
        client_s3 = boto3.client('s3')
        response = client_s3.list_objects(
            Bucket=APPSTREAM_S3_BUCKET_NAME,
            Prefix=APPSTREAM_DATASET_PATH+hex_dig_user_id+'/'+APPSTREAM_DATASET_FOLDER_NAME
        )
        total_content=response['Contents']

        
        for c in total_content:
            if not c['Key'].endswith(hex_dig_user_id+'/'+APPSTREAM_DATASET_FOLDER_NAME):
                content.add(c['Key'].split(hex_dig_user_id+'/'+APPSTREAM_DATASET_FOLDER_NAME)[1])
    except BaseException as ce:
        logger.exception("Failed to list datasets folder of user %s. %s" % (user_id,ce))
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")

    try:
        client_s3 = boto3.client('s3')
        response = client_s3.list_objects(
            Bucket=APPSTREAM_S3_BUCKET_NAME,
            Prefix=APPSTREAM_DATASET_PATH+hex_dig_user_id+'/'+APPSTREAM_ALGORITHM_FOLDER_NAME
        )
        total_content=response['Contents']

        
        for c in total_content:
            if not c['Key'].endswith(hex_dig_user_id+'/'+APPSTREAM_ALGORITHM_FOLDER_NAME):
                content.add(c['Key'].split(hex_dig_user_id+'/'+APPSTREAM_ALGORITHM_FOLDER_NAME)[1])
    except BaseException as ce:
        logger.exception("Failed to list algorithm folder of user %s. %s" % (user_id,ce))
        raise ChaliceViewError("Internal error occurred! Contact your administrator.")        
                                           
    return Response(body=list(content),
                    status_code=200,
                    headers={'Content-Type': 'text/plain'})

@app.route('/instancestatus', authorizer=authorizer, cors=cors_config)
def get_instance_status():  
    params = app.current_request.query_params
    if not params or "instance_id" not in params:
        logger.error("The query parameters 'instance_id' is missing")
        raise BadRequestError("The query parameters 'instance_id' is missing")

    try:
        client_ec2 = boto3.client('ec2')
        response = client_ec2.describe_instance_status(
            InstanceIds=[
                params['instance_id'],
            ]
        )
    except BaseException as be:
        logging.exception("Error: Failed to get info about instance" + str(be) )
        raise ChaliceViewError("Internal error at server side")    
                                           
    return Response(body={'Status': response},
                    status_code=200,
                    headers={'Content-Type': 'text/plain'})

@app.route('/instance', methods=['POST'], authorizer=authorizer, cors=cors_config)
def perform_instance_action():  
    params = app.current_request.query_params
    if not params or "instance_id" not in params:
        logger.error("The query parameters 'instance_id' is missing")
        raise BadRequestError("The query parameters 'instance_id' is missing")

    if not params or "action" not in params:
        logger.error("The query parameters 'action' is missing")
        raise BadRequestError("The query parameters 'action' is missing")

    if params['action'] == 'run':
        try:
            client_ec2 = boto3.client('ec2')
            response = client_ec2.start_instances(
                InstanceIds=[
                    params['instance_id'],
                ]
            )
        except BaseException as be:
            logging.exception("Error: Failed to start instance" + str(be) )
            raise ChaliceViewError("Internal error at server side")
    else:
        try:
            client_ec2 = boto3.client('ec2')
            response = client_ec2.stop_instances(
                InstanceIds=[
                    params['instance_id'],
                ],
                Force=True
            )
        except BaseException as be:
            logging.exception("Error: Failed to stop instance" + str(be) )
            raise ChaliceViewError("Internal error at server side")    
                                           
    return Response(body={'Status': response},
                    status_code=200,
                    headers={'Content-Type': 'text/plain'})


@app.route('/dataset_dictionary', authorizer=authorizer, cors=cors_config)
def get_dataset_dictionary():  
    params = app.current_request.query_params
    if not params or "datasetcode" not in params or "datasettype" not in params:
        logger.error("The query parameters 'datasetcode' or 'datasettype' is missing")
        raise BadRequestError("The query parameters 'datasetcode' or 'datasettype' is missing")

    try:
        client_s3 = boto3.client('s3')
        response = client_s3.get_object(
        Bucket=DATA_DICT_S3_BUCKET_NAME,
        Key=DATA_DICT_PATH+params['datasetcode']+'-'+params['datasettype']+'-dictionary.README.md'
        )
        data = response['Body'].read()
    except BaseException as be:
        logging.exception("Error: Failed to get data from s3 file" + str(be) )
        raise ChaliceViewError("Internal error at server side")    
                                           
    return Response(body={'data': data },
                    status_code=200,
                    headers={'Content-Type': 'text/plain'})                                                               
    