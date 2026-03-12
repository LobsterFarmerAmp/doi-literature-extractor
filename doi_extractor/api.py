"""FastAPI web API for DOI Literature Extractor."""
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .extractor import DOIExtractor
from .db.storage import (
    create_tables, get_paper_by_doi, search_papers, 
    get_all_papers, store_papers, check_paper_exists
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DOI Literature Extractor API",
    description="通过DOI提取期刊文章关键信息",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 数据模型
class PaperResponse(BaseModel):
    id: int
    doi: str
    title: Optional[str]
    authors: Optional[str]
    journal: Optional[str]
    published: Optional[str]
    abstract: Optional[str]
    citation_count: int = 0
    url: Optional[str]
    chinese_title: Optional[str]
    chinese_abstract: Optional[str]
    
    class Config:
        from_attributes = True


class ExtractRequest(BaseModel):
    doi: str = Field(..., description="DOI号")
    enable_web_extraction: bool = Field(True, description="启用网页摘要爬取")
    skip_existing: bool = Field(True, description="如果已存在则跳过")


class ExtractResponse(BaseModel):
    success: bool
    message: str
    paper: Optional[dict] = None


class BatchExtractRequest(BaseModel):
    dois: List[str] = Field(..., description="DOI列表")
    enable_web_extraction: bool = Field(True, description="启用网页摘要爬取")


# 生命周期事件
@app.on_event("startup")
async def startup():
    await create_tables()
    logger.info("Database initialized")


# API端点
@app.get("/")
async def root():
    return {
        "name": "DOI Literature Extractor API",
        "version": "0.1.0",
        "endpoints": [
            "/extract - 提取单篇文献",
            "/extract/batch - 批量提取",
            "/papers - 获取文献列表",
            "/papers/{doi} - 获取单篇文献",
            "/search - 搜索文献"
        ]
    }


@app.post("/extract", response_model=ExtractResponse)
async def extract_paper(request: ExtractRequest):
    """通过DOI提取单篇文献"""
    
    # 检查是否已存在
    if request.skip_existing and await check_paper_exists(request.doi):
        paper = await get_paper_by_doi(request.doi)
        return ExtractResponse(
            success=True,
            message="Paper already exists",
            paper=paper.to_dict() if paper else None
        )
    
    extractor = DOIExtractor(enable_web_extraction=request.enable_web_extraction)
    
    try:
        paper = await extractor.extract_by_doi(request.doi, skip_existing=False)
        
        if paper:
            result = await store_papers([paper])
            return ExtractResponse(
                success=True,
                message="Paper extracted successfully",
                paper=paper
            )
        else:
            return ExtractResponse(
                success=False,
                message="Failed to extract paper"
            )
    finally:
        await extractor.close()


@app.post("/extract/batch")
async def extract_batch(request: BatchExtractRequest):
    """批量提取文献"""
    extractor = DOIExtractor(enable_web_extraction=request.enable_web_extraction)
    
    try:
        papers = await extractor.extract_batch(request.dois)
        
        if papers:
            result = await store_papers(papers)
            return {
                "success": True,
                "extracted": len(papers),
                "inserted": result["inserted"],
                "updated": result["updated"]
            }
        else:
            return {
                "success": False,
                "extracted": 0,
                "message": "No papers extracted"
            }
    finally:
        await extractor.close()


@app.get("/papers", response_model=List[PaperResponse])
async def list_papers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """获取文献列表"""
    papers = await get_all_papers(limit=limit, offset=offset)
    return papers


@app.get("/papers/{doi:path}", response_model=PaperResponse)
async def get_paper(doi: str):
    """通过DOI获取文献"""
    paper = await get_paper_by_doi(doi)
    
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    return paper


@app.get("/search")
async def search_papers_api(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, ge=1, le=100)
):
    """搜索文献"""
    papers = await search_papers(q, limit=limit)
    return {
        "query": q,
        "count": len(papers),
        "results": [p.to_dict() for p in papers]
    }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
