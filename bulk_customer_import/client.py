import json
import logging

from urllib.parse import urlparse
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

LOG = logging.getLogger(__name__)


class Client(object):
    def __init__(self, base_url=None, auth_user=None, auth_pass=None,
                 verify=None, **kwargs):
        if not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        self.verify = verify
        self.api_url = urljoin(self.base_url, "rest/servicedesk_api/")
        self.auth_pass = auth_pass
        self.auth_user = auth_user
        self.organization = OrganizationManager(self)
        self.customer = CustomerManager(self)
        self.servicedesk = ServicedeskManager(self)

    def request(self, method, url, verify=True, experimental=False, **kwargs):

        headers = kwargs.pop("headers", {})
        if experimental and self.platform == "server":
            headers.update({"X-ExperimentalApi": "opt-in"})
        if experimental and self.platform == "cloud":
            headers.update({"X-ExperimentalApi": "true"})

        url = urljoin(self.api_url, url)
        LOG.debug(f"{method} {url} {headers} {kwargs}")
        auth = HTTPBasicAuth(self.auth_user, self.auth_pass)
        print(auth, self.auth_user, self.auth_pass)

        return requests.request(
            method, url, auth=auth, headers=headers, **kwargs
        )

    def post(self, url, **kwargs):

        if "data" in kwargs:
            kwargs["data"] = json.dumps(["kwargs"])
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def get_paginated_resource(self, url, content_key, **kwargs):

        results, last_page, start = [], False, 0
        params = kwargs.get("params", {})
        while not last_page:
            params["start"] = start
            response = self.get(url, **kwargs)

            if response.ok:
                _json = json.loads(response.text)
                last_page = _json["isLastPage"]
                start += _json["size"]
                results += _json[content_key]

        return results

    @property
    def platform(self):
        if urlparse(self.base_url).netloc.endswith("atlassian.net"):
            return "cloud"
        return "server"


client = None


def get_client(*args, **kwargs):
    global client
    if client:
        return client
    return  Client(*args, **kwargs)


class OrganizationManager(object):
    def __init__(self, client):
        self.client = client

    def list(self):
        organizations = self.client.get_paginated_resource(
            "organization", "values", experimental=True
        )
        return {
            organization["name"]: organization
            for organization in organizations
        }

    def create(self, name):
        return self.client.post(
            "organization", data={"name": name}, experimental=True
        )

    def add_customers(self, organization, customers):

        # TODO(Simon): to do confirm if this is correct for server
        fields = ("usernames", "emailAddress")
        if self.client.platform == "cloud":
            fields = ("accountIds", "accountId")
        data = {fields[0]: [customer[fields[1]] for customer in customers]}
        self.client.post(
            f"/organization/{organization}/user", data=data, experimental=True
        )


class CustomerManager(object):
    def __init__(self, client):
        self.client = client

    def create(self, name, email):

        name_field_key = "fullName"
        if self.client.platform == "cloud":
            name_field_key = "displayName"

        customer = {"email": email, name_field_key: name}
        return self.client.post("customer", data=customer, experimental=True)


class ServicedeskManager(object):
    def __init__(self, client):
        self.client = client

    def add_organisation(self, servicedesk, organization):

        LOG.info(
            f"Adding organization to service desk: " "{organization['name']}"
        )

        return self.client.post(
            f"/servicedesk/{servicedesk}/organization",
            data={"organizationId": organization["id"]},
            experimental=True,
        )

    def add_customer(self, servicedesk, customers):

        LOG.info(f"Adding customers to service desk: {customers}")

        # TODO(Simon): to do confirm if this is correct for server
        fields = ("usernames", "emailAddress")
        if self.client.platform == "cloud":
            fields = ("accountIds", "accountId")
        data = {fields[0]: [customer[fields[1]] for customer in customers]}

        return self.client.post(
            f"/servicedesk/{servicedesk}/customer",
            data=data,
            experimental=True,
        )
