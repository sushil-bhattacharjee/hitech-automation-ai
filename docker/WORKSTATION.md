# hiTech Automation AI on the lab workstations

Each workstation runs this from `/opt/hitech-netauto`, a git checkout of
ctrlvm's GitLab (`root/hitech-netauto`, private), started with
`docker-compose.workstation.yml`.

**To update every new session:** push to the `ctrlvm` remote. At boot,
`hitech-update.service` pulls and restarts the container — no image rebuild,
no internet.

**Only a change to `requirements.txt` needs a new workstation image**, since
the dependencies are baked into the container image and the workstations
have no internet to install new ones.

The code directory is root-only (`chmod 700`), and the pull token is a
read-only project token stored inside it, so students cannot see either.
