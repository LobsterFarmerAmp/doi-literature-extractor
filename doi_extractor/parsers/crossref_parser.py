"""Parser for Crossref API response data."""
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CrossrefParser:
    """Parser for Crossref API response data."""
    
    def parse(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析Crossref API返回的单个条目
        
        Args:
            item: Crossref API返回的单个条目
            
        Returns:
            标准化的论文字典，解析失败返回None
        """
        if not item or not isinstance(item, dict):
            logger.warning("Invalid item format, skipping")
            return None
        
        try:
            # 提取DOI（必需字段）
            doi = item.get("DOI")
            if not doi:
                logger.warning("Item missing DOI, skipping")
                return None
            
            # 提取标题（必需字段）
            title = None
            if "title" in item and item["title"]:
                title = item["title"][0]
            else:
                logger.warning(f"Item with DOI {doi} missing title, skipping")
                return None
            
            # 提取作者
            authors = []
            if "author" in item and item["author"]:
                for author in item["author"]:
                    name_parts = []
                    if "given" in author:
                        name_parts.append(author["given"])
                    if "family" in author:
                        name_parts.append(author["family"])
                    if name_parts:
                        authors.append(" ".join(name_parts))
            
            # 提取发表日期
            published = None
            if "published" in item and "date-parts" in item["published"]:
                date_parts = item["published"]["date-parts"][0]
                if len(date_parts) >= 3:
                    published = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                elif len(date_parts) >= 2:
                    published = f"{date_parts[0]}-{date_parts[1]:02d}-01"
                elif len(date_parts) >= 1:
                    published = f"{date_parts[0]}-01-01"
            
            # 提取期刊和ISSN
            journal = None
            issn = None
            eissn = None
            
            if "container-title" in item and item["container-title"]:
                journal = item["container-title"][0]
            
            # 提取ISSN
            if "ISSN" in item and item["ISSN"]:
                if "issn-type" in item and item["issn-type"]:
                    for issn_info in item["issn-type"]:
                        if "value" in issn_info and "type" in issn_info:
                            if issn_info["type"] == "print":
                                issn = issn_info["value"]
                            elif issn_info["type"] == "electronic":
                                eissn = issn_info["value"]
                else:
                    issns = item["ISSN"]
                    if len(issns) >= 1:
                        issn = issns[0]
                    if len(issns) >= 2:
                        eissn = issns[1]
            
            # 提取摘要
            abstract = item.get("abstract")
            
            # 提取URL
            url = item.get("URL")
            
            # 提取引用次数
            citation_count = item.get("is-referenced-by-count", 0)
            
            # 创建标准化的论文字典
            paper = {
                "source": "crossref",
                "doi": doi,
                "title": title,
                "authors": json.dumps(authors) if authors else None,
                "authors_list": json.dumps(authors) if authors else None,
                "published": published,
                "journal": journal,
                "abstract": abstract,
                "url": url,
                "issn": issn,
                "eissn": eissn,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "citation_count": citation_count,
            }
            
            return paper
            
        except Exception as e:
            logger.error(f"Error parsing Crossref item: {e}", exc_info=True)
            return None
