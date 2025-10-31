import os, boto3
from dotenv import load_dotenv

load_dotenv()

session = boto3.Session(profile_name=os.getenv("AWS_PROFILE", "dev"))
s3 = session.client("s3", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
