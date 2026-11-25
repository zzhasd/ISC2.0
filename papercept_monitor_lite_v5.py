#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PaperCept ICRA 2027 论文状态查询（requests 轻量版，只读，不修改投稿）。"""
import argparse
import getpass
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlsplit

LOGIN_URL = 'https://ras.papercept.net/conferences/scripts/login.pl'
DEFAULT_CONFERENCE = 'ICRA 2027'
TRANSLATIONS = {
    'under review': '审稿中', 'decision pending': '等待决定',
    'accepted': '已接收', 'rejected': '已拒稿', 'received': '已收到',
    'submitted': '已提交', 'withdrawn': '已撤稿',
}


class QueryError(Exception):
    pass


def clean(s):
    return ' '.join(s.replace('¶', '').split())


def parse_papers(html):
    """根据表头定位 Number/Title/Status，忽略附件行。"""
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    for table in soup.find_all('table'):
        columns = None
        for tr in table.find_all('tr'):
            if tr.find_parent('table') is not table:
                continue
            cells = tr.find_all(['td', 'th'], recursive=False)
            if not cells:
                continue
            values = [clean(c.get_text(' ', strip=True)) for c in cells]
            labels = [v.casefold() for v in values]
            if all(k in labels for k in ('number', 'title', 'status')):
                columns = {k: labels.index(k) for k in ('number', 'title', 'status')}
                if 'type of submission' in labels:
                    columns['type'] = labels.index('type of submission')
                continue
            if columns is None or len(values) <= max(columns.values()):
                continue
            number = values[columns['number']]
            title = values[columns['title']]
            status = values[columns['status']]
            if not re.fullmatch(r'\d+', number) or not title or not status:
                continue
            submission_type = values[columns['type']].casefold() if 'type' in columns else ''
            if (submission_type.startswith('attachment to submission')
                    or title.casefold().startswith(('video attachment', 'attachment to submission'))):
                continue
            result[number] = {'number': number, 'title': title, 'status': status}
    return sorted(result.values(), key=lambda p: int(p['number']))


def trusted_url(base, target):
    url = urljoin(base, target)
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname != 'ras.papercept.net'
            or parts.username or parts.password or parts.port not in (None, 443)):
        raise QueryError('网页指向非预期地址，已停止请求以保护账号信息。')
    return url


def request(session, method, url, data=None, referer=None):
    """仅访问原站 HTTPS；不向第三方转发账号密码或会话。"""
    for _ in range(8):
        url = trusted_url(LOGIN_URL, url)
        response = session.request(method, url, data=data if method == 'POST' else None,
                                   params=data if method == 'GET' else None,
                                   headers={'Referer': referer} if referer else {},
                                   timeout=30, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            target = response.headers.get('Location')
            if not target:
                raise QueryError('网站返回无效跳转。')
            referer, url = response.url, trusted_url(response.url, target)
            if response.status_code in (301, 302, 303):
                method, data = 'GET', None
            continue
        response.raise_for_status()
        return response
    raise QueryError('页面跳转次数过多。')


def login_form(html, base, account, password):
    """读取真实 HTML 表单字段（包括隐藏字段），不硬编码 PIN 字段名。"""
    soup = BeautifulSoup(html, 'html.parser')
    pw = soup.select_one('form input[type="password"][name]:not([disabled])')
    if pw is None:
        raise QueryError('没有找到登录密码表单，可能需要 JavaScript 或人工验证。')
    form = pw.find_parent('form')
    fields = [x for x in form.find_all('input', attrs={'name': True})
              if not x.has_attr('disabled') and x.get('type', 'text').lower() in ('text', 'email', 'tel', 'number')]
    if not fields:
        raise QueryError('没有找到账号输入框。')
    def score(x):
        return bool(re.search(r'pin|alias|email|orcid|login|user',
                              ' '.join(str(x.get(k, '')) for k in ('name', 'id', 'placeholder')), re.I))
    user = max(fields, key=score)
    data = []
    for x in form.find_all(['input', 'select', 'textarea'], attrs={'name': True}):
        if x.has_attr('disabled'):
            continue
        name = x['name']
        kind = x.get('type', 'text').lower()
        if x is user:
            value = account
        elif x is pw:
            value = password
        elif kind in ('submit', 'button', 'reset', 'image', 'file', 'password'):
            continue
        elif kind in ('checkbox', 'radio') and not x.has_attr('checked'):
            continue
        elif x.name == 'select':
            option = x.select_one('option[selected]') or x.find('option')
            if option is None:
                continue
            value = option.get('value', option.get_text())
        elif x.name == 'textarea':
            value = x.get_text()
        else:
            value = x.get('value', 'on' if kind in ('checkbox', 'radio') else '')
        data.append((name, value))
    submits = [x for x in form.find_all(['input', 'button']) if not x.has_attr('disabled')
               and x.get('type', 'submit' if x.name == 'button' else 'text').lower() == 'submit']
    login = [x for x in submits if re.fullmatch(r'log\s*in|sign\s*in',
             clean(x.get('value', '') or x.get_text(' ', strip=True)), re.I)]
    submit = login[0] if login else (submits[0] if len(submits) == 1 else None)
    if submit is not None and submit.get('name'):
        data.append((submit['name'], submit.get('value', '')))
    # The real login page has a zero-size native Submit input and a visible
    # Log in link (title="Click to log in") calling command('Login').
    # form.submit() excludes the native submit button from submitted fields.
    actual_link = form.find('a', attrs={'title': re.compile(r'^Click to log in$', re.I)})
    if actual_link is not None:
        if command_arg(actual_link) != 'Login' or not form.find('input', attrs={'name': 'Command'}):
            raise QueryError('登录链接结构已变化，无法安全模拟登录。')
        data = [(k, v) for k, v in data if k not in ('Command', 'Submit')]
        data.append(('Command', 'Login.x'))
        method = form.get('method', 'get').lower()
        action = form.get('action', '')
    else:
        if submit is None:
            raise QueryError('没有找到明确的登录提交按钮。')
        method = submit.get('formmethod', form.get('method', 'get')).lower()
        action = submit.get('formaction', form.get('action', ''))
    if method != 'post':
        raise QueryError('未找到标准 POST 登录表单；为避免密码进入网址，已停止。')
    return trusted_url(base, action), data


def target_rows(soup, conference):
    target = re.sub(r'\W+', '', conference.casefold())
    for tr in soup.find_all('tr'):
        cells = tr.find_all(['td', 'th'], recursive=False)
        if any(re.sub(r'\W+', '', clean(c.get_text(' ', strip=True)).casefold()) == target
               for c in cells):
            yield tr
            # A conference name can span several rows, e.g. author and reviewer.
            span = max([int(c.get('rowspan', '1')) for c in cells
                        if str(c.get('rowspan', '1')).isdigit()] or [1])
            for extra in tr.find_next_siblings('tr', limit=min(span-1, 20)) if span > 1 else []:
                yield extra


def enter_controls(row):
    for x in row.find_all(['a', 'button', 'input']):
        if x.find_parent('tr') is not row:
            continue
        label = clean(x.get_text(' ', strip=True) or x.get('value', ''))
        if label.casefold() == 'enter':
            yield x



def command_arg(control):
    """Recognize only a direct command('...') invocation, not arbitrary JS."""
    for attr in ('href', 'onclick'):
        expr = control.get(attr, '').strip()
        m = re.fullmatch(r"(?:javascript:\s*)?(?:return\s+)?command\(\s*(['\"])([A-Za-z0-9_ +.-]+)\1\s*\)\s*;?", expr, re.I)
        if m:
            return m.group(2)
    return None


def command_post(soup, control, base, arg):
    """Replicate the exact form submission seen on the access page."""
    form = soup.find('form')  # command() uses document.forms[0]
    if form is None or form.get('method', 'get').lower() != 'post':
        raise QueryError('未找到工作区 POST 表单。')
    field = form.find('input', attrs={'name': 'Command'})
    if field is None or field.has_attr('disabled'):
        raise QueryError('工作区表单没有可用的 Command 字段。')
    data = []
    for x in form.find_all('input', attrs={'name': True}):
        if x.has_attr('disabled'):
            continue
        name = x['name']
        kind = x.get('type', 'text').lower()
        if x is field:
            data.append((name, arg.replace(' ', '+') + '.x'))
        elif kind in ('submit', 'button', 'reset', 'image', 'file', 'password'):
            continue
        elif kind in ('checkbox', 'radio') and not x.has_attr('checked'):
            continue
        else:
            data.append((name, x.get('value', 'on' if kind in ('checkbox', 'radio') else '')))
    return ('POST', trusted_url(base, form.get('action', '')), data)


def workspace_request(html, base, conference):
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []
    for row in target_rows(soup, conference):
        author = bool(re.search(r'author|proposer', row.get_text(' ', strip=True), re.I))
        for link in enter_controls(row):
            arg = command_arg(link)
            if arg is not None:
                # Limit actions to the explicitly selected author's workspace.
                if not re.fullmatch(r'LoginAs_Proposer_\d+', arg, re.I):
                    continue
                candidates.append((True, command_post(soup, link, base, arg)))
                continue
            href = link.get('href', '').strip()
            if (link.name == 'a' and href and not href.startswith('#')
                    and urlsplit(href).scheme in ('', 'https') and not link.has_attr('onclick')
                    and author):
                candidates.append((True, ('GET', trusted_url(base, href), None)))
    matches = []
    for _, item in candidates:
        if item not in matches:
            matches.append(item)
    if len(matches) > 1:
        raise QueryError('发现多个作者工作区，无法安全确定入口。')
    return matches[0] if matches else None


def diagnostic(page, conference):
    """Only output fixed labels and counts; never dump HTML, URLs, cookies or inputs."""
    soup = BeautifulSoup(page.content, 'html.parser')
    rows = list(target_rows(soup, conference))
    controls = [x for row in rows for x in enter_controls(row)]
    js_controls = sum(x.has_attr('onclick') or x.get('href', '').lower().startswith(('javascript:', '#'))
                      or not x.get('href') for x in controls)
    password_field = bool(soup.select_one('input[type="password"]'))
    access = bool(re.search(r'access a workspace|author or proposer of submission', soup.get_text(' ', strip=True), re.I))
    print('\n--- 安全诊断（不含账号、密码、Cookie 或会话链接）---', flush=True)
    print(f'HTTP 状态码：{page.status_code}')
    print(f'仍有密码框：{"是" if password_field else "否"}')
    print(f'出现工作区标志：{"是" if access else "否"}')
    print(f'目标会议匹配行数：{len(rows)}')
    print(f'目标会议 Enter 控件数：{len(controls)}')
    print(f'疑似需 JavaScript 或表单提交的 Enter 数：{js_controls}')
    print('-----------------------------------------------', flush=True)
    if password_field:
        return '仍显示密码框：可能未完成登录，或页面同时保留了登录表单。请先用浏览器验证；不要反复尝试密码。'
    if rows and js_controls:
        return '已找到会议，但 Enter 的实现与已知表单结构不同，或不是作者入口。请核对工作区。'
    if access and not rows:
        return '页面出现工作区标志，但没有匹配会议。请核对浏览器中会议的实际名称和权限。'
    return '无法确认已成功进入会议工作区，请将以上诊断文字发来（不要发送网页源代码或密码）。'


def query_once(session, account, password, conference):
    page = request(session, 'GET', LOGIN_URL)
    if conference.casefold() in BeautifulSoup(page.content, 'html.parser').get_text(' ', strip=True).casefold():
        papers = parse_papers(page.content)
        if papers:
            return papers
    workspace = workspace_request(page.content, page.url, conference)
    if workspace is None:
        if not BeautifulSoup(page.content, 'html.parser').select_one('input[type="password"]'):
            raise QueryError(diagnostic(page, conference))
        print('已识别登录表单，正在提交登录请求。', flush=True)
        action, data = login_form(page.content, page.url, account, password)
        page = request(session, 'POST', action, data, page.url)
        workspace = workspace_request(page.content, page.url, conference)
        if workspace is None:
            raise QueryError(diagnostic(page, conference))
    method, url, data = workspace
    print('已定位作者工作区，正在查询论文状态。', flush=True)
    page = request(session, method, url, data, referer=page.url)
    papers = parse_papers(page.content)
    if not papers:
        diagnostic(page, conference)
        raise QueryError('未读取到论文状态表。可能没有论文，或工作区需要 JavaScript。不会覆盖已有状态记录。')
    return papers


def compare_and_save(papers, path, conference):
    previous = {}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding='utf-8'))
            previous = {p['number']: p for p in old['papers']}
        except (ValueError, KeyError, TypeError, OSError):
            print('提示：历史记录无法读取，本次将重新建立基准。')
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    print(f'\n[{now}] {conference}：共查询到 {len(papers)} 篇论文')
    changes = []
    for p in papers:
        status = p['status']
        zh = TRANSLATIONS.get(status.casefold(), '')
        print(f"  #{p['number']}  {status}" + (f'（{zh}）' if zh else ''))
        print(f"    {p['title']}")
        old = previous.get(p['number'])
        if old and clean(old['status']).casefold() != clean(status).casefold():
            changes.append(f"#{p['number']}: {old['status']} -> {status}")
        elif previous and old is None:
            changes.append(f"#{p['number']}: 新发现论文，{status}")
    missing = set(previous) - {p['number'] for p in papers}
    if missing:
        print('注意：本次未显示以下历史论文，不将其判定为撤稿：' + ', '.join(sorted(missing)))
    if changes:
        print('\a\n*** 论文状态变化 ***')
        for change in changes:
            print(change)
    elif previous:
        print('状态无变化。')
    else:
        print('首次查询：已建立状态基准。')
    # 保留本次缺失的历史论文，以便其重新出现时仍可比较。
    merged = {**previous, **{p['number']: p for p in papers}}
    payload = {'conference': conference, 'checked_at': now, 'papers': list(merged.values()),
               'visible_numbers': [p['number'] for p in papers], 'changes': changes}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    print(f'记录文件：{path.resolve()}', flush=True)


def main():
    parser = argparse.ArgumentParser(description='PaperCept 论文状态自动查询')
    parser.add_argument('--conference', default=DEFAULT_CONFERENCE, help='会议名称，默认 ICRA 2027')
    parser.add_argument('--watch', action='store_true', help='持续监控，默认每30分钟查询一次')
    parser.add_argument('--interval', type=int, default=30, help='监控间隔（分钟，至少10分钟）')
    parser.add_argument('--test-login', type=Path, help='离线验证登录表单，不联网，不使用真实账号密码')
    parser.add_argument('--test-html', type=Path, help='离线解析作者工作区 HTML，不联网、不需要密码、不写入监控记录')
    parser.add_argument('--test-access', type=Path, help='离线检查 Access page HTML 的作者入口，不联网、不显示会话字段')
    args = parser.parse_args()
    if args.test_login or args.test_html or args.test_access:
        try:
            if args.test_login:
                action, fields = login_form(args.test_login.read_bytes(), LOGIN_URL, 'TEST_ACCOUNT', 'TEST_PASSWORD')
                values = dict(fields)
                if (values.get('LoginId') != 'TEST_ACCOUNT' or values.get('Password') != 'TEST_PASSWORD'
                        or values.get('Command') != 'Login.x' or 'Submit' in values):
                    raise QueryError('离线登录参数与已知登录页面不一致。')
                print('登录表单：已识别 LoginId / Password / Command=Login.x（不发送请求，不显示隐藏字段值）')
            if args.test_access:
                result = workspace_request(args.test_access.read_bytes(), LOGIN_URL, args.conference)
                if result is None:
                    raise QueryError('离线检查未找到作者工作区入口。')
                print(f'{args.conference}：已识别作者入口，HTTP 方法 {result[0]}（未实际发送请求）')
            if args.test_html:
                papers = parse_papers(args.test_html.read_bytes())
                if not papers:
                    raise QueryError('离线检查未找到论文状态表格。')
                print(f'{args.conference}：离线提取 {len(papers)} 篇论文（不是实时状态）')
                for paper in papers:
                    status = paper['status']
                    zh = TRANSLATIONS.get(status.casefold(), '')
                    print(f"#{paper['number']}  {status}" + (f'（{zh}）' if zh else ''))
                    print(f"  {paper['title']}")
            return 0
        except (OSError, QueryError) as exc:
            print(f'离线检查失败：{exc}', file=sys.stderr)
            return 1
    if args.interval < 10:
        parser.error('请使用至少10分钟的查询间隔。')
    account = input('PaperCept 账号（PIN / 邮箱 / 登录别名）：').strip()
    password = getpass.getpass('密码（输入时不显示）：')
    if not account or not password:
        print('账号和密码不能为空。', file=sys.stderr)
        return 1
    # 按账号和会议区分记录，不将明文账号或密码写入磁盘。
    key = hashlib.sha256((account.casefold() + '\0' + args.conference.casefold()).encode()).hexdigest()[:16]
    path = Path(__file__).resolve().parent / 'papercept_status' / f'{key}.json'
    with requests.Session() as session:
        session.headers.update({'User-Agent': 'PaperCeptStatusMonitor/5.0', 'Accept': 'text/html,application/xhtml+xml'})
        while True:
            try:
                papers = query_once(session, account, password, args.conference)
                compare_and_save(papers, path, args.conference)
            except QueryError as exc:
                # 不反复尝试可能无效的密码，以免触发账户锁定。
                print(f'查询停止：{exc}', file=sys.stderr)
                return 1
            except requests.RequestException:
                print('网络请求失败（连接超时、证书或 HTTP 错误等）。请检查网络及网站是否正常开放；不会输出可能含会话信息的 URL。', file=sys.stderr)
                return 1
            except OSError:
                print('无法写入本地状态记录，请检查目录权限。', file=sys.stderr)
                return 1
            if not args.watch:
                return 0
            print(f'将在 {args.interval} 分钟后再次查询；按 Ctrl+C 停止。', flush=True)
            time.sleep(args.interval * 60)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n已停止监控。')
