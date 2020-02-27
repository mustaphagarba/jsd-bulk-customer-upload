import logging
import argparse

from bulk_customer_import import client as sdclient
from bulk_customer_import import utils

parser = argparse.ArgumentParser()
parser.add_argument("base_url", help="The url of the hosted instance of JIRA")
parser.add_argument("auth_user", help="Username for basic http authentication")
parser.add_argument("auth_pass", help="Password for basic http authentication")
parser.add_argument("filename", help="The name of the csv for bulk upload")
parser.add_argument("servicedesk_id", help="The id of the service desk")
parser.add_argument(
    "--verify",
    choices=["True", "False"],
    default="True",
    type=bool,
    help="Verify the ssl certificate")
parser.add_argument(
    "-l",
    "--loglevel",
    type=str.upper,
    default="INFO",
    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    help="Set log level",
)
args = parser.parse_args()

logging.basicConfig(
    level=args.loglevel, format="%(asctime)s - %(levelname)s - %(message)s"
)

jira_session = None
api_url = args.base_url + "/rest/servicedeskapi"

rows_not_processed = []


def main():

    client = sdclient.get_client(
        base_url=args.base_url,
        auth_user=args.auth_user,
        auth_pass=args.auth_pass)

    servicedesk_id = args.servicedesk_id
    # Parse CSV
    rows = utils.parse_csv(args.filename)
    # Get Organisations
    organizations = client.organization.list()

    # For each row in the CSV (skip header)
    for row in rows[1:]:
        try:
            organization_name, customer_name, customer_email = (
                row[0],
                row[1],
                row[2],
            )

            customer_name_key = "fullName"
            if client.plaform == "cloud":
                customer_name_key = "displayName"

            # Create the customer if they do not already exist
            new_customer = {
                customer_name_key: customer_name,
                "emailAddress": customer_email,
            }
            existing_customer = client.customer.create(new_customer)
            customer = existing_customer if existing_customer else new_customer

            # Create organisation if one does not exist
            if organization_name in organizations.keys():
                organization = organizations[organization_name]
            else:
                organization = client.organization.create(
                    organization_name).json()
                client.servicedesk.add_organization(
                    args.servicedesk_id, organization
                )

            # Move the customer into the organization
            client.add_customer_to_organization(organization, customer)

            # Add the customer into the service desk
            client.servicedesk.add_customer(servicedesk_id, customer)
        except Exception as e:
            print("Failed to process row: {}".format(row))
            logging.exception(e)
            rows_not_processed.append(row)

    if rows_not_processed:
        print("An error occurred while processing the following rows.")
        for row in rows_not_processed:
            print(row)


if __name__ == "__main__":
    main()