"""
密码安全验证模块

提供：
- 密码强度验证（长度、复杂度、常见密码检查）
- 密码安全评分
- 密码生成建议
"""
import re
import hashlib
import os
from typing import Tuple, List

# 常见弱密码列表（可扩展）
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "123456789", "1234567890",
    "qwerty", "abc123", "password1", "admin", "admin123",
    "root", "root123", "letmein", "welcome", "monkey",
    "dragon", "master", "passw0rd", "password123", "iloveyou",
    "sunshine", "princess", "football", "baseball", "welcome1",
    "shadow", "superman", "qazwsx", "michael", "trustno1"
}

# 密码策略配置（可通过环境变量覆盖）
MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
MAX_LENGTH = int(os.getenv("PASSWORD_MAX_LENGTH", "128"))
REQUIRE_UPPERCASE = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
REQUIRE_LOWERCASE = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
CHECK_COMMON = os.getenv("PASSWORD_CHECK_COMMON", "true").lower() == "true"


def validate_password(password: str, username: str = None) -> Tuple[bool, List[str]]:
    """
    验证密码强度

    Args:
        password: 待验证密码
        username: 用户名（用于检查密码是否包含用户名）

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    # 长度检查
    if len(password) < MIN_LENGTH:
        errors.append(f"密码长度至少为 {MIN_LENGTH} 个字符")
    if len(password) > MAX_LENGTH:
        errors.append(f"密码长度不能超过 {MAX_LENGTH} 个字符")

    # 复杂度检查
    if REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        errors.append("密码必须包含至少一个大写字母")

    if REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        errors.append("密码必须包含至少一个小写字母")

    if REQUIRE_DIGIT and not re.search(r'\d', password):
        errors.append("密码必须包含至少一个数字")

    if REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password):
        errors.append("密码必须包含至少一个特殊字符 (!@#$%^&*等)")

    # 常见密码检查
    if CHECK_COMMON and password.lower() in COMMON_PASSWORDS:
        errors.append("密码过于常见，请使用更复杂的密码")

    # 用户名检查
    if username:
        username_lower = username.lower()
        password_lower = password.lower()
        if username_lower in password_lower:
            errors.append("密码不能包含用户名")
        if password_lower in username_lower:
            errors.append("密码不能是用户名的一部分")

    # 连续字符检查
    if has_sequential_chars(password, 4):
        errors.append("密码不能包含4个或以上连续字符（如 1234, abcd）")

    # 重复字符检查
    if has_repeated_chars(password, 4):
        errors.append("密码不能包含4个或以上重复字符（如 aaaa, 1111）")

    return len(errors) == 0, errors


def has_sequential_chars(password: str, length: int) -> bool:
    """检查是否包含连续字符"""
    password_lower = password.lower()

    # 检查连续数字
    for i in range(len(password_lower) - length + 1):
        substr = password_lower[i:i + length]
        if substr.isdigit():
            digits = [int(c) for c in substr]
            if all(digits[j + 1] - digits[j] == 1 for j in range(len(digits) - 1)):
                return True
            if all(digits[j] - digits[j + 1] == 1 for j in range(len(digits) - 1)):
                return True

    # 检查连续字母
    for i in range(len(password_lower) - length + 1):
        substr = password_lower[i:i + length]
        if substr.isalpha():
            ords = [ord(c) for c in substr]
            if all(ords[j + 1] - ords[j] == 1 for j in range(len(ords) - 1)):
                return True
            if all(ords[j] - ords[j + 1] == 1 for j in range(len(ords) - 1)):
                return True

    return False


def has_repeated_chars(password: str, length: int) -> bool:
    """检查是否包含重复字符"""
    for i in range(len(password) - length + 1):
        if len(set(password[i:i + length])) == 1:
            return True
    return False


def calculate_password_strength(password: str) -> Tuple[int, str]:
    """
    计算密码强度评分

    Returns:
        (score: 0-100, level: weak/medium/strong/very_strong)
    """
    score = 0

    # 长度评分 (最多 30 分)
    length = len(password)
    if length >= 8:
        score += 10
    if length >= 12:
        score += 10
    if length >= 16:
        score += 10

    # 字符类型评分 (最多 40 分)
    if re.search(r'[a-z]', password):
        score += 10
    if re.search(r'[A-Z]', password):
        score += 10
    if re.search(r'\d', password):
        score += 10
    if re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password):
        score += 10

    # 混合程度评分 (最多 20 分)
    char_types = sum([
        bool(re.search(r'[a-z]', password)),
        bool(re.search(r'[A-Z]', password)),
        bool(re.search(r'\d', password)),
        bool(re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password))
    ])
    if char_types >= 3:
        score += 10
    if char_types >= 4:
        score += 10

    # 扣分项
    if password.lower() in COMMON_PASSWORDS:
        score -= 30
    if has_sequential_chars(password, 4):
        score -= 10
    if has_repeated_chars(password, 4):
        score -= 10

    # 限制范围
    score = max(0, min(100, score))

    # 评级
    if score < 40:
        level = "weak"
    elif score < 60:
        level = "medium"
    elif score < 80:
        level = "strong"
    else:
        level = "very_strong"

    return score, level


def generate_password_hint() -> str:
    """生成密码建议提示"""
    requirements = []

    requirements.append(f"• 长度至少 {MIN_LENGTH} 个字符")

    if REQUIRE_UPPERCASE:
        requirements.append("• 包含大写字母 (A-Z)")
    if REQUIRE_LOWERCASE:
        requirements.append("• 包含小写字母 (a-z)")
    if REQUIRE_DIGIT:
        requirements.append("• 包含数字 (0-9)")
    if REQUIRE_SPECIAL:
        requirements.append("• 包含特殊字符 (!@#$%^&*等)")

    requirements.append("• 避免使用常见密码")
    requirements.append("• 避免连续或重复字符")

    return "\n".join(requirements)


def check_password_pwned(password: str) -> Tuple[bool, int]:
    """
    检查密码是否在已泄露密码库中（使用 Have I Been Pwned API 的 k-anonymity）

    Returns:
        (is_pwned, count) - 是否泄露，泄露次数
    """
    try:
        import requests

        # SHA1 哈希
        sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        # 查询 API
        response = requests.get(
            f'https://api.pwnedpasswords.com/range/{prefix}',
            timeout=5
        )

        if response.status_code == 200:
            for line in response.text.splitlines():
                hash_suffix, count = line.split(':')
                if hash_suffix == suffix:
                    return True, int(count)

        return False, 0

    except Exception:
        # API 调用失败不阻止登录，仅记录日志
        return False, 0
