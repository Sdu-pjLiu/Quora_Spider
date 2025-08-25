#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quora 爬虫脚本
使用 Playwright 自动化登录 Quora 并爬取指定关键词的帖子
"""

import json
import csv
import time
import random
import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright
import logging

# 配置日志
import os

def ensure_directories():
    """确保必要的目录存在"""
    directories = ["log", "data", "result"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"确保目录存在: {directory}")

# 确保所有必要目录存在
ensure_directories()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/quora_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def sanitize_filename(filename):
    """
    清理文件名，移除或替换不安全的字符
    
    Args:
        filename (str): 原始文件名
        
    Returns:
        str: 安全的文件名
    """
    # 移除或替换文件名中的不安全字符
    # Windows 不允许的字符: < > : " | ? * \ /
    # 其他可能引起问题的字符: 空格、制表符等
    unsafe_chars = r'[<>:"|?*\\/\t\n\r]'
    safe_filename = re.sub(unsafe_chars, '_', filename)
    
    # 移除开头和结尾的点号（Windows 不允许）
    safe_filename = safe_filename.strip('.')
    
    # 如果文件名为空，使用默认名称
    if not safe_filename:
        safe_filename = "quora_results"
    
    return safe_filename


class QuoraScraper:
    def __init__(self, headless=False):
        """
        初始化 Quora 爬虫
        
        Args:
            headless (bool): 是否使用无头模式，默认 False 方便调试
        """
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        
    def start_browser(self):
        """启动浏览器"""
        logger.info("启动浏览器...")
        self.playwright = sync_playwright().start()
        
        # 代理配置
        proxy_configs = [
            {'proxy': 'http://192.168.2.116:7890', 'auth': None}
        ]
        
        # 选择第一个代理配置
        proxy_config = proxy_configs[0]
        logger.info(f"使用代理: {proxy_config['proxy']}")
        
        # 尝试使用系统安装的 Google Chrome
        try:
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                executable_path="/usr/bin/google-chrome",
                proxy={
                    'server': proxy_config['proxy'],
                    'username': proxy_config['auth'][0] if proxy_config['auth'] else None,
                    'password': proxy_config['auth'][1] if proxy_config['auth'] else None
                },
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            logger.info("使用系统安装的 Google Chrome 浏览器（带代理）")
        except Exception as e:
            logger.warning(f"无法使用系统 Chrome: {e}")
            logger.info("使用 Playwright 内置的 Chromium（带代理）")
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                proxy={
                    'server': proxy_config['proxy'],
                    'username': proxy_config['auth'][0] if proxy_config['auth'] else None,
                    'password': proxy_config['auth'][1] if proxy_config['auth'] else None
                },
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
        
    def login_quora(self, manual_login=True):
        """
        登录 Quora
        
        Args:
            manual_login (bool): 是否手动登录，默认 True
        """
        try:
            # 尝试加载已保存的登录状态
            if manual_login:
                self.context = self.browser.new_context()
            else:
                try:
                    self.context = self.browser.new_context(storage_state="quora_state.json")
                    logger.info("已加载保存的登录状态")
                except:
                    logger.warning("未找到保存的登录状态，需要手动登录")
                    self.context = self.browser.new_context()
            
            self.page = self.context.new_page()
            
            # 设置用户代理
            self.page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # 访问 Quora 首页
            logger.info("访问 Quora 首页...")
            self.page.goto("https://www.quora.com/", wait_until="networkidle")
            
            if not manual_login:
                # 检查是否已经登录
                try:
                    # 等待页面加载完成
                    self.page.wait_for_timeout(3000)
                    
                    # 检查是否有登录相关的元素
                    login_elements = self.page.query_selector_all("button[data-login], a[href*='login'], div[class*='login']")
                    if not login_elements:
                        logger.info("检测到已登录状态")
                        return True
                    else:
                        logger.info("检测到未登录状态")
                        return False
                        
                except Exception as e:
                    logger.debug(f"检查登录状态时出错: {e}")
                    return False
            
            # 手动登录流程
            logger.info("请在浏览器中手动登录 Quora...")
            input("登录完成后按回车继续...")
            
            # 保存登录状态
            self.context.storage_state(path="quora_state.json")
            logger.info("已保存登录状态到 quora_state.json")
            
            logger.info("登录成功！")
            return True
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False
    
    def search_keyword(self, keyword, target_posts=10):
        """
        搜索关键词并获取帖子列表
        
        Args:
            keyword (str): 搜索关键词
            target_posts (int): 目标帖子数量
            
        Returns:
            list: 帖子列表
        """
        try:
            # 构建搜索 URL
            # 确保关键词正确编码，处理特殊字符
            encoded_keyword = quote(keyword, safe='')
            search_url = f"https://www.quora.com/search?q={encoded_keyword}"
            
            logger.info(f"搜索关键词: {keyword}")
            logger.info(f"访问搜索页面: {search_url}")
            
            self.page.goto(search_url, wait_until="networkidle")
            time.sleep(3)
            
            # 检查是否有搜索结果
            page_content = self.page.content()
            if "no results" in page_content.lower() or "no answers" in page_content.lower():
                logger.warning("没有找到搜索结果")
                return []
            
            # 等待页面完全加载
            logger.info("等待页面完全加载...")
            try:
                self.page.wait_for_timeout(5000)  # 等待5秒
            except:
                pass
            
            # 智能滚动加载更多结果
            logger.info(f"开始智能滚动，目标获取 {target_posts} 个帖子...")
            scroll_count = 0
            max_scrolls = 50  # 最大滚动次数，防止无限循环
            previous_count = 0
            no_new_posts_count = 0  # 连续没有新帖子的次数
            
            while scroll_count < max_scrolls:
                scroll_count += 1
                logger.info(f"第 {scroll_count} 次滚动...")
                
                # 滚动到页面底部
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # 等待内容加载
                time.sleep(random.uniform(2, 4))
                
                # 检查当前找到的帖子数量（不设置目标数量，只统计当前数量）
                current_posts = self.extract_posts_for_count()
                current_count = len(current_posts)
                logger.info(f"当前找到 {current_count} 个帖子")
                
                # 如果已经找到足够的帖子，停止滚动
                if current_count >= target_posts:
                    logger.info(f"已找到 {current_count} 个帖子，达到目标数量 {target_posts}")
                    break
                
                # 检查是否有新帖子
                if current_count > previous_count:
                    no_new_posts_count = 0  # 重置计数器
                    logger.info(f"发现 {current_count - previous_count} 个新帖子")
                else:
                    no_new_posts_count += 1
                    logger.info(f"连续 {no_new_posts_count} 次滚动未发现新帖子")
                
                # 如果连续5次滚动没有新帖子，停止滚动
                if no_new_posts_count >= 5:
                    logger.info(f"连续 {no_new_posts_count} 次滚动未发现新帖子，停止滚动")
                    break
                
                previous_count = current_count
            
            # 检查页面标题和内容长度
            try:
                # 检查页面标题
                page_title = self.page.title()
                logger.info(f"页面标题: {page_title}")
                
                # 检查页面内容长度
                page_content = self.page.content()
                logger.info(f"页面内容长度: {len(page_content)} 字符")
                
            except Exception as e:
                logger.debug(f"页面信息获取失败: {e}")
            
            # 提取帖子链接和标题
            logger.info("提取帖子信息...")
            self.target_posts = target_posts  # 设置目标数量
            posts = self.extract_posts()
            
            logger.info(f"找到 {len(posts)} 个帖子")
            return posts
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def extract_posts(self):
        """
        从搜索结果页面提取帖子信息
        
        Returns:
            list: 帖子信息列表
        """
        posts = []
        
        try:
            # 使用你提供的具体选择器模式
            # 模式1：带div子元素的链接
            pattern1_links = [
                "#mainContent > div > div > div:nth-child(2) > div:nth-child(1) > div > div > div:nth-child(1) > div > span > span > a"
            ]
            
            # 模式2：简单的span链接
            pattern2_links = [
                "#mainContent > div > div > div:nth-child(2) > div:nth-child(4) > span > a"
            ]
            
            # 标题内容选择器
            title_selectors = [
                "#mainContent > div > div > div:nth-child(2) > div:nth-child(1) > div > div > div:nth-child(1) > div > span > span > a > div > div > div > div > span",
                "#mainContent > div > div > div:nth-child(2) > div:nth-child(4) > span > a > div > div > div > div > span"
            ]
            
            # 通用选择器作为备用
            fallback_selectors = [
                "a[href*='/answer/']",
                "a[href*='/question/']",
                "a[href*='/topic/']",
                "div[class*='answer'] a",
                "div[class*='question'] a",
                "div[class*='feed'] a",
                "div[class*='result'] a",
                "div[class*='item'] a",
                "div[class*='content'] a",
                "div[class*='post'] a",
                "div[class*='search'] a",
                "div[class*='list'] a",
                "div[class*='card'] a",
                "div[class*='tile'] a"
            ]
            
            posts = []
            
            # 按顺序爬取所有文章
            logger.info("按顺序爬取文章...")
            
            # 设置目标数量，如果没有指定则默认为10
            target_posts = getattr(self, 'target_posts', 10)
            
            # 按顺序尝试每个位置的文章
            for i in range(1, 100):  # 尝试前100个位置
                # 尝试模式1：带div子元素的链接
                selector1 = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div > div:nth-child(1) > div > span > span > a"
                link1 = self.page.query_selector(selector1)
                
                # 尝试模式2：简单的span链接
                selector2 = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > span > a"
                link2 = self.page.query_selector(selector2)
                
                # 根据模式初始化数据
                follow_text = ""
                follow_count = ""
                views = ""
                likes = ""
                
                # 如果是模式2，尝试点击more按钮并获取观看数量和点赞数量
                if link2:  # 如果是模式2
                    try:
                        # 尝试点击more按钮
                        more_selector = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div:nth-child(1) > div > div.q-click-wrapper.c1nud10e.qu-display--block.qu-tapHighlight--none.qu-cursor--pointer > div.q-box.spacing_log_answer_content.puppeteer_test_answer_content > div > div > div.q-absolute"
                        more_button = self.page.query_selector(more_selector)
                        if more_button:
                            logger.debug(f"位置 {i}: 找到more按钮，尝试点击")
                            more_button.click()
                            time.sleep(1)  # 等待内容加载
                            
                            # 获取观看数量 - 使用你提供的选择器
                            views_selector = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div:nth-child(1) > div > div.q-text.qu-dynamicFontSize--small.qu-pb--tiny.qu-mt--small.qu-color--gray_light.qu-passColorToLinks > div > span > span:nth-child(2)"
                            views_element = self.page.query_selector(views_selector)
                            if views_element:
                                views = views_element.inner_text().strip()
                                logger.debug(f"位置 {i}: 观看数量 = {views}")
                            else:
                                views = "0"
                            
                            # 获取点赞数量
                            likes_selector = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div:nth-child(1) > div > div.q-text.qu-dynamicFontSize--small.qu-pb--tiny.qu-mt--small.qu-color--gray_light.qu-passColorToLinks > div > span > span:nth-child(4) > div > div"
                            likes_element = self.page.query_selector(likes_selector)
                            if likes_element:
                                likes = likes_element.inner_text().strip()
                                logger.debug(f"位置 {i}: 点赞数量 = {likes}")
                            else:
                                likes = "0"
                            

                    except Exception as e:
                        logger.debug(f"模式2处理more按钮时出错: {e}")
                        # 出错时填充默认值
                        if not views:
                            views = "0"
                        if not likes:
                            likes = "0"
                
                # 选择找到的链接
                link = link1 if link1 else link2
                
                if link:
                    try:
                        # 获取链接的href
                        href = link.get_attribute("href")
                        
                        # 获取标题文本
                        title = link.inner_text().strip()
                        
                        # 显示调试信息
                        logger.debug(f"位置 {i}: href={href}, title={title[:100]}...")
                        
                        # 过滤有效的帖子
                        if title and len(title) > 10:
                            # 确保是完整的 URL
                            if href and href.startswith("/"):
                                full_url = "https://www.quora.com" + href
                            elif href:
                                full_url = href
                            else:
                                full_url = ""
                            
                            # 如果是模式1，采集Follow数据
                            if link1:  # 如果是模式1
                                try:
                                    # 尝试第一种Follow选择器
                                    follow_selector = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div > div.q-box.qu-zIndex--action_bar > div > div > div > div:nth-child(1) > button:nth-child(2) > div > div.q-text.qu-display--inline-flex.qu-alignItems--center.qu-overflow--hidden.puppeteer_test_button_text.qu-medium.qu-color--gray.qu-ellipsis.qu-ml--tiny"
                                    follow_element = self.page.query_selector(follow_selector)
                                    if follow_element:
                                        follow_text = follow_element.inner_text().strip()
                                    
                                    # 尝试第一种Follow数字选择器
                                    follow_count_selector = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div > div.q-box.qu-zIndex--action_bar > div > div > div > div:nth-child(1) > button:nth-child(2) > div > div:nth-child(3)"
                                    follow_count_element = self.page.query_selector(follow_count_selector)
                                    if follow_count_element:
                                        follow_count = follow_count_element.inner_text().strip()
                                    
                                    # 如果第一种选择器为空，尝试第二种选择器
                                    if not follow_text:
                                        follow_selector2 = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div.q-box.puppeteer_test_question_component_base > div > div.q-box.qu-zIndex--action_bar > div > div > div > div:nth-child(1) > button > div > div.q-text.qu-display--inline-flex.qu-alignItems--center.qu-overflow--hidden.puppeteer_test_button_text.qu-medium.qu-color--gray.qu-ellipsis.qu-ml--tiny"
                                        follow_element2 = self.page.query_selector(follow_selector2)
                                        if follow_element2:
                                            follow_text = follow_element2.inner_text().strip()
                                            logger.debug(f"位置 {i}: 使用备用Follow选择器获取到文本: {follow_text}")
                                    
                                    if not follow_count:
                                        follow_count_selector2 = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div.q-box.puppeteer_test_question_component_base > div > div.q-box.qu-zIndex--action_bar > div > div > div > div:nth-child(1) > button > div > div:nth-child(3)"
                                        follow_count_element2 = self.page.query_selector(follow_count_selector2)
                                        if follow_count_element2:
                                            follow_count = follow_count_element2.inner_text().strip()
                                            logger.debug(f"位置 {i}: 使用备用Follow选择器获取到数字: {follow_count}")
                                    
                                    # 如果Follow文本为空，填充为0
                                    if not follow_text:
                                        follow_text = "0"
                                        logger.debug(f"位置 {i}: Follow文本为空，填充为0")
                                    
                                    # 如果数值为空，填充为0
                                    if not follow_count:
                                        follow_count = "0"
                                        logger.debug(f"位置 {i}: Follow数值为空，填充为0")
                                        
                                except Exception as e:
                                    logger.debug(f"获取Follow数据时出错: {e}")
                                    # 出错时也填充默认值
                                    if not follow_text:
                                        follow_text = "0"
                                    if not follow_count:
                                        follow_count = "0"
                            
                            posts.append({
                                "title": title,
                                "url": full_url,
                                "follow_text": follow_text,
                                "follow_count": follow_count,
                                "views": views,
                                "likes": likes,
                                "content": ""
                            })
                            logger.info(f"添加第 {len(posts)} 篇文章: {title[:50]}...")
                            if full_url:
                                logger.info(f"文章URL: {full_url}")
                            
                            # 如果已经达到目标数量，停止爬取
                            if len(posts) >= target_posts:
                                logger.info(f"已达到目标数量 {target_posts}，停止爬取")
                                break
                        
                    except Exception as e:
                        logger.debug(f"处理位置 {i} 时出错: {e}")
                        continue
                else:
                    logger.debug(f"位置 {i} 未找到文章")
            
            # 如果按顺序爬取不够，尝试备用方法
            if len(posts) < target_posts:
                logger.info(f"按顺序爬取不够，当前只有 {len(posts)} 篇，目标 {target_posts} 篇，尝试备用方法...")
                
                # 使用通用选择器作为备用
                for selector in fallback_selectors:
                    if len(posts) >= target_posts:
                        break
                    
                    try:
                        links = self.page.query_selector_all(selector)
                        for link in links:
                            if len(posts) >= target_posts:
                                break
                            
                            try:
                                href = link.get_attribute("href")
                                title = link.inner_text().strip()
                                
                                if title and len(title) > 10:
                                    # 确保是完整的 URL
                                    if href and href.startswith("/"):
                                        full_url = "https://www.quora.com" + href
                                    elif href:
                                        full_url = href
                                    else:
                                        full_url = ""
                                    
                                    posts.append({
                                        "title": title,
                                        "url": full_url,
                                        "content": ""
                                    })
                                    logger.info(f"备用方法添加第 {len(posts)} 篇文章: {title[:50]}...")
                            except Exception as e:
                                logger.debug(f"备用方法处理链接时出错: {e}")
                                continue
                    except Exception as e:
                        logger.debug(f"备用选择器 '{selector}' 处理失败: {e}")
                        continue
            
                        # 处理完成，显示结果
            logger.info(f"按顺序爬取完成，共找到 {len(posts)} 篇文章")
            
            return posts
            
        except Exception as e:
            logger.error(f"提取帖子信息失败: {e}")
            return []
    
    def extract_posts_for_count(self):
        """
        仅用于统计当前页面帖子数量，不设置目标数量限制
        
        Returns:
            list: 帖子信息列表
        """
        posts = []
        
        try:
            # 按顺序尝试每个位置的文章
            for i in range(1, 100):  # 尝试前100个位置
                # 尝试模式1：带div子元素的链接
                selector1 = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > div > div > div:nth-child(1) > div > span > span > a"
                link1 = self.page.query_selector(selector1)
                
                # 尝试模式2：简单的span链接
                selector2 = f"#mainContent > div > div > div:nth-child(2) > div:nth-child({i}) > span > a"
                link2 = self.page.query_selector(selector2)
                
                # 选择找到的链接
                link = link1 if link1 else link2
                
                if link:
                    try:
                        # 获取标题文本
                        title = link.inner_text().strip()
                        
                        # 过滤有效的帖子
                        if title and len(title) > 10:
                            posts.append({
                                "title": title,
                                "url": "",
                                "content": ""
                            })
                        
                    except Exception as e:
                        logger.debug(f"统计位置 {i} 时出错: {e}")
                        continue
                else:
                    logger.debug(f"位置 {i} 未找到文章")
            
            return posts
            
        except Exception as e:
            logger.error(f"统计帖子数量失败: {e}")
            return []
    
    def extract_post_content(self, post_info):
        """
        提取单个帖子的详细内容
        
        Args:
            post_info (dict): 帖子信息
            
        Returns:
            dict: 包含内容的帖子信息
        """
        try:
            logger.info(f"提取帖子内容: {post_info['title'][:50]}...")
            
            # 访问帖子页面
            self.page.goto(post_info["url"], wait_until="networkidle")
            time.sleep(random.uniform(2, 4))
            
            # 尝试多种选择器来提取内容
            content_selectors = [
                "div.q-relative.spacing_log_answer_content",
                "div.q-text",
                "div[data-testid='answer_content']",
                "div.Answer",
                "div.q-box",
                "div[class*='answer']",
                "div[class*='content']",
                "div[class*='text']",
                "div[class*='body']",
                "div[class*='description']",
                "div[class*='post']",
                "div[class*='story']"
            ]
            
            content = ""
            for selector in content_selectors:
                try:
                    content_element = self.page.query_selector(selector)
                    if content_element:
                        content = content_element.inner_text().strip()
                        if content and len(content) > 50:
                            break
                except:
                    continue
            
            # 如果没有找到内容，尝试提取问题描述
            if not content:
                try:
                    question_element = self.page.query_selector("div.q-text")
                    if question_element:
                        content = question_element.inner_text().strip()
                except:
                    pass
            
            post_info["content"] = content if content else "内容提取失败"
            logger.info(f"内容提取完成，长度: {len(content)} 字符")
            
            return post_info
            
        except Exception as e:
            logger.error(f"提取帖子内容失败: {e}")
            post_info["content"] = f"内容提取失败: {str(e)}"
            return post_info
    
    def scrape_posts(self, keyword, max_posts=10):
        """
        完整的爬取流程 - 只提取标题和链接
        
        Args:
            keyword (str): 搜索关键词
            max_posts (int): 目标爬取帖子数量
            
        Returns:
            list: 爬取结果
        """
        try:
            # 搜索并获取帖子列表
            posts = self.search_keyword(keyword, max_posts)
            
            if not posts:
                logger.warning("未找到任何帖子")
                return []
            
            # 限制爬取数量
            posts = posts[:max_posts]
            
            # 只返回标题和链接，不提取内容
            logger.info(f"成功获取 {len(posts)} 个帖子的标题和链接")
            return posts
            
        except Exception as e:
            logger.error(f"爬取过程失败: {e}")
            return []
    
    def save_results(self, results, filename="quora_results.json"):
        """
        保存爬取结果到JSON文件
        
        Args:
            results (list): 爬取结果
            filename (str): 保存文件名
        """
        try:
            # 构建完整路径
            filepath = os.path.join("data", filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON结果已保存到 {filepath}")
            
        except Exception as e:
            logger.error(f"保存JSON结果失败: {e}")
    
    def save_results_csv(self, results, filename="quora_results.csv"):
        """
        保存爬取结果到CSV文件
        
        Args:
            results (list): 爬取结果
            filename (str): 保存文件名
        """
        try:
            # 构建完整路径
            filepath = os.path.join("result", filename)
            
            with open(filepath, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                
                # 写入表头
                writer.writerow(["序号", "标题", "链接", "Follow按钮", "Follow数量", "观看数量", "点赞数量"])
                
                # 写入数据
                for i, post in enumerate(results, 1):
                    writer.writerow([
                        i, 
                        post["title"], 
                        post["url"], 
                        post.get("follow_text", ""),
                        post.get("follow_count", ""),
                        post.get("views", ""),
                        post.get("likes", "")
                    ])
            
            logger.info(f"CSV结果已保存到 {filepath}")
            
        except Exception as e:
            logger.error(f"保存CSV结果失败: {e}")
    
    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
        logger.info("浏览器已关闭")


def main():
    """主函数"""
    # 配置参数
    keyword = input("请输入要搜索的关键词: ").strip()
    if not keyword:
        keyword = "amazon acos"  # 默认关键词
    
    max_posts = input("请输入要爬取的帖子数量 (默认10): ").strip()
    max_posts = int(max_posts) if max_posts.isdigit() else 10
    
    # 选择浏览器模式
    headless_input = input("是否使用无头模式？(y/n，默认n): ").strip().lower()
    headless = headless_input == 'y'
    
    # 创建爬虫实例
    scraper = QuoraScraper(headless=headless)
    
    try:
        # 启动浏览器
        scraper.start_browser()
        
        # 尝试使用保存的登录状态，如果失败则手动登录
        if not scraper.login_quora(manual_login=False):
            logger.info("自动登录失败，需要手动登录...")
            if not scraper.login_quora(manual_login=True):
                logger.error("登录失败，程序退出")
                return
        
        # 爬取帖子
        results = scraper.scrape_posts(keyword, max_posts)
        
        if results:
            # 安全处理文件名
            safe_keyword = sanitize_filename(keyword)
            
            # 保存JSON结果
            json_filename = f"quora_{safe_keyword}_{len(results)}posts.json"
            scraper.save_results(results, json_filename)
            
            # 保存CSV结果
            csv_filename = f"quora_{safe_keyword}_{len(results)}posts.csv"
            scraper.save_results_csv(results, csv_filename)
            
            # 打印统计信息
            logger.info(f"爬取完成！共获取 {len(results)} 个帖子")
            print(f"\n=== 爬取结果 ({len(results)} 个帖子) ===")
            for i, post in enumerate(results, 1):
                print(f"{i}. {post['title']}")
                if post['url']:
                    print(f"   链接: {post['url']}")
                if post.get('follow_text'):
                    print(f"   Follow: {post['follow_text']} {post.get('follow_count', '')}")
                if post.get('views') or post.get('likes'):
                    print(f"   观看: {post.get('views', '')} | 点赞: {post.get('likes', '')}")
            print("=" * 80)
            print(f"结果已保存到:")
            print(f"  JSON: data/{json_filename}")
            print(f"  CSV:  result/{csv_filename}")
        else:
            logger.warning("未获取到任何结果")
    
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
