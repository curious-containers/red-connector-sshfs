import os
import subprocess
import tempfile
from shutil import which

import jsonschema

sshfs_access_schema = {
    'type': 'object',
    'properties': {
        'host': {'type': 'string'},
        'port': {'type': 'integer'},
        'auth': {
            'oneOf': [{
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                },
                'additionalProperties': False,
                'required': ['username', 'password']
            }, {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'privateKey': {'type': 'string'},
                },
                'additionalProperties': False,
                'required': ['username', 'privateKey']
            }]
        },
        'dirPath': {'type': 'string'},
    },
    'additionalProperties': False,
    'required': ['host', 'auth', 'dirPath']
}


DEFAULT_PORT = 22
FUSERMOUNT_EXECUTABLES = ['fusermount3', 'fusermount']
SSHFS_EXECUTABLES = ['sshfs']


def _create_password_command(username, host, port, local_path, remote_path, configfile_path):
    """
    Creates a command as string list, that can be executed to mount the <remote_path> to <local_path>, using the
    provided information.
    echo '<password>' | sshfs <username>@<host>:<remote_path> <local_path> -o password_stdin -p <port>
    """
    sshfs_executable, _ = _find_executables()
    remote_connection = '{username}@{host}:{remote_path}'.format(username=username, host=host, remote_path=remote_path)
    return [
        sshfs_executable, remote_connection, local_path,
        '-o', 'password_stdin',
        '-o', 'ro',
        '-F', configfile_path,
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
        port = access.get('port', DEFAULT_PORT)
        remote_path = access['dirPath']
        auth = access['auth']
        username = auth['username']

        local_path = internal['path']

        if 'password' in auth:
            password = auth['password']
            with tempfile.NamedTemporaryFile('w') as temp_configfile:
                temp_configfile.write('StrictHostKeyChecking=no')
                temp_configfile.flush()
                command = _create_password_command(username, host, port, local_path, remote_path, temp_configfile.name)
                command = ' '.join(command)

                os.mkdir(local_path)

                process_result = subprocess.run(
                    command, input=password.encode('utf-8'), stderr=subprocess.PIPE, shell=True
                )

                if process_result.returncode != 0:
                    raise Exception(
                        'Could not mount "{}" from "{}@{}:{}" using password and "sshfs":\n{}'.format(
                            local_path, username, host, remote_path, process_result.stderr.decode('utf-8'))
                    )
        else:
            raise NotImplementedError()

    @staticmethod
    def receive_directory_validate(access):
        try:
            jsonschema.validate(access, sshfs_access_schema)
        except jsonschema.ValidationError as e:
            if e.context:
                raise Exception(e.context)
            else:
                raise Exception(str(e))

        if 'privateKey' in access['auth']:
            raise NotImplementedError('Authentication via privateKey is not yet implemented')

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
