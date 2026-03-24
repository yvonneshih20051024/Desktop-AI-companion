import sys, json, threading, time, requests, os, base64, math
import pyautogui
from io import BytesIO
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QTextEdit,
    QLineEdit, QMenu, QDialog, QDateTimeEdit, QPushButton,
    QHBoxLayout, QListWidget, QListWidgetItem, QGraphicsDropShadowEffect
)

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QDateTime
from PyQt6.QtGui import QPixmap, QAction


API_KEY = "sk-0d518a538e73487396e0a94107cfba2b"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(BASE_DIR, "schedules.json")


class PetSignals(QObject):
    update_text = pyqtSignal(str)
    change_mouth = pyqtSignal(bool)


# ================= 添加日程窗口 =================

class AddScheduleDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("添加日程")
        self.setFixedSize(300, 160)

        layout = QVBoxLayout()

        self.time_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.time_edit.setCalendarPopup(True)

        self.task_edit = QLineEdit()
        self.task_edit.setPlaceholderText("输入任务")

        btn_layout = QHBoxLayout()

        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")

        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addWidget(self.time_edit)
        layout.addWidget(self.task_edit)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def get_data(self):
        return self.time_edit.dateTime().toString("yyyy-MM-dd HH:mm"), self.task_edit.text()


# ================= 日程管理窗口 =================

class ScheduleManagerDialog(QDialog):

    def __init__(self, schedules, parent=None):
        super().__init__(parent)

        self.setWindowTitle("日程管理")
        self.setFixedSize(400, 300)

        self.schedules = schedules

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.load_items()

        # 双击编辑
        self.list_widget.itemDoubleClicked.connect(self.edit_schedule)

        btn_layout = QHBoxLayout()

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self.remove_selected)

        close_btn = QPushButton("完成")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(del_btn)
        btn_layout.addWidget(close_btn)

        layout.addWidget(self.list_widget)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_items(self):

        self.list_widget.clear()

        for item in self.schedules:
            text = f"{item['time']} | {item['task']}"
            self.list_widget.addItem(QListWidgetItem(text))

    # ================= 双击编辑 =================

    def edit_schedule(self, item):

        row = self.list_widget.row(item)

        text = item.text()

        t, task = text.split("|", 1)

        dialog = AddScheduleDialog(self)

        # 预填充时间
        dt = QDateTime.fromString(t.strip(), "yyyy-MM-dd HH:mm")
        dialog.time_edit.setDateTime(dt)

        dialog.task_edit.setText(task.strip())

        if dialog.exec():

            new_time, new_task = dialog.get_data()

            item.setText(f"{new_time} | {new_task}")

            self.schedules[row] = {
                "time": new_time,
                "task": new_task
            }

    # ================= 删除 =================

    def remove_selected(self):

        current_item = self.list_widget.currentItem()

        if current_item:
            row = self.list_widget.row(current_item)

            self.list_widget.takeItem(row)

            self.schedules.pop(row)

    def get_updated_schedules(self):

        new_schedules = []

        for i in range(self.list_widget.count()):

            text = self.list_widget.item(i).text()

            if "|" in text:
                t, task = text.split("|", 1)

                new_schedules.append({
                    "time": t.strip(),
                    "task": task.strip()
                })

        return new_schedules
# ================= 桌宠 =================

class DesktopPet(QWidget):

    def __init__(self):
        super().__init__()

        self.m_flag = False
        self.m_Position = None

        self.schedules = self.load_schedules()
        self.reminded_tasks=set()

        self.signals=PetSignals()

        self.signals.update_text.connect(self.display_message)
        self.signals.change_mouth.connect(self.set_mouth_state)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint|
            Qt.WindowType.WindowStaysOnTopHint|
            Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.scale_factor=1.0

        self.base_width=200
        self.base_height=200

        self.raw_pixmap_normal=QPixmap(os.path.join(BASE_DIR,"normal1.png"))
        self.raw_pixmap_talk=QPixmap(os.path.join(BASE_DIR,"normal2.png"))

        self.label=QLabel(self)

        self.text_display=QTextEdit(self)
        self.text_display.setReadOnly(True)
        self.text_display.setFixedHeight(60)

        self.input_box=QLineEdit(self)
        self.input_box.setPlaceholderText("和我说点什么吧...")
        self.input_box.returnPressed.connect(self.handle_input)

        layout=QVBoxLayout()

        layout.addWidget(self.label)
        layout.addWidget(self.text_display)
        layout.addWidget(self.input_box)

        self.setLayout(layout)

        self.update_scaling()

        self.float_offset=0

        self.float_timer=QTimer()
        self.float_timer.timeout.connect(self.float_animation)
        self.float_timer.start(200)

        self.check_timer=QTimer()
        self.check_timer.timeout.connect(self.scan_schedules)
        self.check_timer.start(30000)

    # ================= 浮动 =================

    def float_animation(self):

        self.float_offset+=0.3

        y=int(4*math.sin(self.float_offset))

        self.label.move(self.label.x(),10+y)

    # ================= 缩放 =================

    def wheelEvent(self,event):

        if event.angleDelta().y()>0:
            self.scale_factor+=0.1
        else:
            self.scale_factor-=0.1

        self.scale_factor=max(0.4,min(self.scale_factor,3))

        self.update_scaling()

    def update_scaling(self):

        new_w=int(self.base_width*self.scale_factor)
        new_h=int(self.base_height*self.scale_factor)

        self.pixmap_normal=self.raw_pixmap_normal.scaled(
            new_w,new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.pixmap_talk=self.raw_pixmap_talk.scaled(
            new_w,new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.label.setPixmap(self.pixmap_normal)

        self.label.setFixedSize(new_w,new_h)

        self.setFixedWidth(new_w+20)

        self.adjustSize()

    # ================= AI =================

    def handle_input(self):

        text=self.input_box.text().strip()

        self.input_box.clear()

        if not text:
            return

        threading.Thread(target=self.ai_chat_flow,args=(text,),daemon=True).start()

    def ai_chat_flow(self, user_text):
        # 1. 动态加载 system_prompt，默认值为“你是可爱的桌宠”
        system_content = "你是可爱的桌宠"
        config_path = os.path.join(BASE_DIR, "oc.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # 假设你的 oc.json 格式为 {"system_prompt": "你的设定..."}
                    system_content = config.get("system_prompt", system_content)
            except Exception as e:
                print(f"读取配置失败: {e}")

        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "qwen-turbo",
            "input": {
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_text}
                ]
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            res = response.json()
            
            # 调试：如果有问题，可以在控制台看到返回内容
            if response.status_code != 200:
                print(f"API Error: {res}")
                ai_text = "服务器似乎发生了问题..."
            else:
                # 兼容性解析：尝试获取 output.text
                output = res.get('output', {})
                ai_text = output.get('text', "......")
                
        except Exception as e:
            print(f"Network Error: {e}")
            ai_text = "连接似乎发生了问题..."

        # 触发打字机效果，将 AI 的回复显示在桌宠 UI 上
        self.typewriter_effect(ai_text)

    # ================= 打字机 =================

    def typewriter_effect(self,text):

        self.signals.change_mouth.emit(True)

        displayed=""

        for c in text:

            displayed+=c

            self.signals.update_text.emit(displayed)

            time.sleep(0.03)

        self.signals.change_mouth.emit(False)

    # ================= UI =================

    def set_mouth_state(self,talking):

        self.label.setPixmap(self.pixmap_talk if talking else self.pixmap_normal)

    def display_message(self,text):

        self.text_display.setText(text)

    # ================= 日程 =================

    def load_schedules(self):

        if os.path.exists(SCHEDULE_FILE):

            try:
                with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []

        return []

    def save_schedules(self):

        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.schedules, f, ensure_ascii=False, indent=4)

    def scan_schedules(self):

        now = datetime.now()

        for item in self.schedules:

            try:

                task_time = datetime.strptime(item['time'], "%Y-%m-%d %H:%M")
                reminder_time = task_time - timedelta(minutes=10)

                task_id = item['time'] + item['task']

                if now >= reminder_time and task_id not in self.reminded_tasks:

                    self.reminded_tasks.add(task_id)

                    msg = f"朋友，{item['task']} 10分钟后就要开始了"

                    threading.Thread(
                        target=self.typewriter_effect,
                        args=(msg,),
                        daemon=True
                    ).start()

            except:
                continue

    # ================= 日程菜单 =================

    def open_add_schedule_dialog(self):

        dialog = AddScheduleDialog(self)

        if dialog.exec():

            t, task = dialog.get_data()

            if task:

                self.schedules.append({
                    "time": t,
                    "task": task
                })

                self.save_schedules()

                self.typewriter_effect(f"好的，我记住了 {task}")

    def open_manage_schedules(self):

        dialog = ScheduleManagerDialog(self.schedules, self)

        if dialog.exec():

            self.schedules = dialog.get_updated_schedules()

            self.save_schedules()

    def clear_old_schedules(self):

        now = datetime.now()

        self.schedules = [
            s for s in self.schedules
            if datetime.strptime(s['time'], "%Y-%m-%d %H:%M") > now
        ]

        self.save_schedules()
        self.typewriter_effect("已经清理掉过期日程了。")

    # ================= 右键菜单 =================

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        scan_action = QAction("识别桌面", self)
        scan_action.triggered.connect(
            lambda: threading.Thread(
                target=self.capture_and_analyze,
                daemon=True
            ).start()
        )

        add_action = QAction("添加日程", self)
        add_action.triggered.connect(self.open_add_schedule_dialog)

        manage_action = QAction("管理日程", self)
        manage_action.triggered.connect(self.open_manage_schedules)

        clear_action = QAction("清理过期日程", self)
        clear_action.triggered.connect(self.clear_old_schedules)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)

        menu.addAction(scan_action)
        menu.addAction(add_action)
        menu.addAction(manage_action)
        menu.addAction(clear_action)

        menu.addSeparator()
        menu.addAction(exit_action)

        menu.exec(event.globalPos())
    
 # ================= 拖动 =================

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.m_flag = True
            # 记录相对窗口的坐标，用于平滑拖拽
            self.m_Position = event.globalPosition().toPoint() - self.pos()
            # 记录起始位置，用于松开时判断是“点击”还是“拖动”
            self.mouse_start_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        # 如果左键按住且在移动，则搬动窗体
        if Qt.MouseButton.LeftButton and self.m_flag:
            self.move(event.globalPosition().toPoint() - self.m_Position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 计算鼠标抬起时与按下时的位移距离
            curr_pos = event.globalPosition().toPoint()
            dis = (curr_pos - self.mouse_start_pos).manhattanLength()

            # 如果位移距离很小（小于5像素），说明用户只是点了一下，不是想拖走它
            if dis < 5:
                self.toggle_ui()
            
            self.m_flag = False
            event.accept()

 # ================= 桌面识别 =================

    def capture_and_analyze(self):

        self.signals.update_text.emit("......")

        try:

            screenshot=pyautogui.screenshot()

            buffer=BytesIO()

            screenshot.save(buffer,format="JPEG")

            img_b64=base64.b64encode(buffer.getvalue()).decode()

            url="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

            headers={
                "Authorization":f"Bearer {API_KEY}",
                "Content-Type":"application/json"
            }

            payload={
                "model":"qwen-vl-max",
                "input":{
                    "messages":[
                        {
                            "role":"user",
                            "content":[
                                {"image":f"data:image/jpeg;base64,{img_b64}"},
                                {"text":"观察截图并简短评论"}
                            ]
                        }
                    ]
                }
            }

            res=requests.post(url,headers=headers,json=payload).json()

            comment=res['output']['choices'][0]['message']['content'][0]['text']

        except:

            comment="我看不清..."

        self.typewriter_effect(comment)

#------------------ 隐藏 -----------------
    def toggle_ui(self):
        # 1. 切换显示/隐藏状态
        is_visible = not self.input_box.isVisible()
        
        # 2. 统一设置控件可见性
        self.input_box.setVisible(is_visible)
        self.text_display.setVisible(is_visible)
        
        if not is_visible:
            # 隐藏模式：强制固定为宠物图片的高度（加上布局内边距）
            # 这里的 20 是因为 setContentsMargins(10,10,10,10) 上下边距之和
            self.setFixedHeight(self.label.height() + 20)
        else:
            # 显示模式：解除高度固定，允许窗口根据内容自适应
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215) # QWIDGETSIZE_MAX
            self.adjustSize()
            
        # 保持宽度一致，防止左右晃动
        self.setFixedWidth(self.label.width() + 20)

if __name__=="__main__":

    app=QApplication(sys.argv)

    pet=DesktopPet()

    pet.show()

    sys.exit(app.exec())