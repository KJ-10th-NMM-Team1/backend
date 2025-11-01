import os, boto3
from dotenv import load_dotenv

load_dotenv()


aws_profile = os.getenv("AWS_PROFILE")
aws_region = os.getenv("AWS_REGION", "ap-northeast-2")

session_kwargs = {}
if aws_profile:
    session_kwargs["profile_name"] = aws_profile

session = boto3.Session(**session_kwargs, region_name=aws_region)
s3 = session.client("s3")
