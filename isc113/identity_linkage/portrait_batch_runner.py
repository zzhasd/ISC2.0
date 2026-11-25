#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""画像实验外部串行调度器；仅使用 Python 标准库，不导入原实验脚本。"""
from __future__ import annotations

import codecs
import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import random
import subprocess
import sys
import threading
import time
import uuid

SUBJECTS = tuple('''IK IH BK GM EH BC HT FP
IN GA IE HN HY
HQ BE FI HK EA EY HZ GQ
FJ GL DS GY FS FT GT HE
HA DB HB DM CS GD DD
EU GX ET DY AZ GW BJ
AL CK EV AS CN GU
FE CO BH BL CR BF EM BI AV DK AK CV CY GI AT'''.split())
TARGET_NAME = 'subject_one_portrait_tokenplan_v1.py'
HERE = Path(__file__).resolve().parent


def timestamp():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def elapsed_text(seconds):
    n = int(seconds)
    return f'{n // 3600:02d}:{n // 60 % 60:02d}:{n % 60:02d}'


def run_batch(target, subjects, root, stop, emit, delay_picker=None):
    """外部控制：逐个启动、读取合并输出、等待退出、记账，再随机等待。"""
    delay_picker = delay_picker or (lambda: random.randint(1, 30))
    root.mkdir(parents=True, exist_ok=False)
    status_path = root / 'status.csv'
    env = os.environ.copy()
    # 仅设置子进程输出方式；继承现有环境（包括 API 密钥），不读取或修改业务配置。
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    successes = failures = 0
    fields = ['index', 'subject', 'status', 'exit_code', 'started_at', 'finished_at',
              'elapsed_seconds', 'log_file', 'error']
    with status_path.open('w', encoding='utf-8-sig', newline='') as status_file:
        writer = csv.DictWriter(status_file, fieldnames=fields)
        writer.writeheader()
        status_file.flush()
        for index, subject in enumerate(subjects, 1):
            if stop.is_set():
                break
            cmd = [sys.executable, str(target), subject, '--retries', '3']
            log_path = root / f'{index:03d}_{subject}.log'
            start = timestamp()
            t0 = time.monotonic()
            code = None
            error = ''
            emit('status', subject, '运行中', '', '')
            emit('current', f'正在运行 {index}/{len(subjects)}：{subject}')
            header = f'\n===== [{index}/{len(subjects)}] {subject} | {start} =====\n命令：{subprocess.list2cmdline(cmd)}\n'
            emit('output', header)
            with log_path.open('wb') as log:
                log.write(header.encode('utf-8'))
                log.flush()
                proc = None
                try:
                    kwargs = {'cwd': str(target.parent), 'env': env, 'stdout': subprocess.PIPE,
                              'stderr': subprocess.STDOUT, 'stdin': subprocess.DEVNULL}
                    if os.name == 'nt':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    proc = subprocess.Popen(cmd, **kwargs)
                    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
                    # read1 即使没有换行也会及时返回；兼容 tqdm 的回车进度输出。
                    with proc.stdout as pipe:
                        while True:
                            data = pipe.read1(8192)
                            if not data:
                                break
                            log.write(data)
                            log.flush()
                            output = decoder.decode(data)
                            if output:
                                emit('output', output)
                    tail = decoder.decode(b'', final=True)
                    if tail:
                        emit('output', tail)
                    code = proc.wait()
                except Exception as exc:
                    error = f'{type(exc).__name__}: {exc}'
                    # 如果已经启动，务必等待它退出，绝不与下一个子进程重叠。
                    if proc is not None:
                        if proc.stdout is not None:
                            proc.stdout.close()
                        code = proc.wait()
                    msg = f'\n[调度器异常] {error}\n'
                    log.write(msg.encode('utf-8', errors='replace'))
                    emit('output', msg)
                duration = time.monotonic() - t0
                state = '成功' if code == 0 and not error else '失败'
                footer = f'\n===== {subject} {state} | 退出码={code} | 耗时={elapsed_text(duration)} =====\n'
                log.write(footer.encode('utf-8'))
                emit('output', footer)
            writer.writerow(dict(index=index, subject=subject, status=state,
                                 exit_code='' if code is None else code, started_at=start,
                                 finished_at=timestamp(), elapsed_seconds=round(duration, 2),
                                 log_file=log_path.name, error=error))
            status_file.flush()
            os.fsync(status_file.fileno())
            successes += state == '成功'
            failures += state == '失败'
            emit('status', subject, state, '—' if code is None else str(code), elapsed_text(duration))
            emit('counts', successes, failures)
            if index < len(subjects) and not stop.is_set():
                delay = delay_picker()
                emit('output', f'[调度器] 随机等待 {delay} 秒，下一个：{subjects[index]}\n')
                deadline = time.monotonic() + delay
                while not stop.is_set():
                    left = deadline - time.monotonic()
                    if left <= 0:
                        break
                    emit('current', f'等待 {int(left + .999)} 秒，下一个：{subjects[index]}')
                    stop.wait(min(left, 1))
    return successes, failures


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from tkinter.scrolledtext import ScrolledText

    window = tk.Tk()
    window.title('Portrait 批量运行调度器')
    window.geometry('1150x720')
    window.minsize(850, 500)
    events = queue.Queue()
    stop = threading.Event()
    running = False
    close_after = False
    results = {}
    log_dir = None
    default_target = HERE / TARGET_NAME
    uploaded_name = HERE / 'subject_one_portrait_tokenplan_v1(1).py'
    if not default_target.is_file() and uploaded_name.is_file():
        default_target = uploaded_name
    target_var = tk.StringVar(value=str(default_target))
    current_var = tk.StringVar(value='就绪；点击开始运行')
    count_var = tk.StringVar(value=f'总计 {len(SUBJECTS)} | 成功 0 | 失败 0 | 未完成 {len(SUBJECTS)}')
    path_var = tk.StringVar(value='日志目录：尚未创建')
    auto_scroll = tk.BooleanVar(value=True)

    outer = ttk.Frame(window, padding=12)
    outer.pack(fill='both', expand=True)
    outer.columnconfigure(1, weight=1)
    outer.rowconfigure(4, weight=1)
    ttk.Label(outer, text='原脚本：').grid(row=0, column=0, sticky='w')
    entry = ttk.Entry(outer, textvariable=target_var)
    entry.grid(row=0, column=1, sticky='ew', padx=6)

    def browse():
        path = filedialog.askopenfilename(initialdir=HERE, filetypes=[('Python 脚本', '*.py')])
        if path:
            target_var.set(path)

    browse_button = ttk.Button(outer, text='选择脚本', command=browse)
    browse_button.grid(row=0, column=2)
    toolbar = ttk.Frame(outer)
    toolbar.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(12, 6))
    start_button = ttk.Button(toolbar, text='开始运行')
    start_button.pack(side='left')
    stop_button = ttk.Button(toolbar, text='当前任务结束后停止', state='disabled')
    stop_button.pack(side='left', padx=8)
    log_button = ttk.Button(toolbar, text='打开日志目录', state='disabled')
    log_button.pack(side='left')
    ttk.Label(toolbar, textvariable=count_var).pack(side='right')
    progress = ttk.Progressbar(outer, maximum=len(SUBJECTS), mode='determinate')
    progress.grid(row=2, column=0, columnspan=3, sticky='ew', pady=4)
    ttk.Label(outer, textvariable=current_var).grid(row=3, column=0, columnspan=3, sticky='w', pady=(3, 8))
    panes = ttk.Panedwindow(outer, orient='horizontal')
    panes.grid(row=4, column=0, columnspan=3, sticky='nsew')
    left = ttk.Frame(panes, padding=(0, 0, 6, 0))
    right = ttk.Frame(panes)
    panes.add(left, weight=1)
    panes.add(right, weight=3)
    ttk.Label(left, text='任务队列（固定顺序）').pack(anchor='w', pady=(0, 6))
    table_frame = ttk.Frame(left)
    table_frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(table_frame, columns=('num', 'id', 'state', 'code', 'time'), show='headings')
    for col, label, width in [('num', '#', 38), ('id', 'ID', 45), ('state', '状态', 70),
                              ('code', '退出码', 55), ('time', '耗时', 75)]:
        tree.heading(col, text=label)
        tree.column(col, width=width, minwidth=32, anchor='center', stretch=col == 'state')
    scroll = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    for i, subject in enumerate(SUBJECTS, 1):
        tree.insert('', 'end', iid=subject, values=(i, subject, '等待中', '', ''))
    tree.tag_configure('成功', foreground='#16803c')
    tree.tag_configure('失败', foreground='#bd3030')
    tree.tag_configure('运行中', foreground='#1461ba')
    output_header = ttk.Frame(right)
    output_header.pack(fill='x', pady=(0, 6))
    ttk.Label(output_header, text='实时输出（stdout + stderr）').pack(side='left')
    ttk.Checkbutton(output_header, text='自动滚动', variable=auto_scroll).pack(side='right')
    output = ScrolledText(right, wrap='word', state='disabled', font='TkFixedFont')
    output.pack(fill='both', expand=True)
    ttk.Label(outer, textvariable=path_var, wraplength=1000).grid(row=5, column=0, columnspan=3, sticky='w', pady=(8, 0))

    def emit(*event):
        events.put(event)

    def append_output(text):
        # 将终端的回车进度刷新变成可阅读的独立行；完整原始字节在日志中。
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        output.configure(state='normal')
        output.insert('end', text)
        lines = int(output.index('end-1c').split('.')[0])
        if lines > 12000:
            output.delete('1.0', f'{lines - 10000}.0')
        # 也限制没有换行的超长输出，完整内容仍保存在日志中。
        chars = output.count('1.0', 'end-1c', 'chars')
        if chars and chars[0] > 1500000:
            output.delete('1.0', f'1.0 + {chars[0] - 1000000} chars')
        output.configure(state='disabled')
        if auto_scroll.get():
            output.see('end')

    def worker(target, pending, root):
        try:
            run_batch(target, pending, root, stop, emit)
        except Exception as exc:
            emit('fatal', f'{type(exc).__name__}: {exc}')
        finally:
            emit('finished')

    def start():
        nonlocal running, log_dir
        if running:
            return
        pending = tuple(s for s in SUBJECTS if s not in results)
        if not pending:
            return
        target = Path(target_var.get().strip()).expanduser().resolve()
        if not target.is_file() or target.suffix.lower() != '.py' or target == Path(__file__).resolve():
            messagebox.showerror('脚本路径错误', '请选择原始 subject_one_portrait_tokenplan_v1.py 文件。')
            return
        stop.clear()
        running = True
        start_button.configure(state='disabled')
        stop_button.configure(state='normal')
        entry.configure(state='disabled')
        browse_button.configure(state='disabled')
        log_dir = target.parent / 'portrait_batch_logs' / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6])
        path_var.set(f'日志目录：{log_dir}')
        log_button.configure(state='normal')
        current_var.set('准备启动…')
        append_output(f'\n[调度器] 本次运行 {len(pending)} 个任务。日志：{log_dir}\n')
        threading.Thread(target=worker, args=(target, pending, log_dir), daemon=True).start()

    def request_stop():
        stop.set()
        stop_button.configure(state='disabled')
        current_var.set('已请求停止：当前任务自然退出后，不再启动新任务')
        append_output('\n[调度器] 已请求在当前任务结束后停止。\n')

    def open_logs():
        if log_dir is None or not log_dir.is_dir():
            messagebox.showinfo('日志', '日志目录尚未创建。')
            return
        try:
            if os.name == 'nt':
                os.startfile(str(log_dir))
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(log_dir)])
        except OSError:
            messagebox.showinfo('日志目录', str(log_dir))

    def poll():
        nonlocal running
        chunks = []
        for _ in range(500):
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            kind, *args = event
            if kind == 'output':
                chunks.append(args[0])
                continue
            if chunks:
                append_output(''.join(chunks))
                chunks.clear()
            if kind == 'status':
                subject, state, code, duration = args
                tree.item(subject, values=(SUBJECTS.index(subject)+1, subject, state, code, duration), tags=(state,))
                tree.see(subject)
                if state in ('成功', '失败'):
                    results[subject] = state
                    n_ok = sum(v == '成功' for v in results.values())
                    n_fail = len(results) - n_ok
                    progress['value'] = len(results)
                    count_var.set(f'总计 {len(SUBJECTS)} | 成功 {n_ok} | 失败 {n_fail} | 未完成 {len(SUBJECTS)-len(results)}')
            elif kind == 'current' and not stop.is_set():
                current_var.set(args[0])
            elif kind == 'fatal':
                append_output(f'\n[调度器致命异常] {args[0]}\n')
                current_var.set('调度器异常，详见输出')
                for subject in SUBJECTS:
                    if tree.item(subject, 'values')[2] == '运行中':
                        tree.item(subject, values=(SUBJECTS.index(subject)+1, subject, '状态未知', '', ''), tags=())
                messagebox.showerror('调度器异常', args[0])
            elif kind == 'finished':
                running = False
                stop_button.configure(state='disabled')
                if len(results) == len(SUBJECTS):
                    current_var.set('全部任务已结束，请查看成功/失败统计和日志')
                    append_output(f'\n[调度器] 全部 {len(SUBJECTS)} 个任务处理完毕。\n')
                else:
                    current_var.set('已停止或中断；可继续运行未记录完成的任务')
                    start_button.configure(state='normal', text='继续运行剩余任务')
                    if not results:
                        entry.configure(state='normal')
                        browse_button.configure(state='normal')
                if close_after:
                    window.destroy()
                    return
        if chunks:
            append_output(''.join(chunks))
        window.after(80, poll)

    def on_close():
        nonlocal close_after
        if not running:
            window.destroy()
        elif messagebox.askyesno('正在运行', '是否等待当前任务自然结束，然后停止队列并关闭窗口？\n不会强制结束原脚本。'):
            close_after = True
            request_stop()

    start_button.configure(command=start)
    stop_button.configure(command=request_stop)
    log_button.configure(command=open_logs)
    window.protocol('WM_DELETE_WINDOW', on_close)
    window.after(80, poll)
    window.mainloop()


if __name__ == '__main__':
    main()
