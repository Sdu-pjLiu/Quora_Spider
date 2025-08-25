# Quora 爬虫项目

这是一个基于 Playwright 的 Quora 爬虫工具，用于爬取指定关键词搜索结果的帖子数据。

## 功能特性

- 🔍 **关键词搜索**: 支持任意关键词搜索，自动处理特殊字符
- 🔐 **自动登录**: 支持保存和复用登录会话，避免重复登录
- 📊 **智能数据采集**: 根据帖子类型自动采集不同数据
- 📁 **结构化输出**: 自动创建目录结构，输出JSON和CSV格式
- 🎯 **精确控制**: 可指定爬取帖子数量，智能滚动加载

## 数据采集逻辑

### 帖子类型识别
- **模式1 (问题帖子)**: 没有回答的问题，采集 Follow 按钮文本和数量
- **模式2 (回答帖子)**: 有回答的帖子，采集观看数量和点赞数量

### 采集字段说明
| 字段 | 说明 | 数据来源 |
|------|------|----------|
| 序号 | 爬取顺序编号 | 自动生成 |
| 标题 | 帖子标题 | 所有帖子 |
| 链接 | 完整URL链接 | 所有帖子 |
| Follow按钮 | Follow按钮文本 | 仅模式1 |
| Follow数量 | Follow按钮后的数字 | 仅模式1 |
| 观看数量 | 原始文本(如"191 views") | 仅模式2 |
| 点赞数量 | 原始文本(如"View 4 upvotes") | 仅模式2 |

### 默认值处理
- 如果某个字段采集为空，自动填充为 "0"
- 观看数量和点赞数量保留原始文本格式

## 安装要求

### 系统要求
- Python 3.7+
- Google Chrome 浏览器 (推荐) 或 Playwright 内置浏览器
- 网络连接 (支持代理配置)

### 依赖安装
```bash
# 安装 Playwright
pip install playwright

# 安装浏览器二进制文件
playwright install chromium
```

## 项目结构

```
pachong/
├── quora_scraper.py    # 主爬虫脚本
├── README.md          # 项目说明文档
├── .gitignore         # Git忽略文件
├── log/               # 日志文件目录 (自动创建)
│   └── quora_scraper.log
├── data/              # JSON数据文件目录 (自动创建)
│   └── quora_results_关键词.json
├── result/            # CSV结果文件目录 (自动创建)
│   └── quora_results_关键词.csv
└── quora_state.json   # 登录会话保存文件
```

## 使用方法

### 基本使用
```bash
python3 quora_scraper.py
```

### 交互式配置
运行脚本后，按提示输入：
1. **关键词**: 要搜索的关键词
2. **帖子数量**: 要爬取的帖子数量
3. **浏览器模式**: 选择有头/无头模式
4. **登录方式**: 选择自动/手动登录

### 示例输出
```
请输入要搜索的关键词: python
请输入要爬取的帖子数量: 10
是否使用无头模式? (y/n): y

开始爬取...
找到 10 个帖子
爬取完成！

输出文件:
  JSON: data/quora_results_python.json
  CSV:  result/quora_results_python.csv
```

## 配置说明

### 代理配置
在 `quora_scraper.py` 中修改 `proxy_configs` 列表：
```python
proxy_configs = [
    {'proxy': 'http://your-proxy:port', 'auth': None},
    {'proxy': 'http://proxy-with-auth:port', 'auth': ('username', 'password')}
]
```

### 浏览器配置
- **系统Chrome**: 优先使用系统安装的Google Chrome
- **内置Chromium**: 如果系统Chrome不可用，自动切换到Playwright内置浏览器

## 输出格式

### JSON格式
```json
[
  {
    "title": "帖子标题",
    "url": "https://www.quora.com/...",
    "follow_text": "Follow",
    "follow_count": "1.2K",
    "views": "191 views",
    "likes": "View 4 upvotes",
    "content": ""
  }
]
```

### CSV格式
```csv
序号,标题,链接,Follow按钮,Follow数量,观看数量,点赞数量
1,帖子标题,https://www.quora.com/...,Follow,1.2K,0,0
2,另一个标题,https://www.quora.com/...,0,0,191 views,View 4 upvotes
```

## 技术特性

### 智能滚动
- 自动检测新内容加载
- 达到目标数量时停止
- 连续5次无新内容时停止

### 错误处理
- 网络异常自动重试
- 元素定位失败时使用备用选择器
- 数据采集失败时使用默认值

### 会话管理
- 自动保存登录状态到 `quora_state.json`
- 下次运行时自动恢复登录状态
- 支持手动登录模式

## 注意事项

1. **遵守网站规则**: 请合理使用，避免过于频繁的请求
2. **网络环境**: 确保网络连接稳定，必要时配置代理
3. **登录状态**: 首次使用需要手动登录，后续可自动登录
4. **数据准确性**: 由于网站结构可能变化，数据采集可能受影响

## 故障排除

### 常见问题

**Q: 提示 "No module named 'playwright'"**
A: 运行 `pip install playwright` 安装依赖

**Q: 登录失败**
A: 选择手动登录模式，在浏览器中完成登录

**Q: 爬取数量不足**
A: 检查网络连接，尝试增加滚动等待时间

### 日志查看
查看 `log/quora_scraper.log` 获取详细的执行日志和错误信息。


## 许可证

本项目仅供学习和研究使用，请遵守相关法律法规和网站使用条款。
