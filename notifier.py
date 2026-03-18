#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - 消息推送模块
支持 Discord 和 邮件，带重试机制
"""

import smtplib
import time
import random
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class MessageConfig:
    """消息配置"""
    # Discord配置
    discord_webhook: str = ""
    discord_channel_id: str = ""
    
    # 邮件配置
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: List[str] = None
    
    def __post_init__(self):
        if self.email_to is None:
            self.email_to = []


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def execute(self, func, *args, **kwargs):
        """执行带重试的任务"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"执行失败 (尝试 {attempt+1}/{self.max_retries}), 等待 {delay:.1f}s: {e}")
                time.sleep(delay)
        
        logger.error(f"执行失败 {self.max_retries} 次: {last_error}")
        return False


class DiscordNotifier:
    """Discord 消息推送"""
    
    def __init__(self, webhook_url: str = "", channel_id: str = ""):
        self.webhook_url = webhook_url or "https://discord.com/api/webhooks/placeholder"
        self.channel_id = channel_id
        self.retry = RetryHandler(max_retries=3, base_delay=2.0)
    
    def _send_webhook(self, payload: Dict) -> bool:
        """发送Webhook请求"""
        import requests
        
        response = requests.post(
            self.webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        return True
    
    def send(self, content: str, embed: Optional[Dict] = None) -> bool:
        """发送消息"""
        if not self.webhook_url or "placeholder" in self.webhook_url:
            logger.warning("Discord webhook 未配置")
            return False
        
        payload = {'content': content}
        if embed:
            payload['embeds'] = [embed]
        
        def _send():
            return self._send_webhook(payload)
        
        result = self.retry.execute(_send)
        
        if result:
            logger.info(f"Discord 消息发送成功: {content[:50]}...")
        else:
            logger.error(f"Discord 消息发送失败")
        
        return result or False
    
    def send_signal_alert(self, stock: str, signal_type: str, price: float, 
                         details: str, score: int) -> bool:
        """发送信号预警"""
        # 颜色根据分数变化
        if score >= 3:
            color = 0x00FF00  # 绿色 - 强烈买入
        elif score >= 1:
            color = 0xFFFF00  # 黄色 - 温和信号
        else:
            color = 0xFF0000  # 红色 - 卖出信号
        
        embed = {
            'title': f"📈 信号预警 - {stock}",
            'color': color,
            'fields': [
                {'name': '信号类型', 'value': signal_type, 'inline': True},
                {'name': '当前价格', 'value': f'¥{price:.2f}', 'inline': True},
                {'name': '信号得分', 'value': str(score), 'inline': True},
                {'name': '详情', 'value': details[:500]}
            ],
            'footer': {'text': '股票分析系统'},
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        return self.send(f"🚨 发现交易信号: {stock}", embed)
    
    def send_trade_alert(self, stock: str, action: str, price: float, 
                        reason: str, position_size: float = 0) -> bool:
        """发送交易提醒"""
        action_emoji = "🟢 买入" if action == "BUY" else "🔴 卖出"
        
        embed = {
            'title': f"{action_emoji} 交易执行",
            'color': 0x00FF00 if action == "BUY" else 0xFF0000,
            'fields': [
                {'name': '股票', 'value': stock, 'inline': True},
                {'name': '价格', 'value': f'¥{price:.2f}', 'inline': True},
                {'name': '仓位', 'value': f'{position_size*100:.1f}%', 'inline': True},
                {'name': '买入理由', 'value': reason[:500]}
            ],
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        return self.send(f"{action_emoji} {stock} @ ¥{price:.2f}", embed)


class EmailNotifier:
    """邮件推送"""
    
    def __init__(self, config: MessageConfig):
        self.config = config
        self.retry = RetryHandler(max_retries=3, base_delay=2.0)
    
    def _send_email(self, subject: str, body: str, html: bool = False) -> bool:
        """发送邮件"""
        if not self.config.smtp_user or not self.config.email_to:
            logger.warning("邮件配置不完整")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.config.email_from or self.config.smtp_user
        msg['To'] = ', '.join(self.config.email_to)
        
        if html:
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            server.starttls()
            server.login(self.config.smtp_user, self.config.smtp_password)
            server.send_message(msg)
        
        return True
    
    def send(self, subject: str, body: str, html: bool = False) -> bool:
        """发送邮件（带重试）"""
        def _send():
            return self._send_email(subject, body, html)
        
        result = self.retry.execute(_send)
        
        if result:
            logger.info(f"邮件发送成功: {subject}")
        else:
            logger.error(f"邮件发送失败: {subject}")
        
        return result or False
    
    def send_signal_alert(self, stock: str, signal_type: str, price: float,
                         details: str, score: int) -> bool:
        """发送信号预警邮件"""
        subject = f"【股票信号】{stock} - {signal_type}"
        
        body = f"""
股票: {stock}
信号类型: {signal_type}
当前价格: ¥{price:.2f}
信号得分: {score}

{details}

---
股票分析系统自动发送
        """
        
        return self.send(subject, body)
    
    def send_trade_alert(self, stock: str, action: str, price: float,
                        reason: str, position_size: float = 0) -> bool:
        """发送交易邮件"""
        action_text = "买入" if action == "BUY" else "卖出"
        subject = f"【交易执行】{stock} - {action_text} @ ¥{price:.2f}"
        
        body = f"""
股票: {stock}
操作: {action_text}
价格: ¥{price:.2f}
仓位: {position_size*100:.1f}%

理由:
{reason}

---
股票分析系统自动发送
        """
        
        return self.send(subject, body)


class NotificationManager:
    """统一通知管理器"""
    
    def __init__(self, config: MessageConfig):
        self.config = config
        self.discord = DiscordNotifier(
            webhook_url=config.discord_webhook,
            channel_id=config.discord_channel_id
        )
        self.email = EmailNotifier(config)
        self.enabled_channels = []
        
        if config.discord_webhook and "placeholder" not in config.discord_webhook:
            self.enabled_channels.append('discord')
        
        if config.smtp_user and config.email_to:
            self.enabled_channels.append('email')
        
        logger.info(f"通知管理器初始化，启用渠道: {self.enabled_channels}")
    
    def notify_signal(self, stock: str, signal_type: str, price: float,
                     details: str, score: int) -> Dict[str, bool]:
        """发送信号通知"""
        results = {}
        
        for channel in self.enabled_channels:
            if channel == 'discord':
                results['discord'] = self.discord.send_signal_alert(
                    stock, signal_type, price, details, score
                )
            elif channel == 'email':
                results['email'] = self.email.send_signal_alert(
                    stock, signal_type, price, details, score
                )
        
        return results
    
    def notify_trade(self, stock: str, action: str, price: float,
                    reason: str, position_size: float = 0) -> Dict[str, bool]:
        """发送交易通知"""
        results = {}
        
        for channel in self.enabled_channels:
            if channel == 'discord':
                results['discord'] = self.discord.send_trade_alert(
                    stock, action, price, reason, position_size
                )
            elif channel == 'email':
                results['email'] = self.email.send_trade_alert(
                    stock, action, price, reason, position_size
                )
        
        return results
    
    def notify(self, message: str, title: str = "") -> Dict[str, bool]:
        """通用通知"""
        results = {}
        
        for channel in self.enabled_channels:
            if channel == 'discord':
                results['discord'] = self.discord.send(message)
            elif channel == 'email':
                results['email'] = self.email.send(title or message, message)
        
        return results


def load_config(config_path: str = "config.json") -> MessageConfig:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return MessageConfig(
            discord_webhook=data.get('discord_webhook', ''),
            discord_channel_id=data.get('discord_channel_id', ''),
            smtp_host=data.get('smtp_host', ''),
            smtp_port=data.get('smtp_port', 587),
            smtp_user=data.get('smtp_user', ''),
            smtp_password=data.get('smtp_password', ''),
            email_from=data.get('email_from', ''),
            email_to=data.get('email_to', [])
        )
    except FileNotFoundError:
        logger.warning(f"配置文件 {config_path} 不存在，使用默认配置")
        return MessageConfig()


def test_notifier():
    """测试通知功能"""
    # 加载配置
    config = load_config()
    
    # 创建通知管理器
    notifier = NotificationManager(config)
    
    print(f"启用渠道: {notifier.enabled_channels}")
    
    # 测试发送
    if notifier.enabled_channels:
        print("\n发送测试信号...")
        results = notifier.notify_signal(
            stock="600519",
            signal_type="MACD金叉",
            price=1850.50,
            details="MACD金叉 + KDJ超卖 + 量价齐升",
            score=3
        )
        print(f"发送结果: {results}")
    else:
        print("未配置任何通知渠道，请先配置 config.json")


if __name__ == "__main__":
    test_notifier()
