from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

#等TimerService发来POST
@app.route('/notify', methods=['POST'])
def receive_notification():
    #提取服务器发来的JSON数据
    data = request.json
    
    #模拟设备收到通知
    print("\n" + "="*40)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔔 叮！收到云端定时器通知！")
    print(f"接收到的核心数据: {data}")
    print("="*40 + "\n")
    
    return "Received successfully", 200

if __name__ == '__main__':
    print("🚀 模拟客户端设备已启动...")
    print("👉 你的设备回调地址是: http://127.0.0.1:8080/notify")
    app.run(port=8080, debug=False)