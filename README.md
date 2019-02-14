# A Git-like library for AWS CodeCommit

**CodeCommit** aims to provide a python library class to you to interact with your **AWS CodeCommit Git Repository** programmatically without the need of **Git** and **Git Credentials**

## The context
This library was born in a context of building an **Infrastructure Automation & CI/CD** solution in a full AWS environment, using exclusively **AWS Developper and Management Tools/Services**
The solution was then architected  arround **AWS CodePipeline**, using **AWS CodeCommit** for sourcing and **AWS ServiceCatalog** for products provisioning from **AWS CloudFormation**, with the most flexibility and cost effectiveness.
The detail of the detail of this solution architecture is out of the scope of this README, you can have a brief overview of the concept in this [blog post](https://aws.amazon.com/blogs/devops/aws-service-catalog-sync-code/)
But for short, the solution consists in managing business units development teams, leveraging their software product shifting from Development to Production environment through projects. Thus for each team/project there are :
- One **pipeline** called the **ops pipeline**, taking all changes from the master branch  of the project repository (in **AWS CodeCommit**), releasing those changes in a **staging** environment (**Continuous Delivery**) for validation tests, promoting and deploying the release in **production** environment (**Continuous Deployment**)
- One **pipeline** called the **dev pipeline**, proncessing changes from any **feature branch** of the project repository and provision products in a development **AWS ServiceCatalog** portfolio. This allows to test all features branches autonomously and independently before merge them for release (**Continuous Integration**). When feature branches are integrated and merged to the **master** branch the **Continuous Delivery** takes place through the **ops pipeline**.
Once aigain the whole solution architecture documentation is out of the scope of this README and will be available later elsewhere. 

##The problematic
One of the limits I had to face with was the **AWS CodePipeline** doesn't support processesing changes from multiple branches within a given CodeCommit repository, and one feature of the solution was to provide a full automated and agnostic development environment to the **Development** teams.
Unfortunatelwy, by the time of this documentation **AWS CodePipeline** only supports being connected to a single CodeCommit repository branch. To achieve the need I designed the solution to manage **AWS CodeCommit** feature branches creation and deletion dynamically and have feature branches changes invoking an intermediate Lambda function that uploads the code to S3, and then invokes the pipeline. 
Here's an outline of this approach in two phases : branches lifecycle and branches update
- Branches lifecycle
  - Developpers create feature branches for their developments upstream and dowstream
  - Each branch creation trigger a "lifecyle" **Lambda** function wich creates a repository trigger for all futur changes on this specific feature branch
  -  When the feature branch is deleted (for example after a merge), the above repository trigger is deleted
- Branches updates
  - Changes are pushed to repository feature branch
  - According to the trigger configuration of that feature branch, the "updates" **Lambda** function is invoked.
  - The "updates" **Lambda** function uses the data from the [event](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/EventTypes.html#codecommit_event_type) to checkout a copy of the code and upload it to an S3 bucket on a fixed location, using an implementation of [git-archive](https://git-scm.com/docs/git-archive)
  - The "updates" Lambda function invokes the [StartPipelineExecution](https://docs.aws.amazon.com/codepipeline/latest/APIReference/API_StartPipelineExecution.html) API call  to start the **dev pipeline**, which is pre-configured to source from the S3 (on the fixed location mentioned above) instead of **AWS CodeCommit**.

We won't get here into technical details of "lifecycle" and "updates" **Lambda** functions code and their inputs data, as these functions are part of the whole **Infrastructure Automation & CI/CD** solution architecture, which is not the main subject of this README. They are mentionned here just to give a complete of the context in which the **codecommit** library mainly concerned by this documentation was writen.

Nevertheless an another blocking point comes here for checking out and archiving the code from the feature branch :
- As mentioned in the context section, we are mananing several developper teams projects dynamically, in different **AWS accounts**
- For each project, **dev** and **ops** pipelines as well as others AWS required resources such as IAM roles and policies are set up automatically 
- **Git** needs credentials to authenticate to **AWS CodeCommit** repository
- It's not possible to use IAM role or either **credential helper** to interact with **AWS CodeCommit** programmatically. The credential helper is only available to be used with the AWS CLI.
- To obtain **AWS CodeCommit** credentials for programmatic authentication using **Git**, you should connect to **AWS console**, select an IAM user, [generate git HTTPS credentials]( https://docs.aws.amazon.com/codecommit/latest/userguide/setting-up-gc.html) and store them in a place where the **Lambda** function can retrieve them
- As all resources setup is automatic, the above credentials generation is not envisageable, for the simple reason that we cannot connect to **AWS console** and manually git generate credentials in the middle of each project pipelines setup.
- This is where the **CodeCommit library** came out to be used by above "lifecycle" and "update" **Lambda** function for **Git** related purposes.

##The solution to Git problem
To address the programtic difficulty/limit described just above, I decided to code a library that implements the [git-archive](https://git-scm.com/docs/git-archive) feature to be used by my **AWS CodeCommit** repository triggers funcitons. The is in the `codecommit module` of this repository.
The library exposes an **archive** method among others, but can be extended to offers more **Git** related useful puroses.
Using the **CodeCommit class** provided here, there is no more need to use a **Git** library like [GitPython](https://gitpython.readthedocs.io/en/stable/), and no headache with [AWS git HTTPS credentials]( https://docs.aws.amazon.com/codecommit/latest/userguide/setting-up-gc.html)
After you have called the `archive` method, your repository content is copied in an `in-memory` zip file, and you can write it to your local disk by calling the `flush_content` method, or alternatively access it using the `content` property and write it to any place you need.

```
    ....
    client = boto3.client('codecommit')
    codecommit = AWSCodeCommit(aws_client, my_repo, logger)
    codecommit.archive('staging')
    print(codecommit.flus_content())
    ....
```
