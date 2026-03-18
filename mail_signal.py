#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票信号邮件推送
配置SMTP发送邮件
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import json
import os

CONFIG_FILE = os.path.expanduser('~/.stock_mail_config.json')
LOCAL_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mail_config.json')


def load_config():
    """加载配置"""
    # 先检查本地配置
    if os.path.exists(LOCAL_CONFIG):
        with open(LOCAL_CONFIG, 'r') as f:
            return json.load(f)
    # 再检查用户目录
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None


def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"配置已保存到 {CONFIG_FILE}")


def setup_mail():
    """交互式配置邮箱"""
    print("\n📧 邮件配置向导")
    print("="*40)
    
    config = {}
    
    # 发件人
    config['smtp_server'] = input("SMTP服务器 (如 smtp.gmail.com 或 smtp.qq.com): ").strip()
    config['smtp_port'] = int(input("SMTP端口 (465或587): ").strip())
    config['sender'] = input("发件人邮箱: ").strip()
    config['password'] = input("应用专用密码/授权码: ").strip()  # 不显示
    
    # 收件人
    config['receiver'] = input("收件人邮箱: ").strip()
    
    # 是否使用TLS
    config['use_tls'] = config['smtp_port'] == 587
    
    save_config(config)
    print("\n✅ 配置完成！")
    return config


def send_mail(subject, content, config=None):
    """发送邮件"""
    if config is None:
        config = load_config()
    
    if config is None:
        print("❌ 请先配置邮件: python3 mail_signal.py --setup")
        return False
    
    # 构建邮件
    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = config['sender']
    msg['To'] = config['receiver']
    
    # HTML内容
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #333;">📈 股票信号推送</h2>
        {content}
        <hr>
        <p style="color: #888; font-size: 12px;">由自动交易系统发送</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    try:
        # 连接SMTP
        if config['smtp_port'] == 465:
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            if config.get('use_tls', True):
                server.starttls()
        
        server.login(config['sender'], config['password'])
        server.sendmail(config['sender'], config['receiver'], msg.as_string())
        server.quit()
        
        print("✅ 邮件发送成功!")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


def send_stock_signal(signals):
    """发送股票信号"""
    # 构建表格
    rows = ""
    for s in signals:
        rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{s['symbol']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;"><b>{s['score']}</b></td>
            <td style="padding: 8px; border: 1pxpx solid #ddd;">{s['price']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{', '.join(s['signals'])}</td>
        </tr>
        """
    
    content = f"""
    <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
        <tr style="background: #4CAF50; color: white;">
            <th style="padding: 10px; text-align: left;">代码</th>
            <th style="padding: 10px; text-align: left;">得分</th>
            <th style="padding: 10px; text-align: left;">价格</th>
            <th style="padding: 10px; text-align: left;">信号</th>
        </tr>
        {rows}
    </table>
    <p style="margin-top: 20px;">
        <b>策略说明:</b><br>
        多头排列 +3分 | 资金连续流入 +3分 | 收阳 +1分<br>
        <span style="color: red;">≥6分为强势信号</span>
    </p>
    """
    
    send_mail("📈 股票信号 V4 - 每日推送", content)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--setup':
        setup_mail()
    else:
        # 测试发送
        test_signals = [
            {'symbol': '600188', 'score': 7, 'price': '17.72', 'signals': ['多头', '资金', '阳']},
            {'symbol': '600971', 'score': 7, 'price': '7.29', 'signals': ['多头', '资金', '阳']},
        ]
        send_stock_signal(test_signals)
