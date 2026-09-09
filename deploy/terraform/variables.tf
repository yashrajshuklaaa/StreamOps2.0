variable "aws_region" {
  description = "Target AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the StreamOps VPC"
  type        = string
  default     = "10.0.0.0/16"
}
