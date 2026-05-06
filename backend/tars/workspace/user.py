# TARS User - 用户画像系统
# Phase 4: USER 用户画像

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserProfile:
    name: str = "User"
    role: str = "Unknown"
    timezone: str = "UTC"
    language: str = "zh"


@dataclass
class UserPreferences:
    reply_style: str = "concise"
    technical_depth: str = "medium"
    feedback_style: str = "direct"


@dataclass
class User:
    profile: UserProfile
    interests: list[str]
    preferences: UserPreferences


def parse_user_markdown(content: str) -> User:
    """解析 USER.md 内容"""
    lines = content.strip().split('\n')
    
    profile = UserProfile()
    interests = []
    preferences = UserPreferences()
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('## '):
            current_section = line[3:].strip().lower()
            continue
        
        if current_section == 'profile':
            if '- 称呼:' in line or '- Name:' in line:
                profile.name = line.split(':', 1)[1].strip()
            elif '- 角色:' in line or '- Role:' in line:
                profile.role = line.split(':', 1)[1].strip()
            elif '- 时区:' in line or '- Timezone:' in line:
                profile.timezone = line.split(':', 1)[1].strip()
            elif '- 语言偏好:' in line or '- Language:' in line:
                profile.language = line.split(':', 1)[1].strip()
        
        elif current_section == 'interests':
            if line and not line.startswith('#'):
                interests.append(line)
        
        elif current_section == 'communication preferences':
            if '- 回复风格:' in line or '- Reply style:' in line:
                preferences.reply_style = line.split(':', 1)[1].strip()
            elif '- 技术深度:' in line or '- Technical depth:' in line:
                preferences.technical_depth = line.split(':', 1)[1].strip()
            elif '- 反馈方式:' in line or '- Feedback style:' in line:
                preferences.feedback_style = line.split(':', 1)[1].strip()
    
    return User(
        profile=profile,
        interests=interests,
        preferences=preferences
    )
