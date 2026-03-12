# DOI Literature Extractor

通过 DOI 号提取期刊文章关键信息并存储到数据库的工具。

## 功能

- 🔍 通过 DOI 从 Crossref API 获取论文元数据
- 🕷️ **网页摘要爬取** - 当 Crossref 没有摘要时，自动从期刊官网爬取
- 🤖 **Selenium 备用方案** - 处理 Cloudflare 保护的网站
- 📄 提取关键信息：标题、作者、期刊、摘要、引用数等
- 💾 数据库存储（SQLite/PostgreSQL）
- 🌐 Web API 支持
- 🔎 文献搜索功能

## 支持的出版商

网页摘要爬取支持以下出版商（HTTP + Selenium 双方案）：

| 出版商 | 域名 | HTTP | Selenium |
|--------|------|------|----------|
| Nature/Springer | nature.com | ✅ | ✅ |
| Elsevier | sciencedirect.com | ✅ | ✅ |
| IEEE | ieeexplore.ieee.org | ✅ | ✅ |
| Wiley | wiley.com | ✅ | ✅ |
| ACS | pubs.acs.org | ✅ | ✅ |
| Oxford (OUP) | oup.com | ✅ | ✅ |
| 其他 | - | ⚠️ 通用 | ❌ |

## 安装

本项目使用 **uv** 进行环境管理。

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目后，进入项目目录
cd doi_literature_extractor

# 创建虚拟环境
uv venv

# 激活环境
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 基础安装（仅HTTP爬取）
uv pip install -e .

# 带 Selenium 支持（推荐，可处理Cloudflare）
uv pip install -e ".[web]"

# 带 Web API 支持
uv pip install -e ".[api]"

# 完整安装
uv pip install -e ".[full]"
```

### 安装 ChromeDriver（Selenium 需要）

```bash
# macOS
brew install chromedriver

# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# 或使用 webdriver-manager
pip install webdriver-manager
```

## 配置

创建 `.env` 文件：

```env
# 数据库配置（可选，默认使用SQLite）
DATABASE_URL=sqlite+aiosqlite:///./doi_literature.db
```

## 使用方法

### 命令行工具

```bash
# 初始化数据库
uv run doi-extractor init

# 提取单篇文献（自动启用网页摘要爬取）
uv run doi-extractor extract "10.1038/s41586-021-03819-2"

# 禁用网页摘要爬取（仅用Crossref）
uv run doi-extractor extract "10.1038/s41586-021-03819-2" --no-web-extraction

# 批量提取（从文件，每行一个DOI）
uv run doi-extractor batch dois.txt

# 搜索数据库
uv run doi-extractor search "machine learning"
```

### Web API

```bash
# 启动API服务器
uv run doi-extractor-api

# 或使用 uvicorn
uv run uvicorn doi_extractor.api:app --reload
```

API端点：

- `POST /extract` - 提取单篇文献
- `POST /extract/batch` - 批量提取
- `GET /papers` - 获取文献列表
- `GET /papers/{doi}` - 获取单篇文献
- `GET /search?q=keyword` - 搜索文献

示例：

```bash
# 提取文献
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"doi": "10.1038/s41586-021-03819-2"}'

# 搜索文献
curl "http://localhost:8000/search?q=machine+learning"
```

### Python API

```python
import asyncio
from doi_extractor.extractor import extract_and_store

async def main():
    result = await extract_and_store(
        doi="10.1038/s41586-021-03819-2",
        enable_web_extraction=True  # 启用网页摘要爬取
    )
    print(result)

asyncio.run(main())
```

## 网页摘要爬取原理

1. **HTTP 请求阶段**（优先）：
   - 首先尝试从 Crossref API 获取摘要
   - 如果 Crossref 没有摘要，解析 DOI 获取文章官网 URL
   - 根据域名识别出版商
   - 使用对应的 CSS 选择器爬取摘要
   - 支持 meta 标签和 HTML 内容提取

2. **Selenium 备用阶段**（当 HTTP 被拦截时）：
   - 遇到 403 错误或 Cloudflare 验证页面时自动切换
   - 启动 Chrome 浏览器模拟真实用户访问
   - 等待页面加载完成（包括 JavaScript 渲染）
   - 提取摘要内容
   - 关闭浏览器

3. **防封禁措施**：
   - 添加随机延迟（0.5-2秒）
   - 模拟真实浏览器 User-Agent
   - Selenium 禁用自动化检测特征

## 数据字段

| 字段 | 说明 |
|------|------|
| doi | DOI号 |
| title | 标题 |
| authors | 作者列表（JSON格式） |
| journal | 期刊名称 |
| published | 发表日期 |
| abstract | 摘要（Crossref或网页爬取） |
| url | 文章URL |
| citation_count | 引用次数 |
| issn/eissn | ISSN号 |

## 项目结构

```
doi_literature_extractor/
├── doi_extractor/
│   ├── __init__.py
│   ├── cli.py              # 命令行接口
│   ├── api.py              # FastAPI Web API
│   ├── extractor.py        # 核心提取逻辑
│   ├── parsers/            # 解析器模块
│   │   ├── __init__.py
│   │   ├── crossref_parser.py      # Crossref API 解析
│   │   └── abstract_extractor.py   # ⭐ 网页摘要爬取（HTTP + Selenium）
│   └── db/                 # 数据库模块
│       ├── __init__.py
│       ├── models.py       # SQLAlchemy 模型
│       └── storage.py      # 数据库操作
├── pyproject.toml          # 项目配置
├── README.md               # 使用文档
└── .env.example            # 环境变量示例
```

## 依赖

- Python >= 3.9
- httpx - HTTP客户端
- SQLAlchemy - ORM
- aiosqlite - SQLite异步支持
- beautifulsoup4 - HTML解析
- requests - HTTP请求
- pydantic - 数据验证
- click - 命令行工具
- selenium - 浏览器自动化（可选）
- fastapi - Web API（可选）
- uvicorn - ASGI服务器（可选）

## 许可证

MIT
