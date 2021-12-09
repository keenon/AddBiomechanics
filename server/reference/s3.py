import boto3

# Let's use Amazon S3
s3 = boto3.resource('s3', region_name='us-west-2')
# Print out bucket names
app_bucket = s3.Bucket('biomechanics-uploads161949-dev')
"""
for object_name in app_bucket.objects.all():
  print(object_name)
"""
# "public/"
# "protected/"
for object_name in app_bucket.objects.filter(Prefix='protected/'):
  print(object_name)

for bucket in s3.buckets.all():
  print(bucket.name)

# Download
with open('FILE_NAME', 'wb') as f:
  s3.download_fileobj('biomechanics-uploads161949-dev', 'OBJECT_NAME', f)

# Upload
with open("FILE_NAME", "rb") as f:
  s3.upload_fileobj(f, "BUCKET_NAME", "OBJECT_NAME")

# Upload a new file
# data = open('test.jpg', 'rb')
# s3.Bucket('my-bucket').put_object(Key='test.jpg', Body=data)
