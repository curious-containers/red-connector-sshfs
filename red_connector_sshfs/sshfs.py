import os
import subprocess
from shutil import which

import jsonschema

sshfs_access_schema = {
    'type': 'object',
    'properties': {
        'host': {'type': 'string'},
        'port': {'type': 'integer'},
        'username': {'type': 'string'},
        'password': {'type': 'string'},
        'dirName': {'type': 'string'},
    },
    'additionalProperties': False,
    'required': ['host', 'username', 'dirName']
}


DEFAULT_PORT = 22
FUSERMOUNT_EXECUTABLES = ['fusermount3', 'fusermount']
SSHFS_EXECUTABLES = ['sshfs']


def _create_password_command(password, username, host, port, local_path, remote_path):
    """
    Creates a command as string list, that can be executed to mount the <remote_path> to <local_path>, using the
    provided information.
    echo '<password>' | sshfs <username>@<host>:<remote_path> <local_path> -o password_stdin -p <port>
    """
    sshfs_executable, _ = _find_executables()
    remote_connection = '{username}@{host}:{remote_path}'.format(username=username, host=host, remote_path=remote_path)
    return [
        'echo', '\'{}\''.format(password), '|',
        sshfs_executable, remote_connection, local_path,
        '-o', 'password_stdin',
        '-p', str(port)
    ]


def _find_executables():
    sshfs_executable = None
    for executable in SSHFS_EXECUTABLES:
        if which(executable):
            sshfs_executable = executable
            break
    if not sshfs_executable:
        raise Exception('One of the following executables must be present in PATH: {}'.format(
            SSHFS_EXECUTABLES
        ))

    fusermount_executable = None
    for executable in FUSERMOUNT_EXECUTABLES:
        if which(executable):
            fusermount_executable = executable
            break
    if not fusermount_executable:
        raise Exception('One of the following executables must be present in PATH: {}'.format(
            FUSERMOUNT_EXECUTABLES
        ))

    return sshfs_executable, fusermount_executable


class Sshfs:
    @staticmethod
    def receive_directory(access, internal, listing):
        """
        Mounts a directory.

        :param access: A dictionary containing access information. Has the following keys
                       - 'host': The host to connect to
                       - 'username': A username that is used to perform authentication
                       - 'password': A password that is used to perform authentication
                       - 'dirName': The name of the directory to fetch
                       - 'port': The port to connect (optional)
        :param internal: A dictionary containing information about where to mount the directory content
        :param listing: Listing of subfiles and subdirectories which are contained by the directory given in access.
                        Is ignored by this connector.
        :raise Exception: If neither privateKey nor password is given in the access dictionary
        """
        host = access['host']
        username = access['username']
        remote_path = access['dirName']
        local_path = internal['path']

        port = access.get('port', DEFAULT_PORT)
        password = access.get('password')
        private_key = access.get('privateKey')

        if password is not None:
            command = _create_password_command(password, username, host, port, local_path, remote_path)
        elif private_key is not None:
            raise NotImplementedError()
        else:
            raise Exception('At least "password" or "privateKey" must be present.')

        os.mkdir(local_path)

        process_result = subprocess.run(' '.join(command), stderr=subprocess.PIPE, shell=True)
        if process_result.returncode != 0:
            raise Exception('Could not mount "{}" from "{}@{}:{}" using password and "sshfs":\n{}'
                            .format(local_path, username, host, remote_path, process_result.stderr.decode('utf-8')))

    @staticmethod
    def receive_directory_validate(access):
        try:
            jsonschema.validate(access, sshfs_access_schema)
        except jsonschema.ValidationError as e:
            if e.context:
                raise Exception(e.context)
            else:
                raise Exception(str(e))
        if ('password' not in access) and ('privateKey' not in access):
            raise Exception('At least "password" or "privateKey" must be present.')

        _ = _find_executables()

    @staticmethod
    def receive_directory_cleanup(internal):
        """
        Unmounts and removes the directory given in internal.

        :param internal: A dictionary containing information about where to unmount a directory.
        """
        path = internal['path']

        _, fusermount_executable = _find_executables()

        process_result = subprocess.run([fusermount_executable, '-u', path], stderr=subprocess.PIPE)
        if process_result.returncode == 0:
            os.rmdir(path)
        else:
            raise Exception('Cleanup failed. Could not unmount "{}" with "{} -u":\n{}'.format(
                fusermount_executable, path, process_result.stderr
            ))
