variable "name" {
  type        = string
  description = "Name prefix for this database. Used as the RDS identifier."
}

variable "database_name" {
  type        = string
  description = "Initial database created on the instance."
}

variable "subnet_group_name" {
  type        = string
  description = "DB subnet group. The subnets must be private."
}

variable "security_group_id" {
  type        = string
  description = "Security group that allows PostgreSQL from the API."
}
