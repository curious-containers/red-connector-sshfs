import os
from subprocess import call

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


def _create_password_command(password, username, host, port, local_path, remote_path):
    """
    Creates a command as string list, that can be executed to mount the <remote_path> to <local_path>, using the
    provided information.
    echo '<password>' | sshfs <username>@<host>:<remote_path> <local_path> -o password_stdin -p <port>
    """
    remote_connection = '{username}@{host}:{remote_path}'.format(username=username, host=host, remote_path=remote_path)
    return [
        'echo', '\'{}\''.format(password), '|',
        'sshfs', remote_connection, local_path,
        '-o', 'password_stdin',
        '-p', str(port)
    ]


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
        call(' '.join(command), shell=True)

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

    @staticmethod
    def receive_directory_cleanup(internal):
        """
        Unmounts and removes the directory given in internal.

        :param internal: A dictionary containing information about where to unmount a directory.
        """
        path = internal['path']
        if call(['fusermount3', '-u', path]) == 0:
            os.rmdir(path)
        else:
            raise Exception('Cleanup failed. Could not unmount "{}" with "fusermount3 -u"'.format(path))
