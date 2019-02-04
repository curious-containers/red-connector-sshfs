from cc_connector_cli.connector_cli import run_connector
from red_connector_sshfs.sshfs import Sshfs
from red_connector_sshfs.version import VERSION


def main():
    run_connector(Sshfs, version=VERSION)


if __name__ == '__main__':
    main()
