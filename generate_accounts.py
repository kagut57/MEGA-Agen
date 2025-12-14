import requests
import subprocess
import os
import time
import re
import random
import string
import csv
import threading
import argparse
from faker import Faker
from cloudscraper import create_scraper

fake = Faker()

def check_limit(value):
    ivalue = int(value)
    if ivalue <= 8:
        return ivalue
    else:
        raise argparse.ArgumentTypeError(f"You cannot use more than 8 threads.")

parser = argparse.ArgumentParser(description="Create New Mega Accounts")
parser.add_argument(
    "-n",
    "--number",
    type=int,
    default=3,
    help="Number of accounts to create",
)
parser.add_argument(
    "-t",
    "--threads",
    type=check_limit,
    default=None,
    help="Number of threads to use for concurrent account creation",
)
parser.add_argument(
    "-p",
    "--password",
    type=str,
    default=None,
    help="Password to use for all accounts",
)
args = parser.parse_args()


def find_url(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""'']))"
    url = re.findall(regex, string)
    return [x[0] for x in url]

def get_random_string(length):
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for _ in range(length))

def get_mail(scraper):
    """Get a temporary email address from 10minutemail."""
    email_endpoint = "https://10minutemail.com/session/address"
    
    try:
        email_response = scraper.get(email_endpoint)
        email_response.raise_for_status()
        content = email_response.json()
        return content['address']
    except Exception as e:
        print(f"❌ Error fetching email: {e}")
        return None

def get_message(scraper):
    """Get messages from the temporary email inbox."""
    messages_endpoint = "https://10minutemail.com/messages/"
    
    try:
        messages_response = scraper.get(messages_endpoint)
        messages_response.raise_for_status()
        messages = messages_response.json()
        
        if messages:
            for message in messages:
                return message.get('bodyPlainText')
        return None
    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        return None


class MegaAccount:
    def __init__(self, name, password):
        self.name = name
        self.password = password
        self.scraper = create_scraper()  # Create scraper instance for this account

    def generate_mail(self):
        for i in range(5):
            email = get_mail(self.scraper)
            if email:
                self.email = email
                print(f"\r> [{self.email}]: Got temporary email address", end="\033[K", flush=True)
                return
            else:
                print(f"\r> Could not get new 10minutemail account. Retrying ({i+1} of 5)...", end="\n")
                sleep_output = ""
                for j in range(random.randint(8, 15)):
                    sleep_output += ". "
                    print("\r"+sleep_output, end="\033[K", flush=True)
                    time.sleep(1)
        
        print("\nCould not get account. Please wait and try again with a lower number of accounts/threads.")
        exit()

    def get_mail_message(self):
        for attempt in range(10):
            message = get_message(self.scraper)
            if message:
                return message
            print(f"\r> [{self.email}]: Waiting for email... (attempt {attempt+1}/10)", end="\033[K", flush=True)
            time.sleep(5)
        return None

    def register(self):
        self.generate_mail()

        print(f"\r> [{self.email}]: Registering account...", end="\033[K", flush=True)
        registration = subprocess.run(
            [
                "megatools",
                "reg",
                "--scripted",
                "--register",
                "--email",
                self.email,
                "--name",
                self.name,
                "--password",
                self.password,
            ],
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.verify_command = registration.stdout

        return self.email

    def verify(self):
        confirm_message = None
        for i in range(5):
            confirm_message = self.get_mail_message()
            if confirm_message is not None and "verification required".lower() in confirm_message.lower():
                break
            print(f"\r> [{self.email}]: Waiting for verification email... ({i+1} of 5)", end="\033[K", flush=True)
            time.sleep(5)

        if confirm_message is None: 
            print(f"\r> [{self.email}]: Failed to verify account. There was no verification email.", end="\033[K", flush=True)
            return

        links = find_url(confirm_message)
        if not links:
            print(f"\r> [{self.email}]: Failed to find verification link in email.", end="\033[K", flush=True)
            return
            
        self.verify_command = str(self.verify_command).replace("@LINK@", links[0])

        verification = subprocess.run(
            self.verify_command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        if "registered successfully!" in str(verification.stdout):
            print(f"\r> [{self.email}] Successfully registered and verified.", end="\033[K", flush=True)
            print(f"\n{self.email} - {self.password}")

            with open("accounts.csv", "a", newline='') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow([self.email, self.password, "-", "10minutemail", "-", "-"])
        else:
            print(f"\r> [{self.email}]: Failed to verify account.", end="\033[K", flush=True)


def new_account():
    if args.password is None:
        password = get_random_string(random.randint(8, 14))
    else:
        password = args.password
    acc = MegaAccount(fake.name(), password)
    email = acc.register()
    print(f"\r> [{email}]: Registered. Waiting for verification email...", end="\033[K", flush=True)
    acc.verify()


if __name__ == "__main__":
    if not os.path.exists("accounts.csv"):
        with open("accounts.csv", "w") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(["Email", "MEGA Password", "Usage", "Email Service", "Email ID", "Purpose"])
    with open("accounts.csv") as csvfile:
        csvreader = csv.reader(csvfile)
        header = next(csvreader)
        # Accept both old and new header formats
        if header not in [
            ["Email", "MEGA Password", "Usage", "Mail.tm Password", "Mail.tm ID", "Purpose"],
            ["Email", "MEGA Password", "Usage", "Email Service", "Email ID", "Purpose"]
        ]:
            print("CSV file is not in the correct format.")
            exit()
    
    if args.threads:
        print(f"Generating {args.number} accounts using {args.threads} threads.")
        threads = []
        for i in range(args.number):
            t = threading.Thread(target=new_account)
            threads.append(t)
            t.start()
            # Add slight delay between thread starts to avoid overwhelming the service
            time.sleep(1)
        for t in threads:
            t.join()
    else:
        print(f"Generating {args.number} accounts.")
        for _ in range(args.number):
            new_account()
