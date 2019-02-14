import zipfile
import tempfile
from io import BytesIO as StringIO

class AWSCodeCommit(object):
    """Helper AWS CodeCommit class, wrapping the Boto codecommit client and letting manage your aws codecommit 
    repository tree and references in AWS, without the need of python git python library and git credentials.
    The class has a  'content' property allowing you to get the whole codecommit repository content in memory and place it anywhere you need. 
    """

    def __init__(self, client, name, logger, compression=zipfile.ZIP_DEFLATED, debug=0):
        """Instantiate a CodeCommit object and initializes attributes

        Args:
            logger (obj): an instance of Logger library class which providing custom lgging functions
            client (obj): an instance of Boto3 codecommit client to use for API requests
            name (str): the name of the codecommit repository to work on
            compression (num const): the ZIP compression method to use when writing the repository content archive
            debug (num const) : the level of debug output to use in the archiving process
        """
        
        self.logger = logger
        self.client = client
        self.name = name
        self.__files = []
        self.__in_memory_content = StringIO()
        self.__in_memory_zip = zipfile.ZipFile(self.__in_memory_content, "w", compression, False)
        self.__in_memory_zip.debug = debug

    def __get_files(self, specifier, folder_path):
        """Private method that recursively retrieves and returne all codecommit repository files' 
        absolute paths

        Args:
            specifier (str): the repository branch or commit id from which to retrieve files
            folder (str): the root folder path from whre files are retrived
        """

        response = self.client.get_folder(
            repositoryName=self.name,
            commitSpecifier=specifier,
            folderPath=folder_path
        )
        for objfile in response.get("files", []): 
            self.__files.append(objfile["absolutePath"])
        for subfolder in response.get("subFolders", []):
            self.__get_files(specifier, subfolder["absolutePath"])

    def archive(self, specifier="master", members=None):
        """Build an in-memory zip file reprenting the whole repository tree content, so that you can you can use 
        the 'flush_content' method to write it on the disk method or either get the it directly through the 'content' portery and manipulate it as you need.
        this method acts like the 'git archive' command, but created the archive in memory.
        If given, the 'members' parameter should be a dictionary, where each key is a file_name/path to be added and value is the file
        content which may be either a str or a byte.

        Args:
            specifier (str): the repository branch or commit id from which to retrieve the reposirory content, default to master branch.
            members (dict): Additional file objects to be added to archive. This parameter can be useful if you want for example to add more files
            to the repository content before archive it.
        """

        self.logger.debug("Emptiying files list, and retriving files from the repository")
        del self.__files[:]
        self.__get_files(specifier, "/")
        self.logger.debug({"FilesPathList": self.__files})
        for file_path in self.__files:
            response = self.client.get_file(
                repositoryName=self.name,
                commitSpecifier=specifier,
                filePath=file_path
            )
            self.__in_memory_zip.writestr(response["filePath"], response["fileContent"])
        if members:
            self.logger.debug({"Adding additional members to archive": [member for member in members]})
            for member in members:
                self.__in_memory_zip.writestr(member, members[member])
        self.logger.info("Mark the files as having been created on Windows so that Unix permissions are not inferred as 0000")
        for zfile in self.__in_memory_zip.filelist:
            zfile.create_system = 0
        self.__in_memory_zip.close()
    
    @property
    def content(self):
        return self.__in_memory_content.getvalue()

    def flush_content(self, file_name=None):
        """Writes the repository in-memory zip content to a file on the disk.

        Args:
            file_name (str): the of the zip file to create/write on the the disk

        Returns:
            the path of the writen archive file
        """

        if not file_name:
            new_file, file_name = tempfile.mkstemp()
        with open(file_name, 'wb') as fd:
            fd.write(self.content)
        return file_name
