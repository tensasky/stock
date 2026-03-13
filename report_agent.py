# 报告Agent - 生成报告/邮件通知
# 功能: 生成各类报告、发送邮件通知

import sqlite3
import json
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os

DB_PATH = 'data/stocks.db'
POSITION_FILE = 'data/positions.json'
TRADE_LOG_FILE = 'data/trade_log.json'
MAIL_CONFIG = 'mail_config.json'


class ReportAgent:
    """报告Agent - 生成报告/发送邮件"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.mail_config = self.load_mail_config()
    
    def load_mail_config(self):
        """加载邮件配置"""
        if os.path.exists(MAIL_CONFIG):
            with open(MAIL_CONFIG, 'r') as f:
                return json.load(f)
        return {}
    
    def get_positions(self):
        """获取持仓"""
        if os.path.exists(POSITION_FILE):
            with open(POSITION_FILE, 'r') as f:
                return json.load(f)
        return []
    
    def get_trade_log(self):
        """获取交易日志"""
        if os.path.exists(TRADE_LOG_FILE):
            with open(TRADE_LOG_FILE, 'r') as f:
                return json.load(f)
        return []
    
    def get_price(self, code):
        """获取价格"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            f"SELECT close, change_pct FROM daily_data WHERE code = '{code}' ORDER BY date DESC LIMIT 1",
            conn
        )
        conn.close()
        if not df.empty:
            return {'price': df.iloc[0]['close'], 'change_pct': df.iloc[0]['change_pct']}
        return None
    
    def get_name(self, code):
        """获取股票名称"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(f"SELECT name FROM stocks WHERE code = '{code}'", conn)
        conn.close()
        return df.iloc[0]['name'] if not df.empty else code
    
    def generate_text_report(self):
        """生成文本报告"""
        positions = self.get_positions()
        trade_log = self.get_trade_log()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""📊 白板红中量化系统报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 生成时间: {now}

📈 持仓情况 ({len(positions)}只)
"""
        
        if positions:
            total_value = 0
            total_cost = 0
            
            report += f"{'代码':<8} {'名称':<10} {'股数':>8} {'成本':>10} {'现价':>10} {'盈亏':>12} {'盈亏%':>10}\n"
            report += "-" * 70 + "\n"
            
            for pos in positions:
                price_data = self.get_price(pos['code'])
                if price_data:
                    price = price_data['price']
                    cost = pos['entry_price'] * pos['shares']
                    value = price * pos['shares']
                    pnl = value - cost
                    pnl_pct = pnl / cost * 100
                    
                    total_value += value
                    total_cost += cost
                    
                    report += f"{pos['code']:<8} {pos['name']:<10} {pos['shares']:>8} "
                    report += f"¥{pos['entry_price']:>9.2f} ¥{price:>9.2f} "
                    report += f"¥{pnl:>+11.2f} {pnl_pct:>+9.2f}%\n"
            
            total_pnl = total_value - total_cost
            total_pnl_pct = total_pnl / total_cost * 100 if total_cost > 0 else 0
            
            report += "-" * 70 + "\n"
            report += f"{'合计':<18} {'':<10} {'':<8} {'':<10} {'':<10} "
            report += f"¥{total_pnl:>+11.2f} {total_pnl_pct:>+9.2f}%\n"
        else:
            report += "  (无持仓)\n"
        
        # 今日操作
        today = datetime.now().strftime('%Y-%m-%d')
        today_trades = [t for t in trade_log if t['time'].startswith(today)]
        
        report += f"\n📜 今日操作 ({len(today_trades)}笔)\n"
        if today_trades:
            for t in today_trades:
                if t['action'] == 'BUY':
                    report += f"  🟢 买入 {t['code']} {t['name']} {t['shares']}股 @ ¥{t['price']:.2f}\n"
                else:
                    report += f"  🔴 卖出 {t['code']} {t['shares']}股 @ ¥{t['price']:.2f}, "
                    report += f"盈亏¥{t.get('pnl', 0):+,.0f}\n"
        else:
            report += "  (无操作)\n"
        
        # 最近信号
        report += f"\n💡 策略信号\n"
        report += f"  评分≥6分 | 止盈5% | 止损2% | 持有2天\n"
        
        report += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += f"🎨 白板 | 🀄 红中 | 策略:V6.2\n"
        
        return report
    
    def generate_html_report(self):
        """生成HTML报告"""
        positions = self.get_positions()
        
        html = f"""<html><body>
<h2>📊 白板红中量化系统 - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>

<h3>📈 当前持仓 ({len(positions)}只)</h3>
<table border='1' cellpadding='5'>
<tr><th>代码</th><th>名称</th><th>股数</th><th>成本</th><th>现价</th><th>盈亏</th><th>盈亏%</th></tr>
"""
        
        total_pnl = 0
        
        for pos in positions:
            price_data = self.get_price(pos['code'])
            if price_data:
                price = price_data['price']
                cost = pos['entry_price'] * pos['shares']
                value = price * pos['shares']
                pnl = value - cost
                pnl_pct = pnl / cost * 100
                total_pnl += pnl
                
                color = 'green' if pnl > 0 else 'red'
                html += f"<tr><td>{pos['code']}</td><td>{pos['name']}</td>"
                html += f"<td>{pos['shares']}</td><td>¥{pos['entry_price']:.2f}</td>"
                html += f"<td>¥{price:.2f}</td><td style='color:{color}'>¥{pnl:+,.0f}</td>"
                html += f"<td style='color:{color}'>{pnl_pct:+.2f}%</td></tr>\n"
        
        html += f"""</table>

<p>📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 白板 | 红中🀄 | 策略:V6.2</p>
</body></html>"""
        
        return html
    
    def send_email(self, subject, body):
        """发送邮件"""
        if not self.mail_config:
            print("❌ 未配置邮件")
            return False
        
        try:
            from email.header import Header
            
            msg = MIMEText(body, 'plain', 'utf-8')
            sender_name = self.mail_config.get('sender_name', '洪福齐天')
            msg['From'] = f"{Header(sender_name, 'utf-8').encode()} <{self.mail_config['from']}>"
            msg['To'] = ', '.join(self.mail_config['to'])
            msg['Subject'] = Header(f"白板红中喜讯 - {subject}", 'utf-8').encode()
            
            with smtplib.SMTP(self.mail_config['smtp'], self.mail_config['port']) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(self.mail_config['user'], self.mail_config['pass'])
                s.sendmail(self.mail_config['from'], self.mail_config['to'], msg.as_string())
            
            print(f"✅ 邮件已发送: {subject}")
            return True
        
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
            return False
    
    def daily_report(self, send_mail=True):
        """生成并发送日报"""
        report = self.generate_text_report()
        print(report)
        
        if send_mail and self.mail_config:
            self.send_email("每日报告", report)
        
        return report
    
    def signal_report(self, signals, send_mail=True):
        """生成信号报告"""
        report = f"""🚨 白板红中量化预警
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 符合买入条件 ({len(signals)}只):
"""
        
        for i, s in enumerate(signals[:10], 1):
            name = self.get_name(s['code'])
            report += f"""
{i}. {s['code']} {name}
   价格: ¥{s.get('price', 0):.2f} | 涨跌幅: {s.get('change_pct', 0):+.2f}%
   评分: {s['score']}分
   信号: {', '.join(s['signals'].keys())}
"""
        
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 策略: V6.2 | 评分≥6分 | 止盈5% | 止损2%
🎨 白板 | 🀄 红中
"""
        
        print(report)
        
        if send_mail and self.mail_config:
            self.send_email(f"预警({len(signals)}只)", report)
        
        return report


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='报告Agent - 报告生成')
    parser.add_argument('action', choices=['daily', 'signal', 'html'],
                        help='操作')
    parser.add_argument('--send', action='store_true', default=False, help='发送邮件')
    
    args = parser.parse_args()
    
    agent = ReportAgent()
    
    if args.action == 'daily':
        agent.daily_report(send_mail=args.send)
    elif args.action == 'html':
        print(agent.generate_html_report())
