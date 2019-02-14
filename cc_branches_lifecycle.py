######################################### Import modules and objects ######################################
import os
import json
import boto3
import logging
from datetime import datetime
from boto3.session import Session
from codecommit import AWSCodeCommit

######################################### Set logging parameters ######################################
LOG_FORMAT = "%(levelname)-8s %(asctime)-15s %(message)s"
logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

######################################### Start the Program ######################################
boto_session = Session()
s3_client = boto_session.client('s3')
cc_client = boto_session.client('codecommit')
cp_client = boto_session.client('codepipeline')

def lambda_handler(event, context):
    """Receive events from codecommit branches creation and deletion,
    process the received event and add or remove the relate branch updates trigger
    """
    
    try:
        repo_name = event['Records'][0]['eventSourceARN'].split(':')[-1]
        reference = event['Records'][0]['codecommit']['references'][0]
        commit_id = reference['commit']
        ref = os.path.split(reference["ref"])
        root = os.path.basename(ref[0])
        created = reference.get("created")
        deleted = reference.get("deleted")
        if created and root == "heads" and ref[1] and ref[1] != "master":
            data = json.loads(event['Records'][0]['customData'])
            logger.info('Putting updates trigger for branch %s' % ref[1])
            put_trigger(repo_name, ref[1], data)
            pipeline_name = data["pipeline_name"]
            bucket = data["bucket"]
            logger.info('Getting and archiving codecommit repository content')
            codecommit = AWSCodeCommit(cc_client, repo_name, logger)
            commit_info = cc_client.get_commit(
                repositoryName=repo_name, 
                commitId=commit_id
            )
            commit_info['commit']['branchName'] = ref[1]
            commit_info['commit']['RepositoryName'] = repo_name
            codecommit.archive(commit_id, {"commit_info.json": json.dumps(commit_info, indent=4)})
            s3_client.put_object(Bucket=bucket,
                                 Key="artifacts/%s" % pipeline_name,
                                 Body=codecommit.content)
            logger.info('Starting pipeline execution')
            cp_client.start_pipeline_execution(name=pipeline_name)
        if deleted and root == "heads" and ref[1] and ref[1] != "master":
            logger.info('Poping updates trigger for branch %s' % ref[1])
            pop_trigger(repo_name, ref[1])
    except Exception as e:
        logger.exception("An error occured when processing codecommit trigger event : %s" % str(e), exc_info=1)
    
def put_trigger(repository_name, branch_name, data):
    """Helper function for new codecommit branch updates trigger add
    Make sure triggers are unique based on name before triggers put api call
    """

    response = cc_client.get_repository_triggers(
        repositoryName=repository_name
    )
    triggers = response.get('triggers', [])
    logger.debug({"Got Triggers": triggers})
    pipeline_exec_function = data["pipeline_exec_function"]
    pipeline_name = data["pipeline_name"]
    bucket = data["bucket"]
    triggers.append({
        "name": "trigger-%s-updates" % branch_name,
        "destinationArn": pipeline_exec_function,
        "customData": '{"pipeline_name": "%s", "bucket": "%s"}' % (pipeline_name, bucket),
        "branches": [
            branch_name
        ],
        "events": [
            "updateReference"
        ]}
    )
    triggers = list({trigger['name']:trigger for trigger in triggers}.values())
    logger.debug({"Updating Triggers": triggers})
    cc_client.put_repository_triggers(
        repositoryName=repository_name,
        triggers=triggers
    )

def pop_trigger(repository_name, branch_name):
    """Helper function to remove deleted branches' triggers
    The algorithm used here take into account the triggers list uniquness
    """

    name = "trigger-%s-updates" % branch_name
    response = cc_client.get_repository_triggers(
        repositoryName=repository_name
    )
    triggers = response.get('triggers', [])
    logger.debug({"Got Triggers": triggers})
    for i in range(len(triggers)):
        if triggers[i].get('name') == name:
            del triggers[i]
            break
    logger.debug({"Updating Triggers": triggers})
    cc_client.put_repository_triggers(
        repositoryName=repository_name,
        triggers=triggers
    )

if __name__ == "__main__":
    lambda_handler(None, None)
