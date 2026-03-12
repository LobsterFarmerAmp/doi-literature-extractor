"""Database models for DOI Literature Extractor."""
import logging
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class Paper(Base):
    """论文数据模型 - 通过DOI提取的期刊文章信息"""
    __tablename__ = "papers"
    
    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(sa.DateTime, default=datetime.now)
    updated_at = sa.Column(sa.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 基本信息
    doi = sa.Column(sa.String(128), unique=True, nullable=False, index=True)
    title = sa.Column(sa.Text)
    authors = sa.Column(sa.Text)  # JSON格式的作者列表
    authors_list = sa.Column(sa.Text, nullable=True)  # JSON格式的作者数组
    
    # 期刊信息
    journal = sa.Column(sa.String(256))
    issn = sa.Column(sa.String(32), nullable=True)
    eissn = sa.Column(sa.String(32), nullable=True)
    published = sa.Column(sa.Date)
    
    # 内容
    abstract = sa.Column(sa.Text)
    url = sa.Column(sa.Text)
    
    # 统计信息
    citation_count = sa.Column(sa.Integer, default=0)
    is_open_access = sa.Column(sa.Boolean, default=False)
    
    # 翻译字段（可选）
    chinese_title = sa.Column(sa.Text, nullable=True)
    chinese_abstract = sa.Column(sa.Text, nullable=True)
    research_summary = sa.Column(sa.Text, nullable=True)
    translation_status = sa.Column(sa.String(32), default='pending')
    translation_error = sa.Column(sa.Text, nullable=True)
    translated_at = sa.Column(sa.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Paper(id={self.id}, doi='{self.doi}', title='{self.title[:30] if self.title else 'N/A'}...')>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'doi': self.doi,
            'title': self.title,
            'authors': self.authors,
            'journal': self.journal,
            'published': self.published.isoformat() if self.published else None,
            'abstract': self.abstract,
            'citation_count': self.citation_count,
            'url': self.url,
            'chinese_title': self.chinese_title,
            'chinese_abstract': self.chinese_abstract,
        }
