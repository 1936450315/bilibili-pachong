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
from datetime import datetime
import os
import sys
import urllib.parse
from pathlib import Path


class BilibiliAPIClient:
    """B站API客户端类"""

    def __init__(self):
        self.base_url = "https://api.bilibili.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
        self.request_count = 0
        self.start_time = time.time()

    def _make_request(self, api_url, params=None):
        """发送API请求"""
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

                if data.get('code') == 0:
                    print(f"✅ 请求成功")
                    return data.get('data', {})
                else:
                    print(f"❌ API错误: {data.get('message', '未知错误')}")
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
        """获取番剧播放地址（番剧专用）

        Args:
            ep_id: 剧集ID
            cid: 视频CID
            quality: 视频质量 (80-高清, 64-超清, 32-高清, 16-标清)
        """
        print(f"🎬 正在获取番剧播放地址 (ep_id: {ep_id}, cid: {cid})")

        # 使用番剧专用的播放地址API
        api_url = f"{self.base_url}/pgc/player/web/playurl"
        params = {
            'ep_id': ep_id,
            'cid': cid,
            'qn': quality,
            'fnval': 16,  # 获取DASH格式
            'fnver': 0,
            'fourk': 1
        }

        return self._make_request(api_url, params)

    def get_bangumi_playurl_by_bvid(self, bvid, cid, quality=80):
        """通过BV号获取番剧播放地址（番剧专用）

        Args:
            bvid: 视频BV号
            cid: 视频CID
            quality: 视频质量 (80-高清, 64-超清, 32-高清, 16-标清)
        """
        print(f"🎬 正在获取番剧播放地址 (bvid: {bvid}, cid: {cid})")

        # 使用番剧专用的播放地址API
        api_url = f"{self.base_url}/pgc/player/web/playurl"
        params = {
            'bvid': bvid,
            'cid': cid,
            'qn': quality,
            'fnval': 16,  # 获取DASH格式
            'fnver': 0,
            'fourk': 1
        }

        return self._make_request(api_url, params)

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
            # 备用方案：使用普通API
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

                # 提示用户需要合并
                print(f"\n💡 提示: 视频和音频已分别下载")
                print(f"💡 视频文件: {video_filename}")
                print(f"💡 音频文件: {audio_filename}")
                print(
                    f"💡 可以使用FFmpeg合并: ffmpeg -i {video_filename} -i {audio_filename} -c copy {os.path.join(output_dir, title)}.mp4")
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

                # 提示用户需要合并
                print(f"\n💡 提示: 视频和音频已分别下载")
                print(f"💡 视频文件: {video_filename}")
                print(f"💡 音频文件: {audio_filename}")
                print(
                    f"💡 可以使用FFmpeg合并: ffmpeg -i {video_filename} -i {audio_filename} -c copy {os.path.join(output_dir, title)}.mp4")
            else:
                return False
        else:
            # 如果没有单独的音频，视频文件就是完整的
            final_filename = os.path.join(output_dir, f"{title}.mp4")
            os.rename(video_filename, final_filename)
            print(f"✅ 视频下载完成: {final_filename}")

        return True

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
    print("🛡️ B站API爬虫 - 完整版本（支持番剧下载）🛡️")
    print("=" * 50)
    print("✨ 新增功能：支持番剧URL处理和下载！")

    client = BilibiliAPIClient()

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
    print("0. 退出")

    choice = input("\n请选择功能 (0-13): ").strip()

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