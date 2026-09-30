# hiTech Automation AI — container image
#
#   Core (no AI):   docker compose -f docker/docker-compose.yml up -d --build
#   With AI:        WITH_AI=1 docker compose -f docker/docker-compose.yml up -d --build
#
FROM python:3.11-slim

# git        : the YANG "Git import" does sparse clones
# ssh client : netmiko / SCP import
# curl       : the RESTCONF "curl" run mode
# openssl    : v1.49.0 Certificates (CA, CSR, signing, verify, PKCS#12)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git openssh-client iputils-ping curl openssl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better layer caching.
COPY build/requirements.txt build/requirements-ai.txt /app/

# WITH_AI=1 also installs the optional AI stack (chromadb, anthropic).
# Without it the app still starts and every network-automation feature works;
# only AI Chat / agent tools / RAG are disabled.
ARG WITH_AI=0
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && if [ "$WITH_AI" = "1" ]; then \
        echo ">>> installing optional AI stack (WITH_AI=1)"; \
        pip install --no-cache-dir -r requirements-ai.txt; \
    else \
        echo ">>> core install (no AI). Rebuild with WITH_AI=1 to enable AI Chat."; \
    fi

# v1.50.0 Ansible, installed in the image: a container has no /usr/bin/python3.x
# for the page's "Install / repair", and lab workstations have no internet.
# Own venv (/opt/vansible, never the app's packages); collections in
# /root/.ansible/collections, which the app searches after its own folder.
# WITH_ANSIBLE=0 leaves it out (the Ansible page then says it is not installed).
ARG WITH_ANSIBLE=1
COPY build/requirements-ansible.txt build/ansible-collections.yml /tmp/ansible/
RUN if [ "$WITH_ANSIBLE" = "1" ]; then \
        python -m venv /opt/vansible \
     && /opt/vansible/bin/pip install --no-cache-dir -r /tmp/ansible/requirements-ansible.txt \
     && /opt/vansible/bin/ansible-galaxy collection install \
            -r /tmp/ansible/ansible-collections.yml -p /root/.ansible/collections; \
    fi && rm -rf /tmp/ansible
ENV HITECH_VANSIBLE=/opt/vansible

COPY build/ /app/

# State (devices.yaml, YANG repos, collections, audit log) is bind-mounted from
# the host in docker-compose.yml, so it is shared with a systemd install and
# survives image rebuilds.
ENV HOME=/root \
    OLLAMA_URL=http://192.168.89.102:11434

EXPOSE 7071
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7071"]
