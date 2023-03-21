provider "aws" {
  profile = "terraform_holoscope"
  region  = "ap-northeast-1"
}

#----------------------------------------
# S3作成
#----------------------------------------
#バケット作成

resource "aws_s3_bucket" "ical-bucket" {
  bucket = "ical-bucket"
  tags = {
    Name = "ical-bucket"
  }
}

#パブリックアクセスを全て許可
resource "aws_s3_bucket_public_access_block" "ical-bucket_pb" {
  bucket                  = aws_s3_bucket.ical-bucket.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# ACLの設定
//private:デフォルトACL。所有者に FULL_CONTROL が付与される
resource "aws_s3_bucket_acl" "ical-bucket_acl" {
  bucket = aws_s3_bucket.ical-bucket.id
  acl    = "private"
}

# S3 versioning disable
resource "aws_s3_bucket_versioning" "versioning_config" {
  bucket = aws_s3_bucket.ical-bucket.id
  versioning_configuration {
    status = "Disabled"
  }
}

