#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站API爬虫 - 完整版本（支持番剧下载）
使用B站官方API获取视频信息、评论、用户数据等
完全合规，遵守B站使用条款
支持番剧URL处理和下载
"""

import requests
import json
import time
import re
import hashlib
import uuid
import subprocess
import shutil
from datetime import datetime
import os
import sys
import urllib.parse
from pathlib import Path


class BilibiliAPIClient:
    """B站API客户端类"""

    def __init__(self, cookies=None, auto_load_cookies=True):
        self.base_url = "https://api.bilibili.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
        self.request_count = 0
        self.start_time = time.time()
        self._cookies_loaded = False
        self._wbi_keys = None
        self._last_wbi_key_fetch = 0

        # 初始化B站设备追踪ID（绕过简单的爬虫检测）
        self._init_buvid()

        # 自动加载或手动设置Cookie
        if cookies:
            self.set_cookies_from_dict(cookies)
        elif auto_load_cookies:
            self.load_cookies(silent=True)

    # ========== Cookie/登录管理 ==========

    def _init_buvid(self):
        """初始化B站设备追踪ID（绕过设备指纹检测）"""
        # buvid3 格式: XZ-<UUID>infoc
        self.session.cookies.set('buvid3', f"XZ-{str(uuid.uuid4()).upper()}infoc")
        self.session.cookies.set('buvid4', str(uuid.uuid4()).upper())

    def set_cookies_from_dict(self, cookies_dict, auto_save=True):
        """从字典设置Cookie（自动保存到文件）
        Args:
            cookies_dict: 如 {'SESSDATA': 'xxx', 'buvid3': 'xxx'}
            auto_save: 是否自动保存到文件（下次启动时自动加载）
        """
        for key, value in cookies_dict.items():
            self.session.cookies.set(key, value)
        self._cookies_loaded = True
        print("✅ Cookie已设置 — 现在可以访问需要登录的内容")
        if auto_save:
            self.save_cookies(silent=True)

    def set_cookies_from_string(self, cookie_str):
        """从浏览器格式的Cookie字符串设置Cookie
        格式: "SESSDATA=abc123; b_lsid=xyz; DedeUserID=12345"
        通常可在浏览器F12 → 网络 → 请求头中复制

        Args:
            cookie_str: 分号分隔的key=value字符串
        """
        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key.strip()] = value.strip()

        if cookies:
            self.set_cookies_from_dict(cookies)
        else:
            print("❌ 无法解析Cookie字符串")

    def set_sessdata(self, sessdata, auto_save=True):
        """快速设置 SESSDATA（大会员身份的关键Cookie，自动保存）
        从浏览器开发者工具中复制SESSDATA的值即可

        Args:
            sessdata: SESSDATA值
            auto_save: 是否自动保存到文件（下次启动时自动加载）
        """
        self.session.cookies.set('SESSDATA', sessdata)
        self._cookies_loaded = True
        print("✅ SESSDATA已设置 — 大会员权限已激活")
        if auto_save:
            self.save_cookies(silent=True)

    def load_cookies(self, filepath='bilibili_cookies.json', silent=False):
        """从本地文件加载Cookie
        Args:
            filepath: Cookie文件路径
            silent: 静默模式（不打印消息）
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            self.set_cookies_from_dict(cookies)
            if not silent:
                print(f"✅ 已从文件加载Cookie: {filepath}")
            return True
        except FileNotFoundError:
            if not silent:
                print(f"❌ 未找到Cookie文件: {filepath}")
            return False
        except Exception as e:
            if not silent:
                print(f"❌ 加载Cookie失败: {e}")
            return False

    def save_cookies(self, filepath='bilibili_cookies.json', silent=False):
        """保存当前Cookie到本地文件（便于下次自动加载）
        Args:
            filepath: Cookie文件路径
            silent: 静默模式，不打印消息（用于自动保存）
        """
        try:
            important_cookies = ['SESSDATA', 'buvid3', 'buvid4', 'b_lsid', '_uuid',
                                 'DedeUserID', 'DedeUserID__ckMd', 'sid', 'b_nut',
                                 'b_ts', 'buvid_fp']
            cookies_dict = {}
            for cookie in self.session.cookies:
                if cookie.name in important_cookies:
                    cookies_dict[cookie.name] = cookie.value

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cookies_dict, f, ensure_ascii=False, indent=2)
            if not silent:
                print(f"✅ Cookie已保存到: {filepath}")
            return True
        except Exception as e:
            if not silent:
                print(f"❌ 保存Cookie失败: {e}")
            return False

    def check_login_status(self):
        """检查当前登录状态
        Returns:
            dict: {is_logged_in: bool, username: str, is_vip: bool, ...}
        """
        try:
            nav_url = f"{self.base_url}/x/web-interface/nav"
            resp = self.session.get(nav_url, timeout=10)
            data = resp.json()

            if data.get('code') == 0:
                nav_data = data.get('data', {})
                is_login = nav_data.get('isLogin', False)
                username = nav_data.get('uname', '')
                # 检查大会员状态
                vip_status = nav_data.get('vipStatus', 0)  # 1=正常
                vip_type = nav_data.get('vipType', 0)  # 2=大会员
                is_vip = (vip_status == 1 and vip_type >= 1)

                return {
                    'is_logged_in': is_login,
                    'username': username,
                    'is_vip': is_vip,
                    'vip_status': vip_status,
                    'vip_type': vip_type
                }
            return {'is_logged_in': False, 'error': data.get('message', '')}
        except Exception as e:
            return {'is_logged_in': False, 'error': str(e)}

    # ========== 核心请求方法 ==========

    def _make_request(self, api_url, params=None, use_wbi=False):
        """发送API请求（含VIP/权限不足智能处理）

        Args:
            api_url: API地址
            params: 请求参数字典
            use_wbi: 是否使用Wbi签名（部分B站新版API要求）
        """
        # 需要Wbi签名的API（番剧播放地址等）
        if use_wbi:
            return self._make_request_with_wbi(api_url, params)

        try:
            self.request_count += 1
            print(f"📡 请求 #{self.request_count}: {api_url}")

            response = self.session.get(api_url, params=params, timeout=15)

            if response.status_code == 200:
                # 检查响应内容是否为空
                if not response.text.strip():
                    print(f"❌ API返回空响应")
                    return None

                # 尝试解析JSON
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析失败: {e}")
                    print(f"❌ 响应内容: {response.text[:200]}...")
                    return None

                code = data.get('code', -1)
                if code == 0:
                    print(f"✅ 请求成功")
                    # B站API字段不统一：有的接口用data，有的用result
                    # pgc/view/web/season (番剧信息) 用 result
                    # x/web-interface/view (视频信息) 用 data
                    return data.get('data') or data.get('result') or {}

                # B站API错误码处理
                error_msg = data.get('message', '未知错误')

                if code == -10403:
                    print(f"❌ 权限不足: {error_msg}")
                    print("💡 该内容需要登录/VIP权限")
                    if self._cookies_loaded:
                        print("⚠️  Cookie已设置但仍被拒绝，可能是Cookie过期或权限不足")
                        print("💡 请尝试重新设置Cookie (功能14)")
                    else:
                        print("💡 请先设置Cookie (功能14)")
                    return None
                elif code == -400:
                    print(f"❌ 请求参数错误: {error_msg}")
                    print("💡 可能需要更新API参数或添加Wbi签名")
                    return None
                elif code == -412:
                    print(f"❌ 请求被拦截: {error_msg}")
                    print("💡 缺少必要的请求头或Cookie，尝试添加Cookie后再试")
                    return None
                elif code == -403:
                    print(f"❌ 访问被拒绝: {error_msg}")
                    print("💡 当前账号可能没有权限访问此内容")
                    return None
                else:
                    print(f"❌ API错误 (code={code}): {error_msg}")
                    return None

            elif response.status_code == 403:
                print(f"❌ HTTP 403 - 权限不足/被服务器拒绝")
                if self._cookies_loaded:
                    print("⚠️  Cookie已设置但仍被拒绝，Cookie可能已过期")
                else:
                    print("💡 该内容可能需要VIP大会员权限")
                    print("💡 请在功能14中设置Cookie(Cookie中需包含大会员SESSDATA)")
                return None

            elif response.status_code == 412:
                print(f"❌ HTTP 412 - 请求被拦截（触发风控）")
                print("💡 请求频率过高或缺少必要标识(Buvid)")
                if not self._cookies_loaded:
                    print("💡 添加Cookie可能有助于绕过风控")
                return None

            else:
                print(f"❌ HTTP错误: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print(f"⏰ 请求超时")
            return None
        except requests.exceptions.ConnectionError:
            print(f"🔌 连接错误")
            return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None

    # ========== Wbi签名（绕过B站新版API验证） ==========

    MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 37, 12, 52, 56, 7, 0, 60, 36, 40, 57, 59, 17, 51,
        61, 6, 30, 1, 20, 25, 24, 26, 13, 4, 22, 11, 62, 55, 41, 38, 44, 21, 63, 54,
        39, 48, 34, 16
    ]

    def _get_wbi_keys(self):
        """获取Wbi签名所需的 img_key 和 sub_key
        从B站导航接口获取，缓存1小时
        """
        if self._wbi_keys and time.time() - self._last_wbi_key_fetch < 3600:
            return self._wbi_keys

        try:
            nav_url = f"{self.base_url}/x/web-interface/nav"
            resp = self.session.get(nav_url, timeout=10)
            data = resp.json()

            if data.get('code') == 0 and 'wbi_img' in data.get('data', {}):
                wbi_img = data['data']['wbi_img']
                img_url = wbi_img.get('img_url', '')
                sub_url = wbi_img.get('sub_url', '')

                # 从URL中提取key: https://i0.hdslb.com/bfs/wbi/xxxxx.png -> xxxxx
                img_key = img_url.rsplit('/', 1)[-1].split('.')[0]
                sub_key = sub_url.rsplit('/', 1)[-1].split('.')[0]

                self._wbi_keys = (img_key, sub_key)
                self._last_wbi_key_fetch = time.time()
                return self._wbi_keys
        except Exception as e:
            print(f"⚠️ 获取Wbi keys失败: {e}")

        return None, None

    def _encrypt_wbi(self, params):
        """对API参数进行Wbi签名（B站前端反爬机制）
        参考B站前端实现中 mixinKeyEncTab 的置换算法

        Args:
            params: 原始请求参数字典

        Returns:
            dict: 添加了 w_rid 和 wts 的参数字典
        """
        if params is None:
            params = {}

        img_key, sub_key = self._get_wbi_keys()
        if not img_key or not sub_key:
            return params

        # 使用置换表计算mixin_key: sub_key + img_key 按 MIXIN_KEY_ENC_TAB 置换
        raw = sub_key + img_key
        mixin_key = ''.join(raw[i] for i in self.MIXIN_KEY_ENC_TAB)[:32]

        # 添加时间戳
        params['wts'] = int(time.time())

        # 按key排序
        keys = sorted(params.keys())
        sorted_params = {k: params[k] for k in keys}

        # 构建查询字符串并计算Wbi签名
        query = urllib.parse.urlencode(sorted_params)
        sign_str = query + mixin_key
        w_rid = hashlib.md5(sign_str.encode()).hexdigest()

        params['w_rid'] = w_rid
        return params

    def _make_request_with_wbi(self, api_url, params=None):
        """使用Wbi签名发送API请求（绕过防爬检测）
        部分B站新版API接口要求携带 w_rid 和 wts 参数
        """
        if params is None:
            params = {}

        # 对参数进行Wbi签名
        signed_params = self._encrypt_wbi(params.copy())

        try:
            self.request_count += 1
            print(f"📡 请求 #{self.request_count} [Wbi签名]: {api_url}")

            response = self.session.get(api_url, params=signed_params, timeout=15)

            if response.status_code == 200:
                if not response.text.strip():
                    print(f"❌ API返回空响应")
                    return None

                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析失败: {e}")
                    return None

                code = data.get('code', -1)
                if code == 0:
                    print(f"✅ 请求成功 (Wbi签名)")
                    # B站API字段不统一：有的接口用data，有的用result
                    return data.get('data') or data.get('result') or {}

                error_msg = data.get('message', '未知错误')
                print(f"❌ API错误 (code={code}): {error_msg}")

                if code in [-10403, -403]:
                    if self._cookies_loaded:
                        print("⚠️  Cookie可能已过期，请重新设置")
                    else:
                        print("💡 该内容需要VIP权限，请设置Cookie (功能14)")
                return None

            elif response.status_code == 403:
                print(f"❌ HTTP 403 - 权限不足")
                print("💡 需要登录/VIP权限的大会员内容")
                return None
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print(f"⏰ 请求超时")
            return None
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None

    def get_video_info(self, bvid):
        """获取视频基本信息"""
        api_url = f"{self.base_url}/x/web-interface/view"
        params = {'bvid': bvid}

        return self._make_request(api_url, params)

    def get_video_stat(self, bvid):
        """获取视频统计数据"""
        api_url = f"{self.base_url}/x/web-interface/archive/stat"
        params = {'bvid': bvid}

        return self._make_request(api_url, params)

    def get_video_tags(self, bvid):
        """获取视频标签"""
        api_url = f"{self.base_url}/x/tag/archive/tags"
        params = {'bvid': bvid}

        return self._make_request(api_url, params)

    def get_video_comments(self, bvid, page=1, page_size=20, sort='time'):
        """获取视频评论

        Args:
            bvid: 视频BV号
            page: 页码
            page_size: 每页评论数
            sort: 排序方式 ('time'按时间, 'like'按点赞)
        """
        api_url = f"{self.base_url}/x/v2/reply/main"
        params = {
            'oid': bvid,
            'type': 1,  # 视频评论
            'pn': page,
            'ps': page_size,
            'sort': sort
        }

        return self._make_request(api_url, params)

    def get_video_danmaku(self, bvid):
        """获取视频弹幕"""
        # 首先获取视频的cid
        video_info = self.get_video_info(bvid)
        if not video_info:
            return None

        cid = video_info.get('cid', 0)
        if cid == 0:
            print("❌ 无法获取视频CID")
            return None

        api_url = f"{self.base_url}/x/v1/dm/list.so"
        params = {
            'oid': cid,
            'type': 1  # 视频弹幕
        }

        return self._make_request(api_url, params)

    def get_user_info(self, user_id):
        """获取用户信息"""
        api_url = f"{self.base_url}/x/space/acc/info"
        params = {'mid': user_id}

        return self._make_request(api_url, params)

    def get_user_videos(self, user_id, page=1, page_size=30):
        """获取用户发布的视频"""
        api_url = f"{self.base_url}/x/space/arc/search"
        params = {
            'mid': user_id,
            'ps': page_size,
            'pn': page
        }

        return self._make_request(api_url, params)

    def get_user_followers(self, user_id, page=1, page_size=20):
        """获取用户粉丝"""
        api_url = f"{self.base_url}/x/relation/followers"
        params = {
            'vmid': user_id,
            'pn': page,
            'ps': page_size
        }

        return self._make_request(api_url, params)

    def get_user_following(self, user_id, page=1, page_size=20):
        """获取用户关注"""
        api_url = f"{self.base_url}/x/relation/followings"
        params = {
            'vmid': user_id,
            'pn': page,
            'ps': page_size
        }

        return self._make_request(api_url, params)

    def search_videos(self, keyword, page=1, page_size=20):
        """搜索视频"""
        api_url = f"{self.base_url}/x/web-interface/search/all/v2"
        params = {
            'keyword': keyword,
            'page': page,
            'page_size': page_size
        }

        return self._make_request(api_url, params)

    def get_hot_videos(self, page=1, page_size=20):
        """获取热门视频"""
        api_url = f"{self.base_url}/x/web-interface/popular/series/one"
        params = {
            'ps': page_size,
            'pn': page
        }

        return self._make_request(api_url, params)

    def get_ranking_videos(self, day='three_day'):
        """获取排行榜视频

        Args:
            day: 排行榜类型 ('three_day', 'week', 'month')
        """
        # 尝试多个API接口
        apis = [
            # 方法1: 原始接口
            {
                'url': f"{self.base_url}/x/web-interface/ranking/v2",
                'params': {'rid': 0, 'day': day, 'type': 1}
            },
            # 方法2: 备用接口
            {
                'url': f"{self.base_url}/x/web-interface/ranking",
                'params': {'rid': 0, 'day': day, 'type': 1}
            },
            # 方法3: 热门接口
            {
                'url': f"{self.base_url}/x/web-interface/popular",
                'params': {'ps': 20, 'pn': 1}
            }
        ]

        for i, api_config in enumerate(apis):
            print(f"🔄 尝试方法 {i + 1}: {api_config['url']}")
            result = self._make_request(api_config['url'], api_config['params'])
            if result:
                return result
            print(f"❌ 方法 {i + 1} 失败，尝试下一个方法...")

        print("❌ 所有API方法都失败了")
        return None

    def get_video_playurl(self, bvid, cid=None, quality=80):
        """获取视频播放地址（普通视频）

        Args:
            bvid: 视频BV号
            cid: 视频CID（可选，如果不提供会自动获取）
            quality: 视频质量 (80-高清, 64-超清, 32-高清, 16-标清)
        """
        # 如果没有提供cid，先获取视频信息
        if not cid:
            video_info = self.get_video_info(bvid)
            if not video_info:
                return None
            cid = video_info.get('cid', 0)

        api_url = f"{self.base_url}/x/player/playurl"
        params = {
            'bvid': bvid,
            'cid': cid,
            'qn': quality,
            'fnval': 16,  # 获取DASH格式
            'fnver': 0,
            'fourk': 1
        }

        return self._make_request(api_url, params)

    # ========== 番剧专用方法 ==========

    def get_bangumi_info_by_epid(self, episode_id):
        """通过剧集ID获取番剧信息

        Args:
            episode_id: 剧集ID (ep3270473中的数字部分)
        """
        print(f"📺 正在获取番剧信息 (剧集ID: {episode_id})")

        # 使用 PGC API
        api_url = f"{self.base_url}/pgc/view/web/season"
        params = {'ep_id': episode_id}

        return self._make_request(api_url, params)

    def get_bangumi_info_by_seasonid(self, season_id):
        """通过季度ID获取番剧信息

        Args:
            season_id: 季度ID (ss12345中的数字部分)
        """
        print(f"📺 正在获取番剧信息 (季度ID: {season_id})")

        api_url = f"{self.base_url}/pgc/view/web/season"
        params = {'season_id': season_id}

        return self._make_request(api_url, params)

    def get_bangumi_playurl(self, ep_id, cid, quality=80):
        """获取番剧播放地址（番剧专用，支持Wbi签名和VIP Cookie）

        对于需要大会员权限的番剧，会根据是否有Cookie自动处理：
        1. 先尝试普通请求
        2. 如果有Cookie且失败，自动使用Wbi签名重试
        3. 如果仍有Cookie权限问题，给出明确提示

        Args:
            ep_id: 剧集ID
            cid: 视频CID
            quality: 视频质量 (80-高清, 64-超清, 32-高清, 16-标清)
        """
        print(f"🎬 正在获取番剧播放地址 (ep_id: {ep_id}, cid: {cid})")

        api_url = f"{self.base_url}/pgc/player/web/playurl"
        params = {
            'ep_id': ep_id,
            'cid': cid,
            'qn': quality,
            'fnval': 16,  # DASH格式
            'fnver': 0,
            'fourk': 1,
            'type': '',
            'platform': 'web'
        }

        # 获取播放地址的关键：
        # 1. 先尝试无签名请求（但带上已有Cookie）
        result = self._make_request(api_url, params)

        # 2. 如果失败且原因可能是权限不足，用Wbi签名重试
        if result is None and self._cookies_loaded:
            print("🔄 尝试使用Wbi签名重试（绕过API检测）...")
            result = self._make_request(api_url, params, use_wbi=True)

        return result

    def get_bangumi_playurl_by_bvid(self, bvid, cid, quality=80):
        """通过BV号获取番剧播放地址（番剧专用，支持Wbi签名）

        Args:
            bvid: 视频BV号
            cid: 视频CID
            quality: 视频质量 (80-高清, 64-超清, 32-高清, 16-标清)
        """
        print(f"🎬 正在获取番剧播放地址 (bvid: {bvid}, cid: {cid})")

        api_url = f"{self.base_url}/pgc/player/web/playurl"
        params = {
            'bvid': bvid,
            'cid': cid,
            'qn': quality,
            'fnval': 16,  # DASH格式
            'fnver': 0,
            'fourk': 1,
            'type': '',
            'platform': 'web'
        }

        # 先尝试无签名请求
        result = self._make_request(api_url, params)

        # 失败时用Wbi签名重试
        if result is None and self._cookies_loaded:
            print("🔄 尝试使用Wbi签名重试（绕过API检测）...")
            result = self._make_request(api_url, params, use_wbi=True)

        return result

    def get_bvid_from_bangumi_url(self, url):
        """从番剧URL中提取BV号和剧集ID

        Args:
            url: 番剧URL

        Returns:
            dict: {'bvid': str, 'ep_id': str, 'cid': int} 或 None
        """
        result = {'bvid': None, 'ep_id': None, 'cid': None}

        # 提取剧集ID (ep3270473)
        ep_match = re.search(r'ep(\d+)', url)
        if ep_match:
            episode_id = ep_match.group(1)
            result['ep_id'] = episode_id
            print(f"📺 检测到番剧剧集ID: {episode_id}")

            # 获取番剧信息
            bangumi_info = self.get_bangumi_info_by_epid(episode_id)
            if bangumi_info:
                # 尝试从返回数据中获取BV号和CID
                episodes = bangumi_info.get('episodes', [])
                for ep in episodes:
                    if str(ep.get('id')) == episode_id:
                        result['bvid'] = ep.get('bvid')
                        result['cid'] = ep.get('cid')
                        if result['bvid']:
                            print(f"✅ 成功从剧集信息获取BV号: {result['bvid']}, CID: {result['cid']}")
                            return result

                # 方法2: 从 sections 中查找
                sections = bangumi_info.get('sections', [])
                for section in sections:
                    episodes_in_section = section.get('episodes', [])
                    for ep in episodes_in_section:
                        if str(ep.get('id')) == episode_id:
                            result['bvid'] = ep.get('bvid')
                            result['cid'] = ep.get('cid')
                            if result['bvid']:
                                print(f"✅ 成功从章节信息获取BV号: {result['bvid']}, CID: {result['cid']}")
                                return result

                # 方法3: 获取第一集的BV号作为备选
                if episodes:
                    first_ep = episodes[0]
                    result['bvid'] = first_ep.get('bvid')
                    result['cid'] = first_ep.get('cid')
                    if result['bvid']:
                        print(f"⚠️  未找到指定剧集，使用第一集BV号: {result['bvid']}, CID: {result['cid']}")
                        return result

                print(f"❌ 无法从番剧信息中提取BV号和CID")

        # 提取季度ID (ss12345)
        ss_match = re.search(r'ss(\d+)', url)
        if ss_match:
            season_id = ss_match.group(1)
            print(f"📺 检测到番剧季度ID: {season_id}")

            # 获取番剧信息
            bangumi_info = self.get_bangumi_info_by_seasonid(season_id)
            if bangumi_info:
                # 获取第一集的BV号
                episodes = bangumi_info.get('episodes', [])
                if episodes:
                    first_ep = episodes[0]
                    result['bvid'] = first_ep.get('bvid')
                    result['cid'] = first_ep.get('cid')
                    result['ep_id'] = first_ep.get('id')
                    if result['bvid']:
                        print(
                            f"✅ 成功从季度信息获取BV号: {result['bvid']}, CID: {result['cid']}, EP_ID: {result['ep_id']}")
                        return result

                print(f"❌ 无法从季度信息中提取BV号和CID")

        return None if not result['bvid'] else result

    def download_bangumi_video(self, url, output_dir='downloads', quality=80):
        """下载番剧视频

        Args:
            url: 番剧URL (ep或ss开头)
            output_dir: 输出目录
            quality: 视频质量
        """
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 获取番剧信息
        bangumi_info = self.get_bvid_from_bangumi_url(url)
        if not bangumi_info:
            print("❌ 无法获取番剧信息")
            return False

        bvid = bangumi_info['bvid']
        ep_id = bangumi_info['ep_id']
        cid = bangumi_info['cid']

        # 获取视频信息（用于标题等）
        video_info = self.get_video_info(bvid)
        if not video_info:
            print("❌ 无法获取视频信息")
            return False

        title = video_info.get('title', 'unknown').replace('/', '_').replace('\\', '_')

        print(f"\n📹 准备下载番剧视频: {title}")
        print(f"BV号: {bvid}")
        print(f"EP_ID: {ep_id}")
        print(f"CID: {cid}")

        # 获取播放地址（使用番剧专用API）
        if ep_id:
            playurl_data = self.get_bangumi_playurl(ep_id, cid, quality)
        else:
            playurl_data = self.get_bangumi_playurl_by_bvid(bvid, cid, quality)

        if not playurl_data:
            print("❌ 无法获取播放地址，尝试使用普通API...")
            # 备用方案：使用普通API（可能对部分非VIP番剧有效）
            playurl_data = self.get_video_playurl(bvid, cid, quality)
            if not playurl_data:
                print("❌ 无法获取播放地址")
                print("💡 可能原因:")
                print("   1. 该番剧需要VIP大会员权限 → 请使用功能14设置Cookie")
                print("   2. Cookie已过期 → 请重新获取")
                print("   3. 当前账号非大会员 → 需要大会员账号")
                return False

        # 解析视频和音频URL
        video_url = None
        audio_url = None

        # DASH格式
        if 'dash' in playurl_data:
            dash_data = playurl_data['dash']

            # 获取视频流
            video_streams = dash_data.get('video', [])
            if video_streams:
                # 选择第一个视频流（通常是最高质量的）
                video_stream = video_streams[0]
                video_url = video_stream.get('baseUrl', '')
                print(f"🎬 找到视频流: {video_stream.get('id', 'unknown')}")

            # 获取音频流
            audio_streams = dash_data.get('audio', [])
            if audio_streams:
                # 选择第一个音频流
                audio_stream = audio_streams[0]
                audio_url = audio_stream.get('baseUrl', '')
                print(f"🎵 找到音频流: {audio_stream.get('id', 'unknown')}")

        # 如果没有找到DASH格式，尝试其他格式
        if not video_url and 'durl' in playurl_data:
            durl_data = playurl_data['durl']
            if durl_data:
                video_url = durl_data[0].get('url', '')
                print(f"🎬 找到传统格式视频流")

        if not video_url:
            print("❌ 无法找到视频流")
            return False

        # 下载视频
        video_filename = os.path.join(output_dir, f"{title}_video.m4s")
        if self._download_file(video_url, video_filename, "视频"):
            print(f"✅ 视频下载完成: {video_filename}")
        else:
            return False

        # 下载音频（如果有）
        if audio_url:
            audio_filename = os.path.join(output_dir, f"{title}_audio.m4s")
            if self._download_file(audio_url, audio_filename, "音频"):
                print(f"✅ 音频下载完成: {audio_filename}")

                # 自动合并视频+音频
                final_filename = os.path.join(output_dir, f"{title}.mp4")
                merged = self._merge_video_audio(video_filename, audio_filename, final_filename)
                if not merged:
                    print("\n💡 稍后可以手动合并:")
                    print(f"   ffmpeg -i \"{video_filename}\" -i \"{audio_filename}\" -c copy \"{final_filename}\"")
            else:
                return False
        else:
            # 如果没有单独的音频，视频文件就是完整的
            final_filename = os.path.join(output_dir, f"{title}.mp4")
            os.rename(video_filename, final_filename)
            print(f"✅ 视频下载完成: {final_filename}")

        return True

    def download_video(self, bvid, output_dir='downloads', quality=80):
        """下载视频（普通视频）

        Args:
            bvid: 视频BV号
            output_dir: 输出目录
            quality: 视频质量
        """
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 获取视频信息
        video_info = self.get_video_info(bvid)
        if not video_info:
            return False

        title = video_info.get('title', 'unknown').replace('/', '_').replace('\\', '_')
        cid = video_info.get('cid', 0)

        print(f"\n📹 准备下载视频: {title}")
        print(f"BV号: {bvid}")
        print(f"CID: {cid}")

        # 获取播放地址
        playurl_data = self.get_video_playurl(bvid, cid, quality)
        if not playurl_data:
            print("❌ 无法获取播放地址")
            return False

        # 解析视频和音频URL
        video_url = None
        audio_url = None

        # DASH格式
        if 'dash' in playurl_data:
            dash_data = playurl_data['dash']

            # 获取视频流
            video_streams = dash_data.get('video', [])
            if video_streams:
                # 选择第一个视频流（通常是最高质量的）
                video_stream = video_streams[0]
                video_url = video_stream.get('baseUrl', '')
                print(f"🎬 找到视频流: {video_stream.get('id', 'unknown')}")

            # 获取音频流
            audio_streams = dash_data.get('audio', [])
            if audio_streams:
                # 选择第一个音频流
                audio_stream = audio_streams[0]
                audio_url = audio_stream.get('baseUrl', '')
                print(f"🎵 找到音频流: {audio_stream.get('id', 'unknown')}")

        # 如果没有找到DASH格式，尝试其他格式
        if not video_url and 'durl' in playurl_data:
            durl_data = playurl_data['durl']
            if durl_data:
                video_url = durl_data[0].get('url', '')
                print(f"🎬 找到传统格式视频流")

        if not video_url:
            print("❌ 无法找到视频流")
            return False

        # 下载视频
        video_filename = os.path.join(output_dir, f"{title}_video.m4s")
        if self._download_file(video_url, video_filename, "视频"):
            print(f"✅ 视频下载完成: {video_filename}")
        else:
            return False

        # 下载音频（如果有）
        if audio_url:
            audio_filename = os.path.join(output_dir, f"{title}_audio.m4s")
            if self._download_file(audio_url, audio_filename, "音频"):
                print(f"✅ 音频下载完成: {audio_filename}")

                # 自动合并视频+音频
                final_filename = os.path.join(output_dir, f"{title}.mp4")
                merged = self._merge_video_audio(video_filename, audio_filename, final_filename)
                if not merged:
                    print("\n💡 稍后可以手动合并:")
                    print(f"   ffmpeg -i \"{video_filename}\" -i \"{audio_filename}\" -c copy \"{final_filename}\"")
            else:
                return False
        else:
            # 如果没有单独的音频，视频文件就是完整的
            final_filename = os.path.join(output_dir, f"{title}.mp4")
            os.rename(video_filename, final_filename)
            print(f"✅ 视频下载完成: {final_filename}")

        return True

    # ========== 文件合并 ==========

    @staticmethod
    def _check_ffmpeg():
        """检查系统中是否有FFmpeg"""
        return shutil.which('ffmpeg') is not None

    @staticmethod
    def _print_ffmpeg_guide():
        """打印安装FFmpeg的教程"""
        print("\n📥 FFmpeg 下载安装教程:")
        print("=" * 50)
        print("方法1 - 一键安装 (推荐):")
        print("  1. 下载: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")
        print("  2. 解压到 C:\\ffmpeg")
        print("  3. 把 C:\\ffmpeg\\bin 添加到系统环境变量 Path")
        print("  4. 重启终端，输入 ffmpeg -version 验证")
        print()
        print("方法2 - 用 winget (Win10/11 自带):")
        print("  以管理员打开终端，运行: winget install FFmpeg")
        print()
        print("方法3 - 使用Python库替代 (无需安装FFmpeg):")
        print("  也可以直接用 Python 的 ffmpeg-python 库:")
        print("  pip install ffmpeg-python")
        print("=" * 50)

    def _merge_video_audio(self, video_path, audio_path, output_path):
        """自动合并视频和音频文件（使用FFmpeg）

        如果系统中有FFmpeg则自动合并，否则打印安装教程。
        也支持使用 pip install ffmpeg-python 后的库合并。

        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径（如 .mp4）

        Returns:
            bool: 是否合并成功
        """
        # 方法1: 用系统FFmpeg
        if self._check_ffmpeg():
            try:
                print("\n🎬 正在使用FFmpeg合并视频+音频...")
                cmd = [
                    'ffmpeg', '-i', video_path, '-i', audio_path,
                    '-c', 'copy', '-y', output_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    # 合并成功，删除原始分离文件
                    os.remove(video_path)
                    os.remove(audio_path)
                    print(f"✅ 合并完成: {output_path}")
                    return True
                else:
                    print(f"❌ FFmpeg合并失败: {result.stderr[:200]}")
                    return False
            except subprocess.TimeoutExpired:
                print("❌ FFmpeg合并超时")
                return False
            except Exception as e:
                print(f"❌ FFmpeg合并出错: {e}")
                return False

        # 方法2: 尝试用 ffmpeg-python 库
        try:
            import ffmpeg
            print("\n🎬 正在使用 ffmpeg-python 库合并视频+音频...")
            input_video = ffmpeg.input(video_path)
            input_audio = ffmpeg.input(audio_path)
            ffmpeg.concat(input_video, input_audio, v=1, a=1).output(output_path, acodec='copy', vcodec='copy').run(
                overwrite_output=True)
            os.remove(video_path)
            os.remove(audio_path)
            print(f"✅ 合并完成: {output_path}")
            return True
        except ImportError:
            pass
        except Exception as e:
            print(f"❌ ffmpeg-python合并失败: {e}")
            return False

        # 两个方法都不可用
        print("\n⚠️  未检测到FFmpeg，视频和音频文件已分别保存")
        print(f"📹 视频: {video_path}")
        print(f"🎵 音频: {audio_path}")
        print("\n💡 手动合并命令 (安装FFmpeg后):")
        print(f"   ffmpeg -i \"{video_path}\" -i \"{audio_path}\" -c copy \"{output_path}\"")
        self._print_ffmpeg_guide()
        return False

    def _download_file(self, url, filename, file_type="文件"):
        """下载文件

        Args:
            url: 文件URL
            filename: 保存文件名
            file_type: 文件类型描述
        """
        try:
            print(f"\n📥 开始下载{file_type}...")
            print(f"📥 URL: {url[:100]}..." if len(url) > 100 else f"📥 URL: {url}")

            # 设置请求头
            headers = {
                'User-Agent': self.session.headers.get('User-Agent'),
                'Referer': 'https://www.bilibili.com',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Origin': 'https://www.bilibili.com'
            }

            # 发送请求
            response = self.session.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0

            print(f"📊 文件大小: {total_size / (1024 * 1024):.2f} MB")

            # 写入文件
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # 显示进度
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(
                                f"\r⏳ 下载进度: {progress:.1f}% ({downloaded / (1024 * 1024):.2f} MB / {total_size / (1024 * 1024):.2f} MB)",
                                end='')

            print(f"\n✅ {file_type}下载完成")
            return True

        except Exception as e:
            print(f"\n❌ 下载{file_type}失败: {e}")
            return False


def format_number(num):
    """格式化数字显示"""
    if num >= 100000000:
        return f"{num / 100000000:.2f}M"
    elif num >= 10000:
        return f"{num / 10000:.2f}万"
    elif num >= 1000:
        return f"{num / 1000:.1f}k"
    else:
        return str(num)


def format_duration(seconds):
    """格式化时长"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_timestamp(timestamp):
    """格式化时间戳"""
    if timestamp == 0:
        return "未知"
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def display_video_detail(video_info, client):
    """显示视频详细信息"""
    print("\n" + "=" * 70)
    print("📹 视频详细信息")
    print("=" * 70)

    print(f"标题: {video_info.get('title', 'N/A')}")
    print(f"BV号: {video_info.get('bvid', 'N/A')}")
    print(f"作者: {video_info.get('owner', {}).get('name', 'N/A')}")
    print(f"作者ID: {video_info.get('owner', {}).get('mid', 'N/A')}")
    print(f"时长: {format_duration(video_info.get('duration', 0))}")
    print(f"发布时间: {format_timestamp(video_info.get('pubdate', 0))}")

    print("\n📊 数据统计")
    print("-" * 30)
    stat = video_info.get('stat', {})
    print(f"播放量: {format_number(stat.get('view', 0))}")
    print(f"弹幕数: {format_number(stat.get('danmaku', 0))}")
    print(f"评论数: {format_number(stat.get('reply', 0))}")
    print(f"收藏数: {format_number(stat.get('favorite', 0))}")
    print(f"投币数: {format_number(stat.get('coin', 0))}")
    print(f"分享数: {format_number(stat.get('share', 0))}")
    print(f"点赞数: {format_number(stat.get('like', 0))}")

    if video_info.get('pic'):
        print(f"\n🖼️ 封面图: {video_info.get('pic')}")

    if video_info.get('desc'):
        desc = video_info.get('desc', '')
        print(f"\n📝 描述: {desc[:80]}..." if len(desc) > 80 else f"\n📝 描述: {desc}")

    # 获取并显示标签
    tags_data = client.get_video_tags(video_info.get('bvid', ''))
    if tags_data:
        tags = tags_data if isinstance(tags_data, list) else [tags_data]
        if tags:
            # 处理字典格式的标签数据
            tag_names = []
            for tag in tags[:5]:
                if isinstance(tag, dict):
                    tag_name = tag.get('tag_name', '')
                    if tag_name:
                        tag_names.append(tag_name)
                elif isinstance(tag, str):
                    tag_names.append(tag)

            if tag_names:
                print(f"\n🏷️ 标签: {', '.join(tag_names)}")


def display_comments(comments_data):
    """显示评论列表"""
    if not comments_data:
        print("\n❌ 没有评论数据")
        return

    comments = comments_data.get('replies', [])
    page_info = comments_data.get('page', {})

    print(f"\n📝 评论列表 (第{page_info.get('num', 1)}页)")
    print("=" * 70)

    for i, comment in enumerate(comments[:10], 1):
        member = comment.get('member', {})
        content = comment.get('content', {}).get('message', '')

        print(f"\n{i}. 用户: {member.get('uname', '未知用户')}")
        print(f"   ID: {member.get('mid', 'N/A')}")
        print(f"   内容: {content[:60]}..." if len(content) > 60 else f"   内容: {content}")
        print(f"   点赞: {format_number(comment.get('like', 0))}")
        print(f"   回复: {format_number(comment.get('rcount', 0))}")
        print(f"   时间: {format_timestamp(comment.get('ctime', 0))}")

    if len(comments) > 10:
        print(f"\n... 还有 {len(comments) - 10} 条评论")


def display_user_info(user_info):
    """显示用户信息"""
    print("\n" + "=" * 60)
    print("👤 用户信息")
    print("=" * 60)

    print(f"用户名: {user_info.get('name', 'N/A')}")
    print(f"用户ID: {user_info.get('mid', 'N/A')}")
    print(f"性别: {user_info.get('sex', 'N/A')}")
    print(f"签名: {user_info.get('sign', 'N/A')}")
    print(f"等级: {user_info.get('level', 0)}")
    print(f"生日: {user_info.get('birthday', 'N/A')}")

    stat = user_info.get('stat', {})
    print(f"\n📊 用户统计")
    print("-" * 30)
    print(f"粉丝数: {format_number(stat.get('follower', 0))}")
    print(f"关注数: {format_number(stat.get('following', 0))}")
    print(f"获赞数: {format_number(stat.get('like_num', 0))}")
    print(f"播放量: {format_number(stat.get('view', 0))}")


def display_user_videos(videos_data):
    """显示用户视频列表"""
    if not videos_data:
        print("\n❌ 没有视频数据")
        return

    videos = videos_data.get('list', {}).get('vlist', [])
    page_info = videos_data.get('page', {})

    print(f"\n📹 用户视频列表 (第{page_info.get('num', 1)}页)")
    print("=" * 70)

    for i, video in enumerate(videos[:10], 1):
        print(f"\n{i}. {video.get('title', 'N/A')[:40]}...")
        print(f"   BV号: {video.get('bvid', 'N/A')}")
        print(f"   时长: {format_duration(video.get('duration', 0))}")
        print(f"   播放: {format_number(video.get('stat', {}).get('view', 0))}")
        print(f"   发布: {format_timestamp(video.get('created', 0))}")

    if len(videos) > 10:
        print(f"\n... 还有 {len(videos) - 10} 个视频")

    total = videos_data.get('page', {}).get('count', 0)
    print(f"\n📊 总视频数: {format_number(total)}")


def save_data_to_file(data, filename):
    """保存数据到JSON文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    full_filename = f"{filename}_{timestamp}.json"

    try:
        with open(full_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 数据已保存到: {full_filename}")
        return full_filename
    except Exception as e:
        print(f"\n❌ 保存文件失败: {e}")
        return None


def get_bvid_from_url(url):
    """从URL中提取BV号，支持多种B站URL格式（包括番剧）

    Args:
        url: B站视频URL 或 番剧URL

    Returns:
        str: BV号 或 None
    """
    if not url:
        return None

    # 处理短链接 b23.tv
    if 'b23.tv' in url:
        try:
            print("🔗 检测到短链接，正在解析...")
            response = requests.get(url, allow_redirects=True, timeout=10)
            url = response.url
            print(f"✅ 解析完成: {url}")
        except Exception as e:
            print(f"❌ 短链接解析失败: {e}")
            return None

    # 检查是否为番剧URL
    if 'bangumi' in url or 'ep' in url or 'ss' in url:
        print("🎬 检测到番剧URL")
        client = BilibiliAPIClient()
        bangumi_info = client.get_bvid_from_bangumi_url(url)
        if bangumi_info:
            return bangumi_info['bvid']
        return None

    # 提取BV号
    bvid_match = re.search(r'BV[a-zA-Z0-9]{10}', url)
    if bvid_match:
        print(f"✅ 成功提取BV号: {bvid_match.group(0)}")
        return bvid_match.group(0)

    # 提取AV号并转换为BV号
    av_match = re.search(r'av(\d+)', url)
    if av_match:
        av_number = av_match.group(1)
        print(f"⚠️  检测到AV号: {av_number}")
        print(f"⚠️  正在转换为BV号...")
        return convert_av_to_bvid(av_number)

    print(f"❌ 无法从URL中提取BV号: {url}")
    return None


def convert_av_to_bvid(av_number):
    """将AV号转换为BV号"""
    try:
        # 使用B站API转换AV号为BV号
        api_url = "https://api.bilibili.com/x/web-interface/view"
        params = {'aid': int(av_number)}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com'
        }

        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                bvid = data.get('data', {}).get('bvid', '')
                if bvid:
                    print(f"✅ 转换成功: BV号 = {bvid}")
                    return bvid

        print(f"❌ 转换失败: {data.get('message', '未知错误')}")
        return None
    except Exception as e:
        print(f"❌ 转换出错: {e}")
        return None


def get_user_id_from_url(url):
    """从URL中提取用户ID"""
    user_id_match = re.search(r'/space.bilibili.com/(\d+)', url)
    if user_id_match:
        return user_id_match.group(1)
    return None


def main():
    print("🛡️ B站API爬虫 - 完整版本（支持番剧下载 + VIP Cookie）🛡️")
    print("=" * 60)
    print("✨ 新增功能：Cookie管理 + Wbi签名 + VIP番剧下载！")

    client = BilibiliAPIClient()

    # 启动时检查Cookie登录状态
    login_status = client.check_login_status()
    if login_status['is_logged_in']:
        vip_badge = "👑 大会员" if login_status['is_vip'] else "普通用户"
        print(f"📌 登录状态: ✅ {login_status['username']} | {vip_badge}")
    else:
        print("📌 登录状态: ❌ 未登录 (VIP番剧下载需要Cookie，请使用功能14设置)")

    print("\n选择功能:")
    print("1. 获取视频详细信息")
    print("2. 获取视频评论")
    print("3. 获取视频弹幕")
    print("4. 获取用户信息")
    print("5. 获取用户视频")
    print("6. 获取用户粉丝")
    print("7. 获取用户关注")
    print("8. 搜索视频")
    print("9. 获取热门视频")
    print("10. 获取排行榜")
    print("11. 下载视频（普通视频）")
    print("12. 下载番剧视频")
    print("13. 获取番剧信息")
    print("14. 🍪 管理Cookie/大会员登录 ▶ 新！(访问VIP番剧必需)")
    print("0. 退出")

    choice = input("\n请选择功能 (0-14): ").strip()

    if choice == '0':
        print("\n👋 感谢使用！")
        return

    elif choice == '1':
        # 获取视频详细信息
        input_str = input("\n请输入视频BV号、AV号、URL或番剧URL: ").strip()

        if input_str.startswith('http') or input_str.startswith('www.') or 'b23.tv' in input_str:
            bvid = get_bvid_from_url(input_str)
        else:
            # 直接输入BV号或AV号
            if input_str.lower().startswith('bv'):
                bvid = input_str
            elif input_str.lower().startswith('av'):
                bvid = convert_av_to_bvid(input_str[2:])
            else:
                bvid = input_str

        if not bvid:
            print("❌ 无法提取BV号")
            return

        print(f"\n🔍 正在获取视频信息: {bvid}")
        video_info = client.get_video_info(bvid)

        if video_info:
            display_video_detail(video_info, client)
            save_data_to_file(video_info, 'video_info')

    elif choice == '2':
        # 获取视频评论
        input_str = input("\n请输入视频BV号、AV号或URL: ").strip()

        if input_str.startswith('http') or input_str.startswith('www.') or 'b23.tv' in input_str:
            bvid = get_bvid_from_url(input_str)
        else:
            if input_str.lower().startswith('bv'):
                bvid = input_str
            elif input_str.lower().startswith('av'):
                bvid = convert_av_to_bvid(input_str[2:])
            else:
                bvid = input_str

        if not bvid:
            print("❌ 无法提取BV号")
            return

        page = input("请输入页码 (默认1): ").strip() or "1"
        page_size = input("每页评论数 (默认20): ").strip() or "20"

        print(f"\n💬 正在获取视频评论: {bvid}")
        comments_data = client.get_video_comments(bvid, int(page), int(page_size))

        if comments_data:
            display_comments(comments_data)
            save_data_to_file(comments_data, 'video_comments')

    elif choice == '3':
        # 获取视频弹幕
        input_str = input("\n请输入视频BV号、AV号或URL: ").strip()

        if input_str.startswith('http') or input_str.startswith('www.') or 'b23.tv' in input_str:
            bvid = get_bvid_from_url(input_str)
        else:
            if input_str.lower().startswith('bv'):
                bvid = input_str
            elif input_str.lower().startswith('av'):
                bvid = convert_av_to_bvid(input_str[2:])
            else:
                bvid = input_str

        if not bvid:
            print("❌ 无法提取BV号")
            return

        print(f"\n💬 正在获取视频弹幕: {bvid}")
        danmaku_data = client.get_video_danmaku(bvid)

        if danmaku_data:
            danmaku_list = danmaku_data if isinstance(danmaku_data, list) else [danmaku_data]
            print(f"\n✅ 成功获取 {len(danmaku_list)} 条弹幕")

            for i, danmaku in enumerate(danmaku_list[:10], 1):
                print(f"{i}. {danmaku}")

            if len(danmaku_list) > 10:
                print(f"... 还有 {len(danmaku_list) - 10} 条弹幕")

            save_data_to_file(danmaku_list, 'video_danmaku')

    elif choice == '4':
        # 获取用户信息
        input_str = input("\n请输入用户ID或空间URL: ").strip()

        if 'space.bilibili.com' in input_str:
            user_id = get_user_id_from_url(input_str)
        else:
            user_id = input_str

        if not user_id:
            print("❌ 无法提取用户ID")
            return

        print(f"\n👤 正在获取用户信息: {user_id}")
        user_info = client.get_user_info(user_id)

        if user_info:
            display_user_info(user_info)
            save_data_to_file(user_info, 'user_info')

    elif choice == '5':
        # 获取用户视频
        input_str = input("\n请输入用户ID或空间URL: ").strip()

        if 'space.bilibili.com' in input_str:
            user_id = get_user_id_from_url(input_str)
        else:
            user_id = input_str

        if not user_id:
            print("❌ 无法提取用户ID")
            return

        page = input("请输入页码 (默认1): ").strip() or "1"
        page_size = input("每页视频数 (默认30): ").strip() or "30"

        print(f"\n📹 正在获取用户视频: {user_id}")
        videos_data = client.get_user_videos(user_id, int(page), int(page_size))

        if videos_data:
            display_user_videos(videos_data)
            save_data_to_file(videos_data, 'user_videos')

    elif choice == '6':
        # 获取用户粉丝
        input_str = input("\n请输入用户ID或空间URL: ").strip()

        if 'space.bilibili.com' in input_str:
            user_id = get_user_id_from_url(input_str)
        else:
            user_id = input_str

        if not user_id:
            print("❌ 无法提取用户ID")
            return

        page = input("请输入页码 (默认1): ").strip() or "1"
        page_size = input("每页粉丝数 (默认20): ").strip() or "20"

        print(f"\n👥 正在获取用户粉丝: {user_id}")
        followers_data = client.get_user_followers(user_id, int(page), int(page_size))

        if followers_data:
            followers = followers_data.get('list', [])
            print(f"\n✅ 成功获取 {len(followers)} 个粉丝")

            for i, follower in enumerate(followers[:10], 1):
                print(f"{i}. {follower.get('uname', '未知用户')} (ID: {follower.get('mid', 'N/A')})")

            if len(followers) > 10:
                print(f"... 还有 {len(followers) - 10} 个粉丝")

            save_data_to_file(followers_data, 'user_followers')

    elif choice == '7':
        # 获取用户关注
        input_str = input("\n请输入用户ID或空间URL: ").strip()

        if 'space.bilibili.com' in input_str:
            user_id = get_user_id_from_url(input_str)
        else:
            user_id = input_str

        if not user_id:
            print("❌ 无法提取用户ID")
            return

        page = input("请输入页码 (默认1): ").strip() or "1"
        page_size = input("每页关注数 (默认20): ").strip() or "20"

        print(f"\n👥 正在获取用户关注: {user_id}")
        following_data = client.get_user_following(user_id, int(page), int(page_size))

        if following_data:
            following = following_data.get('list', [])
            print(f"\n✅ 成功获取 {len(following)} 个关注")

            for i, follow in enumerate(following[:10], 1):
                print(f"{i}. {follow.get('uname', '未知用户')} (ID: {follow.get('mid', 'N/A')})")

            if len(following) > 10:
                print(f"... 还有 {len(following) - 10} 个关注")

            save_data_to_file(following_data, 'user_following')

    elif choice == '8':
        # 搜索视频
        keyword = input("\n请输入搜索关键词: ").strip()

        if not keyword:
            print("❌ 关键词不能为空")
            return

        page = input("请输入页码 (默认1): ").strip() or "1"
        page_size = input("每页结果数 (默认20): ").strip() or "20"

        print(f"\n🔍 正在搜索: {keyword}")
        search_data = client.search_videos(keyword, int(page), int(page_size))

        if search_data:
            results = search_data.get('result', [])
            print(f"\n✅ 找到 {len(results)} 个结果")

            for i, result in enumerate(results[:10], 1):
                video = result if isinstance(result, dict) else {}
                print(f"\n{i}. {video.get('title', 'N/A')[:40]}...")
                print(f"   作者: {video.get('author', 'N/A')}")
                print(f"   播放: {format_number(video.get('stat', {}).get('view', 0))}")
                print(f"   BV号: {video.get('bvid', 'N/A')}")

            if len(results) > 10:
                print(f"... 还有 {len(results) - 10} 个结果")

            save_data_to_file(search_data, 'search_results')

    elif choice == '9':
        # 获取热门视频
        print("\n选择排行榜类型:")
        print("1. 三日排行")
        print("2. 一周排行")
        print("3. 一月排行")

        ranking_choice = input("请选择 (1/2/3): ").strip()

        ranking_types = {'1': 'three_day', '2': 'week', '3': 'month'}
        ranking_type = ranking_types.get(ranking_choice, 'three_day')

        page = input("请输入页码 (默认1): ").strip() or "1"
        page_size = input("每页视频数 (默认20): ").strip() or "20"

        print(f"\n🔥 正在获取热门视频: {ranking_type}")
        ranking_data = client.get_ranking_videos(ranking_type)

        if ranking_data:
            videos = ranking_data.get('list', [])
            print(f"\n✅ 成功获取 {len(videos)} 个热门视频")

            for i, video in enumerate(videos[:10], 1):
                print(f"\n{i}. {video.get('title', 'N/A')[:40]}...")
                print(f"   作者: {video.get('owner', {}).get('name', 'N/A')}")
                print(f"   播放: {format_number(video.get('stat', {}).get('view', 0))}")
                print(f"   BV号: {video.get('bvid', 'N/A')}")

            if len(videos) > 10:
                print(f"... 还有 {len(videos) - 10} 个视频")

            save_data_to_file(ranking_data, 'hot_videos')

    elif choice == '10':
        # 获取排行榜
        print("\n选择排行榜类型:")
        print("1. 三日排行")
        print("2. 一周排行")
        print("3. 一月排行")

        ranking_choice = input("请选择 (1/2/3): ").strip()

        ranking_types = {'1': 'three_day', '2': 'week', '3': 'month'}
        ranking_type = ranking_types.get(ranking_choice, 'three_day')

        print(f"\n🏆 正在获取排行榜: {ranking_type}")
        ranking_data = client.get_ranking_videos(ranking_type)

        if ranking_data:
            videos = ranking_data.get('list', [])
            print(f"\n✅ 成功获取 {len(videos)} 个排行榜视频")

            for i, video in enumerate(videos[:10], 1):
                print(f"\n{i}. {video.get('title', 'N/A')[:40]}...")
                print(f"   排名: {video.get('pts', 0)}")
                print(f"   作者: {video.get('owner', {}).get('name', 'N/A')}")
                print(f"   播放: {format_number(video.get('stat', {}).get('view', 0))}")

            if len(videos) > 10:
                print(f"... 还有 {len(videos) - 10} 个视频")

            save_data_to_file(ranking_data, 'ranking_videos')

    elif choice == '11':
        # 下载视频（普通视频）
        input_str = input("\n请输入视频BV号、AV号或URL: ").strip()

        if input_str.startswith('http') or input_str.startswith('www.') or 'b23.tv' in input_str:
            bvid = get_bvid_from_url(input_str)
        else:
            if input_str.lower().startswith('bv'):
                bvid = input_str
            elif input_str.lower().startswith('av'):
                bvid = convert_av_to_bvid(input_str[2:])
            else:
                bvid = input_str

        if not bvid:
            print("❌ 无法提取BV号")
            return

        print("\n选择视频质量:")
        print("1. 超清 4K")
        print("2. 高清 1080P")
        print("3. 高清 720P")
        print("4. 标清 480P")

        quality_choice = input("请选择质量 (1-4, 默认2): ").strip() or "2"

        quality_map = {'1': 120, '2': 80, '3': 64, '4': 32}
        quality = quality_map.get(quality_choice, 80)

        output_dir = input("请输入输出目录 (默认downloads): ").strip() or "downloads"

        print(f"\n⚠️  注意事项:")
        print(f"⚠️  1. 下载的视频仅供个人学习和研究使用")
        print(f"⚠️  2. 请遵守B站的使用条款和相关法律法规")
        print(f"⚠️  3. 不得用于商业用途或侵犯他人版权")

        confirm = input("\n确认下载? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ 已取消下载")
            return

        success = client.download_video(bvid, output_dir, quality)
        if success:
            print("\n✅ 视频下载成功！")
        else:
            print("\n❌ 视频下载失败！")

    elif choice == '12':
        # 下载番剧视频
        print("\n📺 下载番剧视频")
        print("-" * 50)
        input_str = input("请输入番剧URL (例如: https://www.bilibili.com/bangumi/play/ep3270473 或 ss12345): ").strip()

        print("\n选择视频质量:")
        print("1. 超清 4K")
        print("2. 高清 1080P")
        print("3. 高清 720P")
        print("4. 标清 480P")

        quality_choice = input("请选择质量 (1-4, 默认2): ").strip() or "2"

        quality_map = {'1': 120, '2': 80, '3': 64, '4': 32}
        quality = quality_map.get(quality_choice, 80)

        output_dir = input("请输入输出目录 (默认downloads): ").strip() or "downloads"

        print(f"\n⚠️  注意事项:")
        print(f"⚠️  1. 下载的视频仅供个人学习和研究使用")
        print(f"⚠️  2. 请遵守B站的使用条款和相关法律法规")
        print(f"⚠️  3. 不得用于商业用途或侵犯他人版权")
        print(f"⚠️  4. 番剧下载可能需要会员权限")

        confirm = input("\n确认下载? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ 已取消下载")
            return

        success = client.download_bangumi_video(input_str, output_dir, quality)
        if success:
            print("\n✅ 番剧视频下载成功！")
        else:
            print("\n❌ 番剧视频下载失败！")
            print("💡 提示: 番剧下载可能需要会员权限，请检查您的账号状态")

    elif choice == '13':
        # 获取番剧信息
        print("\n📺 获取番剧信息")
        print("-" * 50)
        input_str = input("请输入番剧URL (例如: https://www.bilibili.com/bangumi/play/ep3270473 或 ss12345): ").strip()

        # 提取ID
        ep_match = re.search(r'ep(\d+)', input_str)
        ss_match = re.search(r'ss(\d+)', input_str)

        if ep_match:
            episode_id = ep_match.group(1)
            print(f"📺 检测到剧集ID: {episode_id}")
            bangumi_info = client.get_bangumi_info_by_epid(episode_id)

            if bangumi_info:
                print(f"\n✅ 成功获取番剧信息")
                print(f"番剧标题: {bangumi_info.get('title', 'N/A')}")

                # 显示所有剧集
                episodes = bangumi_info.get('episodes', [])
                if episodes:
                    print(f"\n📺 剧集列表 (共 {len(episodes)} 集):")
                    for i, ep in enumerate(episodes[:10], 1):
                        print(f"{i}. {ep.get('title', 'N/A')} (BV: {ep.get('bvid', 'N/A')})")

                    if len(episodes) > 10:
                        print(f"... 还有 {len(episodes) - 10} 集")

                save_data_to_file(bangumi_info, 'bangumi_info')

        elif ss_match:
            season_id = ss_match.group(1)
            print(f"📺 检测到季度ID: {season_id}")
            bangumi_info = client.get_bangumi_info_by_seasonid(season_id)

            if bangumi_info:
                print(f"\n✅ 成功获取番剧信息")
                print(f"番剧标题: {bangumi_info.get('title', 'N/A')}")

                episodes = bangumi_info.get('episodes', [])
                if episodes:
                    print(f"\n📺 剧集列表 (共 {len(episodes)} 集):")
                    for i, ep in enumerate(episodes[:10], 1):
                        print(f"{i}. {ep.get('title', 'N/A')} (BV: {ep.get('bvid', 'N/A')})")

                    if len(episodes) > 10:
                        print(f"... 还有 {len(episodes) - 10} 集")

                save_data_to_file(bangumi_info, 'bangumi_info')

        else:
            print("❌ 无法识别番剧URL格式")
            print("支持的格式:")
            print("  - https://www.bilibili.com/bangumi/play/ep3270473")
            print("  - https://www.bilibili.com/bangumi/play/ss12345")
            print("  - 直接输入 ep3270473 或 ss12345")

    elif choice == '14':
        # Cookie/大会员登录管理
        while True:
            print("\n" + "=" * 60)
            print("🍪 Cookie/登录管理")
            print("=" * 60)

            # 显示当前登录状态
            login_status = client.check_login_status()
            if login_status['is_logged_in']:
                vip_badge = "👑 大会员" if login_status['is_vip'] else "普通用户"
                print(f"📌 当前状态: ✅ 已登录 | {login_status['username']} | {vip_badge}")
            else:
                print(f"📌 当前状态: ❌ 未登录")
                if login_status.get('error'):
                    print(f"   ({login_status['error']})")

            print(f"\nCookie管理选项:")
            print("1. 从浏览器Cookie字符串导入")
            print("2. 只设置 SESSDATA（最简方式）")
            print("3. 从本地文件加载")
            print("4. 保存到本地文件（供下次自动加载）")
            print("5. 检查/刷新登录状态")
            print("6. 清除Cookie（登出）")
            print("0. 返回主菜单")

            cookie_choice = input("\n请选择 (0-6): ").strip()

            if cookie_choice == '0':
                break

            elif cookie_choice == '1':
                # 从浏览器Cookie字符串导入
                print("\n📋 如何获取浏览器Cookie:")
                print("   1. 在浏览器中打开B站并登录（确保有大会员）")
                print("   2. 按 F12 打开开发者工具 → Network(网络) 标签")
                print("   3. 刷新页面 → 点击任意请求 → 找到 Request Headers 中的 Cookie")
                print("   4. 右键 → Copy value → 粘贴到下面")
                print("")
                print("   或者更简单的方法：")
                print("   1. F12 → Application(应用) → Storage(存储) → Cookies")
                print("   2. 找到 SESSDATA, b_lsid, DedeUserID 等值")
                print("   3. 复制整行 Cookie 字符串")
                print("")
                print("   关键Cookie说明:")
                print("   - SESSDATA: 登录凭证（最重要，大会员必须）")
                print("   - b_lsid/buvid3: 设备标识（防风控）")
                print("   - DedeUserID: 用户ID")
                print("")

                cookie_str = input("请粘贴Cookie字符串 (或输入0取消): ").strip()
                if cookie_str and cookie_str != '0':
                    client.set_cookies_from_string(cookie_str)
                    # Cookie已自动保存到 bilibili_cookies.json（下次启动自动加载）
                    print("\n🔄 正在验证登录状态...")
                    status = client.check_login_status()
                    if status['is_logged_in']:
                        print(f"✅ 登录成功！用户: {status['username']}")
                        if status['is_vip']:
                            print("👑 大会员权限已激活！可以下载VIP番剧了")
                        else:
                            print("⚠️  当前账号不是大会员，部分VIP番剧可能无法访问")
                    else:
                        print("❌ Cookie无效或已过期，请重新获取")

            elif cookie_choice == '2':
                # 只设置SESSDATA
                print("\n📋 如何获取SESSDATA:")
                print("   1. 浏览器打开B站并登录 → F12 → Application → Cookies")
                print("   2. 找到 bilibili.com 下的 SESSDATA")
                print("   3. 复制其值（一长串字符）")
                print("")

                sessdata = input("请输入SESSDATA值 (或输入0取消): ").strip()
                if sessdata and sessdata != '0':
                    client.set_sessdata(sessdata)
                    # SESSDATA已自动保存到 bilibili_cookies.json（下次启动自动加载）
                    print("\n🔄 正在验证登录状态...")
                    status = client.check_login_status()
                    if status['is_logged_in']:
                        print(f"✅ 登录成功！用户: {status['username']}")
                        if status['is_vip']:
                            print("👑 大会员权限已激活！可以下载VIP番剧了")
                        else:
                            print("⚠️  当前账号不是大会员，部分VIP番剧可能无法访问")
                    else:
                        print("❌ SESSDATA无效或已过期")

            elif cookie_choice == '3':
                filepath = input(
                    "请输入Cookie文件路径 (默认 bilibili_cookies.json): ").strip() or "bilibili_cookies.json"
                if client.load_cookies(filepath):
                    status = client.check_login_status()
                    if status['is_logged_in']:
                        print(f"✅ 登录成功！用户: {status['username']}")
                    else:
                        print("⚠️  文件中的Cookie已失效")

            elif cookie_choice == '4':
                filepath = input("请输入保存路径 (默认 bilibili_cookies.json): ").strip() or "bilibili_cookies.json"
                client.save_cookies(filepath)

            elif cookie_choice == '5':
                print("\n🔄 正在检查登录状态...")
                status = client.check_login_status()
                if status['is_logged_in']:
                    vip_badge = "👑 大会员" if status['is_vip'] else "普通用户"
                    print(f"✅ 已登录 | 用户: {status['username']} | {vip_badge}")
                    print(f"   VIP状态码: {status['vip_status']} | VIP类型: {status['vip_type']}")
                else:
                    print(f"❌ 未登录")
                    if status.get('error'):
                        print(f"   原因: {status['error']}")

            elif cookie_choice == '6':
                confirm = input("确定要清除所有Cookie吗? (y/n): ").strip().lower()
                if confirm == 'y':
                    client.session.cookies.clear()
                    client._cookies_loaded = False
                    # 重新生成buvid
                    client._init_buvid()
                    print("✅ Cookie已清除")
                    # 尝试删除保存的文件
                    try:
                        if os.path.exists('bilibili_cookies.json'):
                            os.remove('bilibili_cookies.json')
                            print("✅ 已删除Cookie文件")
                    except:
                        pass

            else:
                print("❌ 无效的选择")

        # 返回主菜单后，更新BilibiliAPIClient实例以携带新设置的Cookie

    else:
        print("\n❌ 无效的选择！")

    # 显示统计信息
    elapsed_time = time.time() - client.start_time
    print(f"\n📊 运行统计")
    print("-" * 30)
    print(f"总请求数: {client.request_count}")
    print(f"运行时间: {elapsed_time:.2f}秒")
    print(f"平均请求时间: {elapsed_time / max(1, client.request_count):.3f}秒")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n✅ 程序执行完成")
