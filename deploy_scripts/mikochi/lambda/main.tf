provider "aws" {
  profile = "terraform_holoscope"
  region  = "ap-northeast-1"
}

# Variables
variable "system_name" {
  default = "terraform-lambda-mikochi"
}

# Archive
data "archive_file" "layer_zip" {
  type        = "zip"
  source_dir  = "build/layer"
  output_path = "lambda/layer.zip"
}
data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "build/function"
  output_path = "lambda/function.zip"
}

# Layer
resource "aws_lambda_layer_version" "lambda_layer" {
  layer_name       = "${var.system_name}_lambda_layer"
  filename         = data.archive_file.layer_zip.output_path
  source_code_hash = data.archive_file.layer_zip.output_base64sha256
}

# Function
resource "aws_lambda_function" "hololine_mikochi" {
  function_name    = "${var.system_name}"
  handler          = "run.lambda_handler"
  filename         = data.archive_file.function_zip.output_path
  runtime          = "python3.9"
  role             = aws_iam_role.lambda_iam_role.arn
  source_code_hash = data.archive_file.function_zip.output_base64sha256
  layers           = [aws_lambda_layer_version.lambda_layer.arn]
  timeout          = 30
}

# cloudwatch event rule
resource "aws_cloudwatch_event_rule" "hololine_mikochi_event_rule" {
    name                = "${var.system_name}_holoscope_scheduler"
    description         = "Run holoscope every 15 minutes"
    schedule_expression = "cron(4/15 0-17,21-23 * * ? *)"
}

# cloudwatch event target
resource "aws_cloudwatch_event_target" "hololine_mikochi_event_target" {
    rule      = aws_cloudwatch_event_rule.hololine_mikochi_event_rule.name
    target_id = "hololine_mikochi"
    arn       = aws_lambda_function.hololine_mikochi.arn
}

# Permission
resource "aws_lambda_permission" "allow_cloudwatch_to_call_holoscope" {
    statement_id  = "AllowExecutionFromCloudWatch"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.hololine_mikochi.function_name
    principal     = "events.amazonaws.com"
    source_arn    = aws_cloudwatch_event_rule.hololine_mikochi_event_rule.arn
}

# Role
resource "aws_iam_role" "lambda_iam_role" {
  name = "${var.system_name}_iam_role"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
POLICY
}

# Policy
resource "aws_iam_role_policy" "lambda_access_policy" {
  name   = "${var.system_name}_lambda_access_policy"
  role   = aws_iam_role.lambda_iam_role.id
  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
         "dynamodb:ListTables",
         "dynamodb:DeleteItem",
         "dynamodb:DescribeContributorInsights",
         "dynamodb:ListTagsOfResource",
         "dynamodb:DeleteTable",
         "dynamodb:DescribeReservedCapacityOfferings",
         "dynamodb:PartiQLSelect",
         "dynamodb:DescribeTable",
         "dynamodb:GetItem",
         "dynamodb:DescribeContinuousBackups",
         "dynamodb:DescribeExport",
         "dynamodb:DescribeKinesisStreamingDestination",
         "dynamodb:DescribeLimits",
         "dynamodb:BatchGetItem",
         "dynamodb:ConditionCheckItem",
         "dynamodb:Scan",
         "dynamodb:Query",
         "dynamodb:DescribeStream",
         "dynamodb:UpdateItem",
         "dynamodb:DescribeTimeToLive",
         "dynamodb:ListStreams",
         "dynamodb:CreateTable",
         "dynamodb:DescribeGlobalTableSettings",
         "dynamodb:GetShardIterator",
         "dynamodb:DescribeGlobalTable",
         "dynamodb:DescribeReservedCapacity",
         "dynamodb:DescribeBackup",
         "dynamodb:UpdateTable",
         "dynamodb:GetRecords",
         "dynamodb:DescribeTableReplicaAutoScaling",
         "kms:GetPublicKey",
         "kms:ListResourceTags",
         "kms:GetParametersForImport",
         "kms:DescribeCustomKeyStores",
         "kms:GetKeyRotationStatus",
         "kms:DescribeKey",
         "kms:ListKeyPolicies",
         "kms:ListRetirableGrants",
         "kms:GetKeyPolicy",
         "kms:ListGrants",
         "kms:ListKeys",
         "kms:ListAliases",
         "logs:CreateLogStream",
         "logs:CreateLogGroup",
         "logs:PutLogEvents",
         "s3:DeleteObject",
         "s3:ListBucket",
         "s3:HeadObject",
         "s3:GetObject",
         "s3:GetObjectVersion",
         "s3:PutObject",
         "s3:PutObjectAcl",
         "s3-object-lambda:*"
      ],
      "Resource": "*"
    }
  ]
}
POLICY
}
