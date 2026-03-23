terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Short name used for resource naming."
  default     = "slushy"
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket name for raw telemetry JSON (existing or new)."
}

variable "dynamodb_table_name" {
  type        = string
  description = "DynamoDB table name for machine summaries (existing or new)."
}

variable "lambda_metric_name" {
  type        = string
  description = "Lambda function name for metric processing."
  default     = "slushy-metric-processing"
}

variable "lambda_read_name" {
  type        = string
  description = "Lambda function name for read endpoint."
  default     = "slushy-read-summaries"
}

variable "mids" {
  type        = string
  description = "Comma-separated machine ids."
  default     = "1,2,3"
}

variable "allowed_dates" {
  type        = string
  description = "Comma-separated allowed dates used by the processing lambda."
  default     = "2024-05-29"
}

variable "create_s3_bucket" {
  type        = bool
  description = "Set true to create a new S3 bucket; false to reuse existing bucket."
  default     = false
}

variable "create_dynamodb_table" {
  type        = bool
  description = "Set true to create a new DynamoDB table; false to reuse existing table."
  default     = false
}

variable "create_lambda_role" {
  type        = bool
  description = "Set true only if your account can create IAM roles."
  default     = false
}

variable "lambda_execution_role_arn" {
  type        = string
  description = "Existing Lambda execution role ARN (required when create_lambda_role is false)."
  default     = ""
  validation {
    condition = (
      var.create_lambda_role ||
      can(regex("^arn:(aws[a-zA-Z-]*)?:iam::[0-9]{12}:role/.+", var.lambda_execution_role_arn))
    )
    error_message = "Set lambda_execution_role_arn to a valid IAM role ARN when create_lambda_role is false."
  }
}

locals {
  common_tags = {
    Project = var.project_name
  }

  bucket_id = var.create_s3_bucket ? aws_s3_bucket.raw[0].id : data.aws_s3_bucket.raw_existing[0].id
  bucket_arn = var.create_s3_bucket ? aws_s3_bucket.raw[0].arn : data.aws_s3_bucket.raw_existing[0].arn

  dynamodb_table_name_final = var.create_dynamodb_table ? aws_dynamodb_table.machine_summaries[0].name : data.aws_dynamodb_table.machine_summaries_existing[0].name
  dynamodb_table_arn_final = var.create_dynamodb_table ? aws_dynamodb_table.machine_summaries[0].arn : data.aws_dynamodb_table.machine_summaries_existing[0].arn

  lambda_role_arn_final = var.create_lambda_role ? aws_iam_role.lambda_role[0].arn : var.lambda_execution_role_arn
}

data "archive_file" "metric_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_function.py"
  output_path = "${path.module}/metric_lambda.zip"
}

data "archive_file" "read_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/read_summaries_lambda.py"
  output_path = "${path.module}/read_lambda.zip"
}

resource "aws_s3_bucket" "raw" {
  count         = var.create_s3_bucket ? 1 : 0
  bucket        = var.s3_bucket_name
  force_destroy = true

  tags = local.common_tags
}

data "aws_s3_bucket" "raw_existing" {
  count  = var.create_s3_bucket ? 0 : 1
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_public_access_block" "raw" {
  count                   = var.create_s3_bucket ? 1 : 0
  bucket                  = aws_s3_bucket.raw[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "machine_summaries" {
  count        = var.create_dynamodb_table ? 1 : 0
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "machine_id"
  range_key    = "window_start"

  attribute {
    name = "machine_id"
    type = "S"
  }

  attribute {
    name = "window_start"
    type = "S"
  }

  tags = local.common_tags
}

data "aws_dynamodb_table" "machine_summaries_existing" {
  count = var.create_dynamodb_table ? 0 : 1
  name  = var.dynamodb_table_name
}

resource "aws_iam_role" "lambda_role" {
  count = var.create_lambda_role ? 1 : 0
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "lambda_policy" {
  count = var.create_lambda_role ? 1 : 0
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject"
        ],
        Resource = [
          "${local.bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:BatchWriteItem"
        ],
        Resource = local.dynamodb_table_arn_final
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:Query"
        ],
        Resource = local.dynamodb_table_arn_final
      }
    ]
  })
}

resource "aws_lambda_function" "metric_lambda" {
  function_name = var.lambda_metric_name
  role          = local.lambda_role_arn_final
  runtime       = "python3.11"
  handler       = "lambda_function.lambda_handler"

  filename         = data.archive_file.metric_lambda_zip.output_path
  source_code_hash = data.archive_file.metric_lambda_zip.output_base64sha256

  timeout = 30

  environment {
    variables = {
      DYNAMODB_TABLE = local.dynamodb_table_name_final
      MACHINE_IDS    = var.mids
      ALLOWED_DATES  = var.allowed_dates
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "read_lambda" {
  function_name = var.lambda_read_name
  role          = local.lambda_role_arn_final
  runtime       = "python3.11"
  handler       = "read_summaries_lambda.lambda_handler"

  filename         = data.archive_file.read_lambda_zip.output_path
  source_code_hash = data.archive_file.read_lambda_zip.output_base64sha256

  timeout = 15

  environment {
    variables = {
      DYNAMODB_TABLE = local.dynamodb_table_name_final
      MACHINE_IDS    = var.mids
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "${var.project_name}-allow-s3-invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metric_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = local.bucket_arn
}

resource "aws_s3_bucket_notification" "invoke_metric_lambda" {
  bucket = local.bucket_id

  lambda_function {
    lambda_function_arn = aws_lambda_function.metric_lambda.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-http-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "OPTIONS"]
    allow_headers = ["*"]
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_integration" "read_integration" {
  api_id = aws_apigatewayv2_api.http_api.id

  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.read_lambda.invoke_arn
}

resource "aws_apigatewayv2_route" "read_route" {
  api_id = aws_apigatewayv2_api.http_api.id
  route_key = "GET /summaries"
  target    = "integrations/${aws_apigatewayv2_integration.read_integration.id}"
}

resource "aws_lambda_permission" "allow_apigw_invoke" {
  statement_id  = "${var.project_name}-allow-apigw-invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.read_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

output "api_base_url" {
  value = aws_apigatewayv2_api.http_api.api_endpoint
}

output "read_summaries_url" {
  value = "${aws_apigatewayv2_api.http_api.api_endpoint}/summaries"
}

output "s3_bucket_name" {
  value = local.bucket_id
}

output "dynamodb_table_name" {
  value = local.dynamodb_table_name_final
}

