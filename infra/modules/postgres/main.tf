resource "aws_db_parameter_group" "this" {
  name        = var.name
  family      = "postgres16"
  description = "Require TLS."

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }
}

resource "aws_db_instance" "this" {
  identifier = var.name

  engine         = "postgres"
  engine_version = "16.15"
  instance_class = "db.t4g.micro"

  db_name  = var.database_name
  username = "marketwatch"
  port     = 5432

  manage_master_user_password = true

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_subnet_group_name   = var.subnet_group_name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = false

  parameter_group_name = aws_db_parameter_group.this.name

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  auto_minor_version_upgrade = true

  lifecycle {
    ignore_changes = [engine_version]
  }
}
