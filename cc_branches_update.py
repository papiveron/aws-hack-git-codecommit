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
    """Receive events from codecommit branches update, process the received event,
    archive the repository content to s3 and start codecommit related pipeline execution
    """
    
    try:
        repo_name = event['Records'][0]['eventSourceARN'].split(':')[-1]
        reference = event['Records'][0]['codecommit']['references'][0]
        commit_id = reference['commit']
        ref = os.path.split(reference["ref"])
        root = os.path.basename(ref[0])
        if root == "heads" and ref[1] and ref[1] != "master":
            data = json.loads(event['Records'][0]['customData'])
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
    except Exception as e:
        logger.exception("An error occured when processing codecommit trigger event : %s" % str(e), exc_info=1)
    
if __name__ == "__main__":
    lambda_handler(None, None)
