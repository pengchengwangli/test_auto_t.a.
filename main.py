import html
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from threading import Thread
from queue import Queue
import requests
import bs4
import lxml

# 日志队列
log_queue = Queue()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0',
}


def log_message(message):
    """将日志写入队列"""
    log_queue.put(message)


def process_log():
    """实时从队列中获取日志并显示"""
    while not log_queue.empty():
        message = log_queue.get()
        log_area.insert(tk.END, message + "\n")
        log_area.see(tk.END)
    root.after(100, process_log)


def get_session(username, password):
    """登录并返回会话"""
    session = requests.session()
    data = {
        'terminateOldSession': 'true',
        'referrer': 'http://125.223.1.242/mapleta/login/login.do',
        'login': username,
        'password': password
    }
    response = session.post('http://125.223.1.242/mapleta/login/login.do', headers=headers, data=data)
    is_logged_in = "登录失败" not in response.text
    return session, is_logged_in


def get_user_info(session):
    """获取用户信息"""
    res = session.get("http://125.223.1.242/mapleta/#", headers=headers)
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    user_info_path = soup.find('div', {'id': 'global'}).find_all('a')[1].get('href')
    user_id = user_info_path.split('=')[-1]
    url = f"http://125.223.1.242/mapleta/useradmin/MyProfile.do?id={user_id}"
    res = session.get(url)
    soup = bs4.BeautifulSoup(res.text, 'lxml')

    user_info_table = soup.find('div', class_='sectionMain col-sm-9').find('table')
    user_info = {}
    for row in user_info_table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) == 2:
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            user_info[label] = value

    return user_info


def get_class_id(response):
    """获取课程ID"""
    class_id_list = []
    soup = bs4.BeautifulSoup(response.text, 'lxml')
    class_id = soup.find_all('td')
    for a_all in class_id:
        class_id_list.append(a_all.find('a').get('href'))
    return class_id_list

def get_test_id(session, class_id):
    """获取测试 ID 列表"""
    test_id_list = []
    url = f"http://125.223.1.242/mapleta/modules/ClassHomepage.do?cid={class_id}"
    res = session.get(url, headers=headers)
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    section_row = soup.find_all('td', class_='noBorder name')
    for i in section_row:
        a_all = i.find('a')
        if a_all:
            test_id = a_all.get('href').split('=')[-1]
            test_id_list.append(test_id)
    return test_id_list

def get_course_name(session, class_id):
    """判断课程是否为高数"""
    url = f"http://125.223.1.242/mapleta/modules/ClassHomepage.do?cid={class_id}"
    res = session.get(url)
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    class_name = soup.find('h1').get_text()
    is_math_course = "高等数学" in class_name
    return is_math_course, class_name

def do_question(session, headers, test_id, class_id):
    res = session.get(f"http://125.223.1.242/mapleta/modules/test.Test?testId={test_id}")
    flag = -1
    while True:
        print(f"-------------------------正在做Test ID :{test_id}的第{flag + 1}题-------------------------")
        soup = bs4.BeautifulSoup(res.text, 'lxml')
        index = int(soup.find('div', class_='sectionName col-sm-3').find('h3').get_text().split(' ')[-1]) - 1
        if index == flag:
            data = f'currPage=1&testId={test_id}&inAssignment=true&assignment_mode=Proctored&actionID=grade&goto=&noLoad=true&really-grade=true'
            res = session.post("http://125.223.1.242/mapleta/modules/unproctoredTest.QuestionSheet", headers=headers,
                               data=data)
            break

        flag = index
        data = {
            'currPage': index,
            'testId': test_id,
            'inAssignment': 'true',
            'assignment_mode': 'Proctored',
            'actionID': 'next',
            'goto': index,
            'cid': class_id
        }
        # print(f"-------------------------正在做{test_id}的第{index + 1}题-------------------------")
        log_message(f"-------------------------正在做{test_id}的第{index + 1}题-------------------------")
        q_type = soup.find('input', {'name': f'ans.{index}.type'})['value']
        select_list = []
        data[f'ans.{index}.type'] = q_type
        if (q_type == 'string'):
            ans_list = soup.find('table', class_='response multiCh multiChVertical').find_all('tr')
            for ans in ans_list:
                select_list.append(ans.get_text())
        else:
            q_length = soup.find('input', {'name': f'ans.{index}.length'})['value']
            data[f'ans.{index}.length'] = q_length
        res.close()
        time.sleep(0.03)
        ans_url = f"http://125.223.1.242/mapleta/modules/gradeProctoredTest.Login?currPage=1&testId={test_id}&actionID=viewdetails"
        ans_res = session.get(ans_url, headers=headers)
        soup_ans = bs4.BeautifulSoup(ans_res.text, 'lxml')
        q_listq = soup_ans.find_all('div', class_='questionstyle')
        if len(q_listq) == 0:
            log_message(f"Test ID: {test_id} 为计分测试，跳过")
            data = f'currPage=1&testId={test_id}&inAssignment=true&assignment_mode=Proctored&actionID=grade&goto=&noLoad=true&really-grade=true'
            res = session.post("http://125.223.1.242/mapleta/modules/unproctoredTest.QuestionSheet", headers=headers,
                               data=data)
            res.close()
            break
        ans = q_listq[index].find_all('table')[1].find_all('tr')[1].find_all('td')[1]
        if q_type == 'string':
            try:
                data[f'ans.{index}.value'] = select_list.index(ans.get_text())
            except:
                data[f'ans.{index}.value'] = 1
        else:
            data[f'ans.{index}.0.type'] = 'list'
            data[f'ans.{index}.0.length'] = 1
            data[f'ans.{index}.0.0'] = html.unescape(ans.get_text())

        headers['Referer'] = 'http://125.223.1.242/mapleta/modules/unproctoredTest.QuestionSheet'
        res = session.post('http://125.223.1.242/mapleta/modules/unproctoredTest.QuestionSheet',
                      headers=headers, data=data)


def login_and_start():
    """主任务逻辑"""
    username = entry_username.get()
    password = entry_password.get()

    if not username or not password:
        messagebox.showwarning("输入错误", "请输入学号和密码")
        return

    log_message("尝试登录中...")
    session, is_logged_in = get_session(username, password)
    if not is_logged_in:
        log_message("登录失败，请检查学号和密码")
        return

    log_message("登录成功！正在获取用户信息...")
    user_info = get_user_info(session)
    display_user_info(user_info)

    log_message("获取课程列表中...")
    class_id_list = get_class_id(session.get("http://125.223.1.242/mapleta/#", headers=headers))
    for class_id in class_id_list:
        log_message(f"获取课程 ID: {class_id}")
        is_high_math, class_name = get_course_name(session, class_id)
        if not is_high_math:
            log_message(f"课程 {class_name} 不是高数课程，跳过")
            continue

        log_message(f"课程 {class_name} 是高数课程，获取测试 ID...")
        test_id_list = get_test_id(session, class_id)
        for test_id in test_id_list:
            do_question(session, headers, test_id, class_id)

    log_message("所有任务已完成！")


def display_user_info(user_info):
    """在界面上显示用户信息"""
    user_info_text.configure(state="normal")
    user_info_text.delete("1.0", tk.END)
    for label, value in user_info.items():
        user_info_text.insert(tk.END, f"{label}: {value}\n")
    user_info_text.configure(state="disabled")


def start_task():
    """启动后台任务线程"""
    Thread(target=login_and_start, daemon=True).start()


# 创建主窗口
root = tk.Tk()
root.title("自动答题工具")
root.geometry("800x600")
root.resizable(False, False)

# 样式美化
style = ttk.Style()
style.theme_use("clam")

# 主容器
frame_main = ttk.Frame(root, padding=(10, 10))
frame_main.pack(fill="both", expand=True)

# 左侧用户登录区域
frame_inputs = ttk.LabelFrame(frame_main, text="用户登录", padding=(10, 10))
frame_inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

ttk.Label(frame_inputs, text="学号:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entry_username = ttk.Entry(frame_inputs, width=30)
entry_username.grid(row=0, column=1, padx=5, pady=5, sticky="w")

ttk.Label(frame_inputs, text="密码:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_password = ttk.Entry(frame_inputs, show="*", width=30)
entry_password.grid(row=1, column=1, padx=5, pady=5, sticky="w")

btn_login = ttk.Button(frame_inputs, text="登录并开始任务", command=start_task)
btn_login.grid(row=2, column=0, columnspan=2, pady=10)

# 右侧用户信息区域
frame_user_info = ttk.LabelFrame(frame_main, text="当前用户信息", padding=(10, 10))
frame_user_info.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

user_info_text = scrolledtext.ScrolledText(frame_user_info, height=8, state="disabled", wrap="word")
user_info_text.pack(fill="both", expand=True)

# 日志显示区域
frame_logs = ttk.LabelFrame(root, text="日志", padding=(10, 10))
frame_logs.pack(fill="both", expand=True, pady=(10, 0))

log_area = scrolledtext.ScrolledText(frame_logs, width=80, height=15, state="normal", wrap="word")
log_area.pack(fill="both", expand=True)

# 定时器处理日志
root.after(100, process_log)

# 运行主循环
root.mainloop()
