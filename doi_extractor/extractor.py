"""Core DOI extraction functionality with web scraping support."""
import asyncio
import logging
from typing import Optional, Dict, Any, List
import httpx

from .parsers.crossref_parser import CrossrefParser
from .parsers.abstract_extractor import fetch_abstract_by_doi
from .db.storage import check_paper_exists, store_papers, create_tables

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"


class DOIExtractor:
    """DOI文献提取器 - 支持Crossref API和网页爬取"""
    
    def __init__(self, enable_web_extraction: bool = True):
        """
        初始化DOI提取器
        
        Args:
            enable_web_extraction: 是否启用网页摘要爬取
        """
        self.parser = CrossrefParser()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.enable_web_extraction = enable_web_extraction
    
    async def close(self):
        await self.client.aclose()
    
    async def extract_by_doi(self, doi: str, skip_existing: bool = True, 
                            force_web_extraction: bool = False) -> Optional[Dict[str, Any]]:
        """
        通过DOI提取文献信息
        
        Args:
            doi: DOI号
            skip_existing: 如果数据库中已存在则跳过
            force_web_extraction: 强制使用网页爬取（即使Crossref有摘要）
            
        Returns:
            提取的文献信息字典，失败返回None
        """
        # 检查是否已存在
        if skip_existing and await check_paper_exists(doi):
            logger.info(f"Paper with DOI {doi} already exists, skipping")
            return None
        
        try:
            # 调用Crossref API
            url = f"{CROSSREF_API_URL}/{doi}"
            headers = {
                "User-Agent": "DOILiteratureExtractor/1.0 (mailto:your.email@example.com)"
            }
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if "message" not in data:
                logger.error(f"Invalid response from Crossref API for DOI {doi}")
                return None
            
            # 解析Crossref数据
            paper = self.parser.parse(data["message"])
            
            if not paper:
                logger.warning(f"Failed to parse paper data for DOI {doi}")
                return None
            
            # 网页摘要爬取
            if self.enable_web_extraction:
                has_crossref_abstract = bool(paper.get("abstract"))
                
                # 如果Crossref没有摘要，或强制要求网页爬取
                if not has_crossref_abstract or force_web_extraction:
                    logger.info(f"Attempting web extraction for DOI: {doi}")
                    
                    # 使用线程池运行同步的网页爬取
                    loop = asyncio.get_event_loop()
                    article_url, extracted_abstract = await loop.run_in_executor(
                        None, fetch_abstract_by_doi, doi
                    )
                    
                    # 检查是否成功提取到有效摘要
                    if (extracted_abstract and 
                        not extracted_abstract.startswith("Abstract not found") and
                        not extracted_abstract.startswith("Error") and
                        not extracted_abstract.startswith("Selenium") and
                        len(extracted_abstract) > 50):
                        
                        paper["abstract"] = extracted_abstract
                        
                        # 如果论文没有URL，使用提取到的URL
                        if article_url and not paper.get("url"):
                            paper["url"] = article_url
                        
                        logger.info(f"Successfully extracted abstract from web for DOI: {doi}")
                    else:
                        logger.debug(f"Web extraction failed for DOI {doi}: {extracted_abstract}")
                        if not has_crossref_abstract:
                            paper["abstract"] = "No abstract available."
            
            logger.info(f"Successfully extracted paper: {paper.get('title', 'N/A')[:50]}...")
            return paper
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for DOI {doi}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error extracting DOI {doi}: {e}")
            return None
    
    async def extract_batch(self, dois: List[str], skip_existing: bool = True) -> List[Dict]:
        """
        批量提取DOI
        
        Args:
            dois: DOI列表
            skip_existing: 跳过已存在的
            
        Returns:
            成功提取的文献列表
        """
        papers = []
        
        for doi in dois:
            paper = await self.extract_by_doi(doi.strip(), skip_existing=skip_existing)
            if paper:
                papers.append(paper)
        
        return papers


async def extract_and_store(doi: str, enable_web_extraction: bool = True) -> Optional[Dict]:
    """
    提取DOI并存储到数据库
    
    Args:
        doi: DOI号
        enable_web_extraction: 启用网页摘要爬取
        
    Returns:
        提取结果
    """
    # 确保数据库表存在
    await create_tables()
    
    extractor = DOIExtractor(enable_web_extraction=enable_web_extraction)
    
    try:
        paper = await extractor.extract_by_doi(doi)
        
        if paper:
            result = await store_papers([paper])
            return {
                "success": True,
                "paper": paper,
                "database_result": result
            }
        else:
            return {
                "success": False,
                "error": "Failed to extract paper"
            }
    finally:
        await extractor.close()
