"""Prepare a mounted disk, then run the service as the fixed application UID."""
import os
from pathlib import Path


def main():
    root = Path(os.environ.get('OFFSETX_PERSISTENT_MOUNT', '/var/lib/offcrm')).resolve()
    if root == Path('/') or root in (Path('/app'), Path('/etc'), Path('/usr')):
        raise SystemExit('Use a dedicated persistent disk directory for off_CRM')
    if os.getuid() == 0:
        # Ownership applies only to the mount root. Existing customer file
        # permissions are preserved; the application creates children at 0700.
        root.mkdir(parents=True, exist_ok=True)
        os.chown(root, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    os.chmod(root, 0o700)
    os.umask(0o077)
    import sys
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
