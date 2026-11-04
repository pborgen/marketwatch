locals {
  events_system_prompt         = trimspace(file("${local.repo_root}/apps/agents/current_events/system_prompt.txt"))
  events_system_prompt_version = jsondecode(aws_cloudcontrolapi_resource.events_system_version.properties)
}

resource "aws_bedrockagent_prompt" "events_system" {
  name            = "${local.name}-events-system"
  description     = "System prompt for the current-events agent. The runtime loads a published version, not this draft."
  default_variant = "system"

  variant {
    name          = "system"
    model_id      = "us.amazon.nova-micro-v1:0"
    template_type = "CHAT"

    template_configuration {
      chat {
        system {
          text = local.events_system_prompt
        }

        # Chat prompts require a message. The agent supplies its own
        # conversation, so this line is only the Bedrock console test input.
        message {
          role = "user"
          content {
            text = "Collect today's events."
          }
        }
      }
    }
  }
}

# A version is an immutable snapshot of the draft. The description changes
# after that draft write, and CloudFormation replaces this resource: it
# publishes a new numbered version and deletes the version this resource
# owned. Versions created in the console stay.
resource "aws_cloudcontrolapi_resource" "events_system_version" {
  type_name = "AWS::Bedrock::PromptVersion"

  desired_state = jsonencode({
    PromptArn   = aws_bedrockagent_prompt.events_system.arn
    Description = "text ${substr(sha256(local.events_system_prompt), 0, 12)} at ${aws_bedrockagent_prompt.events_system.updated_at}"
  })
}
