"""Command line interface for DOI Literature Extractor."""
import asyncio
import logging
import sys
from pathlib import Path

import click

from .extractor import extract_and_store, DOIExtractor
from .db.storage import create_tables, get_paper_by_doi, search_papers, setup_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.option('--database', '-d', help='数据库URL')
def cli(verbose, database):
    """DOI Literature Extractor - 通过DOI提取期刊文章信息"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if database:
        setup_db(database)


@cli.command()
@click.argument('doi')
@click.option('--no-web-extraction', is_flag=True, help='禁用网页摘要爬取')
@click.option('--force', is_flag=True, help='强制重新提取（即使已存在）')
def extract(doi, no_web_extraction, force):
    """通过DOI提取单篇文献"""
    asyncio.run(_extract_async(doi, not no_web_extraction, force))


async def _extract_async(doi, enable_web_extraction, force):
    await create_tables()
    
    # 检查是否已存在
    if not force:
        existing = await get_paper_by_doi(doi)
        if existing:
            click.echo(f"文献已存在: {existing.title}")
            click.echo(f"期刊: {existing.journal}")
            click.echo(f"DOI: {existing.doi}")
            if existing.abstract and len(existing.abstract) > 50:
                click.echo(f"摘要: ✓ ({len(existing.abstract)} 字符)")
            return
    
    click.echo(f"正在提取 DOI: {doi}...")
    if enable_web_extraction:
        click.echo("网页摘要爬取: 已启用")
    
    result = await extract_and_store(doi, enable_web_extraction=enable_web_extraction)
    
    if result and result.get("success"):
        paper = result["paper"]
        click.echo("\n✅ 提取成功!")
        click.echo(f"标题: {paper.get('title')}")
        click.echo(f"作者: {paper.get('authors')}")
        click.echo(f"期刊: {paper.get('journal')}")
        click.echo(f"发表日期: {paper.get('published')}")
        click.echo(f"引用次数: {paper.get('citation_count', 0)}")
        
        # 显示摘要信息
        abstract = paper.get('abstract', '')
        if abstract and len(abstract) > 50:
            click.echo(f"摘要: ✓ ({len(abstract)} 字符)")
            if len(abstract) > 200:
                click.echo(f"  {abstract[:200]}...")
            else:
                click.echo(f"  {abstract}")
        else:
            click.echo("摘要: ✗ 未获取")
    else:
        click.echo("\n❌ 提取失败")
        if result and result.get('error'):
            click.echo(f"错误: {result['error']}")


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--no-web-extraction', is_flag=True, help='禁用网页摘要爬取')
def batch(file_path, no_web_extraction):
    """从文件批量提取DOI（每行一个DOI）"""
    asyncio.run(_batch_async(file_path, not no_web_extraction))


async def _batch_async(file_path, enable_web_extraction):
    # 读取DOI列表
    with open(file_path, 'r') as f:
        dois = [line.strip() for line in f if line.strip()]
    
    click.echo(f"从文件读取了 {len(dois)} 个DOI")
    if enable_web_extraction:
        click.echo("网页摘要爬取: 已启用")
    
    await create_tables()
    
    extractor = DOIExtractor(enable_web_extraction=enable_web_extraction)
    
    try:
        papers = await extractor.extract_batch(dois)
        
        if papers:
            from .db.storage import store_papers
            result = await store_papers(papers)
            
            # 统计摘要获取情况
            with_abstract = sum(1 for p in papers if p.get('abstract') and len(p['abstract']) > 50)
            
            click.echo(f"\n✅ 批量提取完成!")
            click.echo(f"成功提取: {len(papers)} 篇")
            click.echo(f"有摘要: {with_abstract} 篇")
            click.echo(f"数据库插入: {result['inserted']} 篇")
            click.echo(f"数据库更新: {result['updated']} 篇")
        else:
            click.echo("\n⚠️ 没有成功提取任何文献")
    finally:
        await extractor.close()


@cli.command()
@click.argument('query')
@click.option('--limit', '-l', default=20, help='返回结果数量限制')
def search(query, limit):
    """搜索数据库中的文献"""
    asyncio.run(_search_async(query, limit))


async def _search_async(query, limit):
    await create_tables()
    
    papers = await search_papers(query, limit=limit)
    
    if not papers:
        click.echo("未找到匹配的文献")
        return
    
    click.echo(f"\n找到 {len(papers)} 篇文献:\n")
    
    for i, paper in enumerate(papers, 1):
        click.echo(f"{i}. {paper.title}")
        click.echo(f"   DOI: {paper.doi}")
        click.echo(f"   期刊: {paper.journal or 'N/A'}")
        if paper.abstract:
            click.echo(f"   摘要: ✓ ({len(paper.abstract)} 字符)")
        click.echo()


@cli.command()
def init():
    """初始化数据库"""
    asyncio.run(create_tables())
    click.echo("✅ 数据库初始化完成")


def main():
    cli()


if __name__ == '__main__':
    main()
