"""Database storage functionality for DOI Literature Extractor."""
import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert

from .models import Base, Paper

logger = logging.getLogger(__name__)

# 数据库配置
USE_DATABASE = os.getenv("USE_DATABASE", "true").lower() in ("true", "1", "yes")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./doi_literature.db")
engine = None
AsyncSessionLocal = None


def setup_db(database_url: str = None):
    """设置数据库连接"""
    global engine, AsyncSessionLocal, USE_DATABASE
    
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", DATABASE_URL)
    
    use_database = os.getenv("USE_DATABASE", "true").lower() == "true"
    
    if not use_database:
        logger.info("Database is disabled by environment variable")
        USE_DATABASE = False
        return
    
    try:
        # 为SQLite添加特殊的连接参数
        if "sqlite" in database_url:
            connect_args = {
                "timeout": 30.0,
                "check_same_thread": False,
            }
            
            # 添加SQLite WAL模式
            if "?" in database_url:
                database_url += "&timeout=30&journal_mode=WAL&synchronous=NORMAL"
            else:
                database_url += "?timeout=30&journal_mode=WAL&synchronous=NORMAL"
            
            engine = create_async_engine(
                database_url,
                echo=False,
                connect_args=connect_args,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        else:
            # PostgreSQL或其他数据库
            engine = create_async_engine(
                database_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        USE_DATABASE = True
        logger.info(f"Database setup successful: {database_url}")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        USE_DATABASE = False


async def create_tables():
    """创建数据库表，如果不存在"""
    global engine, USE_DATABASE
    
    if not USE_DATABASE or not engine:
        logger.warning("Database is disabled or not configured correctly.")
        return False
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        return False


async def store_papers(papers: List[Dict]) -> Dict:
    """
    将论文数据存储到数据库
    
    Args:
        papers: 要存储的论文数据列表
        
    Returns:
        包含插入和更新计数的字典
    """
    if not USE_DATABASE:
        logger.warning("Database is disabled. Papers will not be stored.")
        return {"inserted": 0, "updated": 0}
    
    inserted = 0
    updated = 0
    
    try:
        async with AsyncSessionLocal() as session:
            for paper_data in papers:
                try:
                    # 处理日期字段
                    if 'published' in paper_data and isinstance(paper_data['published'], str):
                        try:
                            paper_data['published'] = datetime.fromisoformat(paper_data['published']).date()
                        except ValueError:
                            paper_data['published'] = None
                    
                    # 处理时间戳字段
                    for field in ['created_at', 'updated_at', 'translated_at']:
                        if field in paper_data and isinstance(paper_data[field], str):
                            try:
                                paper_data[field] = datetime.fromisoformat(paper_data[field])
                            except ValueError:
                                paper_data[field] = datetime.now() if field != 'translated_at' else None
                    
                    # 设置默认值
                    paper_data.setdefault('citation_count', 0)
                    paper_data.setdefault('created_at', datetime.now())
                    paper_data.setdefault('updated_at', datetime.now())
                    paper_data.setdefault('translation_status', 'pending')
                    
                    # 处理authors_list
                    if 'authors' in paper_data and paper_data['authors']:
                        try:
                            authors_json = json.loads(paper_data['authors']) if isinstance(paper_data['authors'], str) else paper_data['authors']
                            paper_data['authors_list'] = json.dumps(authors_json)
                        except Exception:
                            pass
                    
                    # PostgreSQL upsert
                    if engine.dialect.name == 'postgresql':
                        stmt = insert(Paper).values(**paper_data)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['doi'],
                            set_={
                                'title': stmt.excluded.title,
                                'authors': stmt.excluded.authors,
                                'journal': stmt.excluded.journal,
                                'abstract': stmt.excluded.abstract,
                                'updated_at': datetime.now(),
                            }
                        )
                        result = await session.execute(stmt)
                        if result.rowcount == 1:
                            inserted += 1
                        else:
                            updated += 1
                    else:
                        # SQLite: 查找-插入/更新
                        stmt = sa.select(Paper).where(Paper.doi == paper_data['doi'])
                        result = await session.execute(stmt)
                        existing = result.scalars().first()
                        
                        if existing:
                            for key, value in paper_data.items():
                                if key != 'id':
                                    setattr(existing, key, value)
                            existing.updated_at = datetime.now()
                            updated += 1
                        else:
                            paper = Paper(**paper_data)
                            session.add(paper)
                            inserted += 1
                            
                except Exception as e:
                    logger.error(f"Error storing paper with DOI {paper_data.get('doi')}: {e}")
                    await session.rollback()
                    
            await session.commit()
            logger.info(f"Stored {inserted} new papers, updated {updated} papers")
    except Exception as e:
        logger.error(f"Database error: {e}")
    
    return {"inserted": inserted, "updated": updated}


async def get_paper_by_doi(doi: str) -> Optional[Paper]:
    """根据DOI获取论文"""
    if not USE_DATABASE or not AsyncSessionLocal:
        return None
    
    try:
        async with AsyncSessionLocal() as session:
            stmt = sa.select(Paper).where(Paper.doi == doi)
            result = await session.execute(stmt)
            return result.scalars().first()
    except Exception as e:
        logger.error(f"Error getting paper by DOI: {e}")
        return None


async def check_paper_exists(doi: str) -> bool:
    """检查论文是否存在"""
    if not USE_DATABASE or not AsyncSessionLocal:
        return False
    
    if not doi:
        return False
    
    try:
        async with AsyncSessionLocal() as session:
            stmt = sa.select(Paper).where(Paper.doi == doi)
            result = await session.execute(stmt)
            return result.scalars().first() is not None
    except Exception as e:
        logger.error(f"Error checking paper existence: {e}")
        return False


async def delete_paper_by_doi(doi: str) -> bool:
    """根据DOI删除论文"""
    if not USE_DATABASE or not AsyncSessionLocal:
        return False
    
    if not doi:
        return False
    
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = sa.select(Paper).where(Paper.doi == doi)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                
                if existing:
                    await session.delete(existing)
                    await session.flush()
                    return True
                return False
    except Exception as e:
        logger.error(f"Error deleting paper: {e}")
        return False


async def get_all_papers(limit: int = 100, offset: int = 0) -> List[Paper]:
    """获取所有论文（分页）"""
    if not USE_DATABASE or not AsyncSessionLocal:
        return []
    
    try:
        async with AsyncSessionLocal() as session:
            stmt = sa.select(Paper).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting papers: {e}")
        return []


async def search_papers(query: str, limit: int = 20) -> List[Paper]:
    """搜索论文（标题、摘要、作者）"""
    if not USE_DATABASE or not AsyncSessionLocal:
        return []
    
    try:
        async with AsyncSessionLocal() as session:
            search_pattern = f"%{query}%"
            stmt = sa.select(Paper).where(
                sa.or_(
                    Paper.title.ilike(search_pattern),
                    Paper.abstract.ilike(search_pattern),
                    Paper.authors.ilike(search_pattern),
                    Paper.doi.ilike(search_pattern),
                )
            ).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()
    except Exception as e:
        logger.error(f"Error searching papers: {e}")
        return []


# 初始化数据库
setup_db()
