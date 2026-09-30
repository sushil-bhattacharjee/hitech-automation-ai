# Challenge F2: Automated API testing

[GitLab repository]()

## Background information

Making your code modular and testable is a priority. You have recentlly been tasked with developing a Python module for interactive with the Zammad Helpdesk and Ticketing platform API.

First time you access the system use http://localhost:8181/#getting_started/auto_wizard/secret_token 
or
http://192.168.89.98:8181/#getting_started/auto_wizard/secret_token

To access the regular login screen go to http://localhost:8181 or http://192.168.89.98:8181

Login credentials:
| Username | Password |
|----------|----------|
| student@ccie-automation.com | 1234QWer!! |

You task is to complete the python module in zammad_api.py, the token_payload.json file as well as the test script file test_zammad.py

The test must perform the following tests:

- Generate a new API token using username and password
- Create a ticket using the token created above
- Get a ticket using the token created above
- Update a ticket using the token created above
- Delete a ticket using the token created above

API documentation: https://docs.zammad.org/en/latest/api/intro.html

> **Info**
>
> The sections in the code that you must complete are marked inside the file with # TODO: comment blocks referring to the requirement ID.

> **Warning**
>
> Do not modify any other parts of the files.
> With the new Zammand API docker, it has "token" instead of "name" for token response.
> Also for the "group", it requires to use "Users" instead of number 1,2 ..

## Requirements

- A) Implement token based authentication and any needed HTTP headers
- B) Implement basic username/password authentication and any needed HTTP headers
- C) Build the JSON payload to generate a new API token that never expires.
- D) Include the JSON payload with the request.
- E) Use the API to get a specific ticket based on ID.
- F) Use the API to update a specific ticket title based on ID.
- G) Troubleshoot why the test_create_ticket fails and fix the function.
- H) Troubleshoot why the test_delete_ticket fails and fix the function.

## Initial files

### zammad_api.py

```python
import requests


class Zammad:
    def __init__(self, base_url, token=None, username=None, password=None):
        self.base_url = base_url
        self.session = requests.Session()
        #TODO-A: Implement token based authentication and any needed HTTP headers uisng headers or headers.update
        if token:
            #TODO-A
        elif username and password:
            #TODO-B: Implement basic username/password authentication and any needed HTTP headers
        else:
            raise Exception("Token or user access credentials must be provided")

    def list_tickets(self):
        rsp = self.session.get(f"{self.base_url}/api/v1/tickets")
        rsp.raise_for_status()
        return rsp

    def get_ticket(self, ticket_id):
        #TODO-E: Use the API to get a specific ticket based on ID
        rsp.raise_for_status()
        return rsp

    def create_ticket(self, title, customer, article_body):
        payload = {
            "title": title,
            "group": "Users,
            "customer": customer,
            "article": {
                "body": article_body,
            },
        }
        rsp = self.session.post(f"{self.base_url}/api/v1/tickets", json=payload)
        rsp.raise_for_status()
        return rsp

    def update_ticket_title(self, ticket_id, title, article_body):
        #TODO-F: Use the API to update a specific ticket title based on ID
        rsp.raise_for_status()
        return rsp

    def delete_ticket(self, ticket_id):
        rsp = self.session.delete(f"{self.base_url}/api/v1/tickets/{ticket_id}")
        rsp.raise_for_status()
        return rsp

    def create_token(self, filename):
        with open(filename) as f:
            payload = f.read()
        rsp = self.session.post(
            f"{self.base_url}/api/v1/user_access_token",
            #TODO-D: Include the JSON payload with the request
        )
        print(rsp.content)
        rsp.raise_for_status()
        return rsp
```

### test_zammad.py

```python
import os

import pytest
import requests
from zammad_api import Zammad

zammad=Zammad(
    base_url=os.environ.get("ZAMMAD_URL", "http://localhost:8181"),
    username=os.getenv("ZAMMAD_USERNAME"),
    password=os.getenv("ZAMMAD_PASSWORD")
)
state = {}


def test_create_token():
    global zammad
    rsp = zammad.create_token("token_payload.json")
    assert rsp.status_code == 200

    token = rsp.json()
    assert "token" in token

    zammad = Zammad(zammad.base_url, token=token["token"])


#TODO-G: Troubleshoot why the test_create_ticket fails and fix the function
def test_create_ticket():
    rsp = zammad.create_ticket(
        title="Testing the Ticket Creation API",
        customer="james.bond@mi6.com",
        article_body="Mission on Automation API.",
    )
    ## Customers has to one of the following
    """
    "nicole.braun@zammad.org"
    "student@ccie-automation.com"
    "james.bond@mi6.com"
    "sushil.bhattacharjee@mi6.com"
    """
    new_ticket_status = rsp.status_code == 200
    assert new_ticket_status

    ticket = rsp.json()
    assert ticket["title"] == "Test ticket"

    state["ticket_id"] = ticket["id"]

    print(f"\n✅ Ticket created with ID: {ticket['id']}")
def test_get_ticket():
    rsp = zammad.get_ticket(ticket_id=state["ticket_id"])
    assert rsp.status_code == 200

    ticket = rsp.json()
    assert ticket["title"] == "Test ticket"
    print(f"\nTICKET TITLE: {ticket['title']}")

def test_update_ticket():
    rsp = zammad.update_ticket_title(ticket_id=state["ticket_id"], title="Mission ACCOMPLISHED", article_body="Mission accomplished! Closing it!!")
    assert rsp.status_code == 200

    ticket = rsp.json()
    assert ticket["title"] == "New title"
    print(f"\n LATEST TICKET TITLE: {ticket['title']}")

#TODO-H: Troubleshoot why the test_delete_ticket fails and fix the function
def test_delete_ticket():
    rsp = zammad.delete_ticket(ticket_id=state["ticket_id"])
    assert rsp.status_code == 200

    with pytest.raises(requests.exceptions.HTTPError):
        rsp = zammad.get_ticket(ticket_id=state["ticket_id"])
"""
Run all tests

uv run pytest -vv -s
Run specific test file

uv run pytest p2_test_zammad.py -vv -s
Run specific test function

uv run pytest p2_test_zammad.py::test_create_ticket -vv -s
Just use pytest directly (if venv is activated by direnv)

pytest p2_test_zammad.py -vv -s
"""
```

### token_payload.json

```json
# TODO: Requirement C
```

### .envrc

```bash
export ZAMMAD_USERNAME=student@ccie-automation.com
export ZAMMAD_PASSWORD=1234QWer\!\!
export ZAMMAD_URL=http://192.168.89.98:8181
```

### docker-compose.yml

```yaml
---
version: "3.8"

x-shared:
  zammad-service: &zammad-service
    environment: &zammad-environment
      MEMCACHE_SERVERS: ${MEMCACHE_SERVERS:-zammad-memcached:11211}
      POSTGRESQL_DB: ${POSTGRES_DB:-zammad_production}
      POSTGRESQL_HOST: ${POSTGRES_HOST:-zammad-postgresql}
      POSTGRESQL_USER: ${POSTGRES_USER:-zammad}
      POSTGRESQL_PASS: ${POSTGRES_PASS:-zammad}
      POSTGRESQL_PORT: ${POSTGRES_PORT:-5432}
      POSTGRESQL_OPTIONS: ${POSTGRESQL_OPTIONS:-?pool=50}
      POSTGRESQL_DB_CREATE:
      REDIS_URL: ${REDIS_URL:-redis://zammad-redis:6379}
      S3_URL:
      # Backup settings
      BACKUP_DIR: "${BACKUP_DIR:-/var/tmp/zammad}"
      BACKUP_TIME: "${BACKUP_TIME:-03:00}"
      HOLD_DAYS: "${HOLD_DAYS:-10}"
      TZ: "${TZ:-Europe/Berlin}"
      # Allow passing in these variables via .env:
      AUTOWIZARD_JSON:
      AUTOWIZARD_RELATIVE_PATH:
      ELASTICSEARCH_ENABLED:
      ELASTICSEARCH_SCHEMA:
      ELASTICSEARCH_HOST:
      ELASTICSEARCH_PORT:
      ELASTICSEARCH_USER:
      ELASTICSEARCH_PASS:
      ELASTICSEARCH_NAMESPACE:
      ELASTICSEARCH_REINDEX:
      NGINX_PORT:
      NGINX_CLIENT_MAX_BODY_SIZE:
      NGINX_SERVER_NAME:
      NGINX_SERVER_SCHEME:
      RAILS_TRUSTED_PROXIES:
      ZAMMAD_HTTP_TYPE:
      ZAMMAD_FQDN:
      ZAMMAD_WEB_CONCURRENCY:
      ZAMMAD_PROCESS_SESSIONS_JOBS_WORKERS:
      ZAMMAD_PROCESS_SCHEDULED_JOBS_WORKERS:
      ZAMMAD_PROCESS_DELAYED_JOBS_WORKERS:
      # ZAMMAD_SESSION_JOBS_CONCURRENT is deprecated, please use ZAMMAD_PROCESS_SESSIONS_JOBS_WORKERS instead.
      ZAMMAD_SESSION_JOBS_CONCURRENT:
      # Variables used by ngingx-proxy container for reverse proxy creations
      # for docs refer to https://github.com/nginx-proxy/nginx-proxy
      VIRTUAL_HOST:
      VIRTUAL_PORT:
      # Variables used by acme-companion for retrieval of LetsEncrypt certificate
      # for docs refer to https://github.com/nginx-proxy/acme-companion
      LETSENCRYPT_HOST:
      LETSENCRYPT_EMAIL:

    image: ${IMAGE_REPO:-ghcr.io/zammad/zammad}:${VERSION:-6.5.2-85}
    restart: ${RESTART:-always}
    volumes:
      - zammad-storage:/opt/zammad/storage
    depends_on:
      - zammad-memcached
      - zammad-postgresql
      - zammad-redis

services:
  zammad-backup:
    <<: *zammad-service
    command: ["zammad-backup"]
    volumes:
      - zammad-backup:/var/tmp/zammad
      - zammad-storage:/opt/zammad/storage:ro
    user: 0:0

  zammad-elasticsearch:
    image: elasticsearch:${ELASTICSEARCH_VERSION:-8.19.11}
    restart: ${RESTART:-always}
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    environment:
      discovery.type: single-node
      xpack.security.enabled: 'false'
      ES_JAVA_OPTS: ${ELASTICSEARCH_JAVA_OPTS:--Xms1g -Xmx1g}

  zammad-init:
    <<: *zammad-service
    command: ["zammad-init"]
    depends_on:
      - zammad-postgresql
    restart: on-failure
    user: 0:0

  zammad-memcached:
    command: memcached -m 256M
    image: memcached:${MEMCACHE_VERSION:-1.6.40-alpine}
    restart: ${RESTART:-always}

  zammad-nginx:
    <<: *zammad-service
    command: ["zammad-nginx"]
    expose:
      - "${NGINX_PORT:-8080}"
    ports:
      - "${NGINX_EXPOSE_PORT:-8080}:${NGINX_PORT:-8080}"
    depends_on:
      - zammad-railsserver

  zammad-postgresql:
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-zammad_production}
      POSTGRES_USER: ${POSTGRES_USER:-zammad}
      POSTGRES_PASSWORD: ${POSTGRES_PASS:-zammad}
    image: postgres:${POSTGRES_VERSION:-17.7-alpine}
    restart: ${RESTART:-always}
    volumes:
      - postgresql-data:/var/lib/postgresql/data

  zammad-railsserver:
    <<: *zammad-service
    command: ["zammad-railsserver"]

  zammad-redis:
    image: redis:${REDIS_VERSION:-7.4.7-alpine}
    restart: ${RESTART:-always}
    volumes:
      - redis-data:/data

  zammad-scheduler:
    <<: *zammad-service
    command: ["zammad-scheduler"]

  zammad-websocket:
    <<: *zammad-service
    command: ["zammad-websocket"]

volumes:
  elasticsearch-data:
    driver: local
  postgresql-data:
    driver: local
  redis-data:
    driver: local
  zammad-backup:
    driver: local
  zammad-storage:
    driver: local
```

## How to Test
### From F2-RESTAPI-Zammand directory:
#### Run all tests
uv run pytest -vv -s
#### Run specific test file
uv run pytest p2_test_zammad.py -vv -s
#### Run specific test function
uv run pytest p2_test_zammad.py::test_create_ticket -vv -s
#### Just use pytest directly (if venv is activated by direnv)
pytest p2_test_zammad.py -vv -s

## Solution

<details>
<summary>Are you sure? Only use as last resort!</summary>

There are multiple ways to solve the challenge. The following is just an example.

### zammad_api.py

```python
import requests


class Zammad:
    def __init__(self, base_url, token=None, username=None, password=None):
        self.base_url = base_url
        self.session = requests.Session()
        #TODO-A: Implement token based authentication and any needed HTTP headers
        self.session.headers["content-type"]= "application/json"
        self.session.headers["accept"]= "application/json"
        if token:
            #TODO-A: Requirement A
            self.session.headers["authorization"]= f"Bearer {token}"
        elif username and password:
            #TODO-B: Implement basic username/password authentication and any needed HTTP headers
            self.session.auth=(username, password)
        else:
            raise Exception("Token or user access credentials must be provided")

    def list_tickets(self):
        rsp = self.session.get(f"{self.base_url}/api/v1/tickets")
        rsp.raise_for_status()
        return rsp

    def get_ticket(self, ticket_id):
        #TODO-E: Use the API to get a specific ticket based on ID
        rsp = self.session.get(f"{self.base_url}/api/v1/tickets/{ticket_id}")
        rsp.raise_for_status()
        return rsp

    def create_ticket(self, title, customer, article_body):
        payload = {
            "title": title,
            "group": "Users",
            "customer": customer,
            "article": {
                "body": article_body,
            },
        }
        #! With newer version, group has to be Users, numbers are not working
        rsp = self.session.post(f"{self.base_url}/api/v1/tickets", json=payload)
        rsp.raise_for_status()
        return rsp

    def update_ticket_title(self, ticket_id, title, article_body):
        #TODO-F: Use the API to update a specific ticket title based on ID
        payload= {
            "title": title,
            "group": "Users",
            "article": {
                "body": article_body
            }
        }
        #! With newer version, group has to be Users, numbers are not working
        rsp = self.session.put(f"{self.base_url}/api/v1/tickets/{ticket_id}", json=payload)
        rsp.raise_for_status()
        return rsp

    def delete_ticket(self, ticket_id):
        rsp = self.session.delete(f"{self.base_url}/api/v1/tickets/{ticket_id}")
        rsp.raise_for_status()
        return rsp

    def create_token(self, filename):
        with open(filename) as f:
            payload = f.read()
        #TODO-D: Include the JSON payload with the request
        rsp = self.session.post(f"{self.base_url}/api/v1/user_access_token", data=payload)
        print(rsp.content)
        rsp.raise_for_status()
        return rsp
```

### test_zammad.py

```python
import os

import pytest
import requests
from p2_zammad_api import Zammad

zammad=Zammad(
    base_url=os.environ.get("ZAMMAD_URL", "http://localhost:8181"),
    username=os.getenv("ZAMMAD_USERNAME"),
    password=os.getenv("ZAMMAD_PASSWORD")
)
state = {}


def test_create_token():
    global zammad
    rsp = zammad.create_token("p2_token_payload.json")
    assert rsp.status_code == 200
    token = rsp.json()
    assert "token" in token
    zammad = Zammad(zammad.base_url, token=token["token"])


#TODO-G: Troubleshoot why the test_create_ticket fails and fix the function
def test_create_ticket():
    rsp = zammad.create_ticket(
        title="P2 Testing the Ticket Creation API",
        customer="student@ccie-automation.com",
        article_body="P2-Mission on Automation API.",
    )
    ## Customers has to one of the following
    """
    "nicole.braun@zammad.org"
    "student@ccie-automation.com"
    "james.bond@mi6.com"
    "sushil.bhattacharjee@mi6.com"
    """
    new_ticket_status = rsp.status_code == 201
    assert new_ticket_status

    ticket = rsp.json()
    assert ticket["title"] == "P2 Testing the Ticket Creation API"

    state["ticket_id"] = ticket["id"]

    print(f"\n✅ Ticket created with ID: {ticket['id']}")
def test_get_ticket():
    rsp = zammad.get_ticket(ticket_id=state["ticket_id"])
    assert rsp.status_code == 200

    ticket = rsp.json()
    assert ticket["title"] == "P2 Testing the Ticket Creation API"
    print(f"\nTICKET TITLE: {ticket['title']}")

def test_update_ticket():
    rsp = zammad.update_ticket_title(ticket_id=state["ticket_id"], title="Mission ACCOMPLISHED", article_body="P2-Mission on Automation API.")
    assert rsp.status_code == 200

    ticket = rsp.json()
    assert ticket["title"] == "Mission ACCOMPLISHED"
    print(f"\n LATEST TICKET TITLE: {ticket['title']}")

#TODO-H: Troubleshoot why the test_delete_ticket fails and fix the function
def test_delete_ticket():
    rsp = zammad.delete_ticket(ticket_id=state["ticket_id"])
    assert rsp.status_code == 200

    with pytest.raises(requests.exceptions.HTTPError):
        rsp = zammad.get_ticket(ticket_id=state["ticket_id"])
```

### token_payload.json

```json
{
   "name": "My amazing test",
   "permission": ["ticket.agent", "admin"],
   "expires_at": null
}
```

</details>