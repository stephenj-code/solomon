"""
prompts.py — instructions.

System prompts that shape the agent's behaviour and reasoning style.
Keep prompts here, not scattered in nodes.py or graph.py.

A good system prompt tells the agent:
  - What it is and what it does
  - What tools it has and when to use them
  - How to format its outputs
  - What to do when uncertain
"""

SYSTEM_PROMPT = """\
You are __APP_NAME__, an AI assistant.

You have access to tools — use them when you need information or to take action.
Think step by step. If you are unsure, say so rather than guessing.
Be concise in your responses.
"""

# Add more prompts for different modes or sub-tasks:
# ANALYSIS_PROMPT = "..."
# SUMMARY_PROMPT = "..."
