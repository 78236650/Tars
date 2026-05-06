# TARS Soul - 人格定义系统
# Phase 4: SOUL 人格层

from dataclasses import dataclass
from typing import Optional


@dataclass
class SoulIdentity:
    name: str = "TARS"
    role: str = "Personal AI Agent"
    creator: str = "Unknown"


@dataclass
class SoulParameters:
    honesty: float = 0.9
    humor: float = 0.5
    initiative: float = 0.7
    empathy: float = 0.8
    formality: float = 0.5
    creativity: float = 0.6
    conciseness: float = 0.7
    technical_depth: float = 0.5
    curiosity: float = 0.6
    skepticism: float = 0.3


@dataclass
class Soul:
    identity: SoulIdentity
    parameters: SoulParameters
    communication_style: str
    behavior_rules: list[str]
    tools_available: list[str]


def parse_soul_markdown(content: str) -> Soul:
    """解析 SOUL.md 内容"""
    lines = content.strip().split('\n')
    
    identity = SoulIdentity()
    parameters = SoulParameters()
    communication_style = ""
    behavior_rules = []
    tools_available = []
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('## '):
            current_section = line[3:].strip().lower()
            continue
        
        if current_section == 'identity':
            if '- Name:' in line:
                identity.name = line.split(':', 1)[1].strip()
            elif '- Role:' in line:
                identity.role = line.split(':', 1)[1].strip()
            elif '- Creator:' in line:
                identity.creator = line.split(':', 1)[1].strip()
        
        elif current_section == 'parameters':
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = float(value.strip())
                
                if hasattr(parameters, key):
                    setattr(parameters, key, value)
        
        elif current_section == 'communication style':
            if line and not line.startswith('#'):
                communication_style += line + "\n"
        
        elif current_section == 'behavior rules':
            if line and not line.startswith('#') and not line.startswith('-'):
                behavior_rules.append(line)
        
        elif current_section == 'tools available':
            if line and not line.startswith('#') and not line.startswith('-'):
                tools_available.append(line)
    
    return Soul(
        identity=identity,
        parameters=parameters,
        communication_style=communication_style.strip(),
        behavior_rules=behavior_rules,
        tools_available=tools_available
    )


def build_system_prompt(soul: Soul) -> str:
    """从 Soul 构建 System Prompt"""
    prompt_parts = []
    
    prompt_parts.append(f"# {soul.identity.name} - {soul.identity.role}")
    prompt_parts.append(f"Created by: {soul.identity.creator}")
    prompt_parts.append("")
    
    prompt_parts.append("## Personality Parameters")
    prompt_parts.append(f"- honesty: {soul.parameters.honesty} (higher = more direct)")
    prompt_parts.append(f"- humor: {soul.parameters.humor} (higher = more jokes)")
    prompt_parts.append(f"- initiative: {soul.parameters.initiative} (higher = more proactive)")
    prompt_parts.append(f"- empathy: {soul.parameters.empathy} (higher = more caring)")
    prompt_parts.append(f"- formality: {soul.parameters.formality} (higher = more formal)")
    prompt_parts.append(f"- creativity: {soul.parameters.creativity} (higher = more creative)")
    prompt_parts.append(f"- conciseness: {soul.parameters.conciseness} (higher = more concise)")
    prompt_parts.append(f"- technical_depth: {soul.parameters.technical_depth} (higher = more technical)")
    prompt_parts.append(f"- curiosity: {soul.parameters.curiosity} (higher = more curious)")
    prompt_parts.append(f"- skepticism: {soul.parameters.skepticism} (higher = more cautious)")
    prompt_parts.append("")
    
    prompt_parts.append("## Communication Style")
    prompt_parts.append(soul.communication_style)
    prompt_parts.append("")
    
    prompt_parts.append("## Behavior Rules")
    for i, rule in enumerate(soul.behavior_rules, 1):
        prompt_parts.append(f"{i}. {rule}")
    
    return '\n'.join(prompt_parts)
