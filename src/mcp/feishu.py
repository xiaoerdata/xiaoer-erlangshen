"""
MCP 工具 - 飞书文档
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class FeishuMCP:
    """
    飞书 MCP
    
    提供飞书文档、消息等操作接口
    """
    
    def __init__(self):
        self.name = "feishu"
        self._client = None
        self._access_token = None
    
    def _get_client(self):
        """获取飞书客户端"""
        if self._client is None:
            try:
                from src.config import get_config
                config = get_config()
                
                if not config.feishu_app_id or not config.feishu_app_secret:
                    logger.warning("飞书配置不完整，请设置 feishu_app_id 和 feishu_app_secret")
                    return None
                
                # 飞书 API 客户端初始化
                # 注意：需要安装 feishu SDK: pip install lark-oapi
                try:
                    import lark
                    
                    self._client = lark.Client(
                        app_id=config.feishu_app_id,
                        app_secret=config.feishu_app_secret,
                    )
                except ImportError:
                    logger.warning("请安装飞书 SDK: pip install lark-oapi")
                    return None
                    
            except Exception as e:
                logger.warning(f"飞书客户端初始化失败: {e}")
                return None
        
        return self._client
    
    async def create_doc(
        self,
        title: str,
        folder_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建飞书文档
        
        Args:
            title: 文档标题
            folder_token: 文件夹token (可选)
        
        Returns:
            文档信息
        """
        client = self._get_client()
        
        if not client:
            return {
                "success": False,
                "error": "飞书客户端未初始化，请检查配置",
                "source": "feishu_mcp"
            }
        
        try:
            response = client.docx.document.create(
                title=title,
                folder_token=folder_token
            )
            
            return {
                "success": True,
                "document_id": response.data.document.document_id,
                "title": title,
                "url": f"https://.feishu.cn/document/{response.data.document.document_id}",
                "source": "feishu_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "source": "feishu_mcp"
            }
    
    async def append_doc(
        self,
        document_id: str,
        content: str
    ) -> Dict[str, Any]:
        """
        向飞书文档追加内容
        
        Args:
            document_id: 文档ID
            content: 追加的内容 (Markdown格式)
        
        Returns:
            操作结果
        """
        client = self._get_client()
        
        if not client:
            return {
                "success": False,
                "error": "飞书客户端未初始化",
                "source": "feishu_mcp"
            }
        
        try:
            # 转换 Markdown 为飞书块
            blocks = self._markdown_to_feishu_blocks(content)
            
            # 插入文档
            response = client.docx.document.blocks.append(
                document_id=document_id,
                children=blocks
            )
            
            return {
                "success": True,
                "blocks_added": len(blocks),
                "source": "feishu_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "source": "feishu_mcp"
            }
    
    async def search_docs(
        self,
        query: str,
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索飞书文档
        
        Args:
            query: 搜索关键词
            count: 返回数量
        
        Returns:
            文档列表
        """
        client = self._get_client()
        
        if not client:
            return []
        
        try:
            response = client.docx.document.search(
                query=query,
                count=count
            )
            
            docs = []
            for doc in response.data.documents:
                docs.append({
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "url": f"https://feishu.cn/document/{doc.document_id}"
                })
            
            return docs
        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            return []
    
    async def send_message(
        self,
        chat_id: str,
        content: str,
        msg_type: str = "text"
    ) -> Dict[str, Any]:
        """
        发送飞书消息
        
        Args:
            chat_id: 群ID
            content: 消息内容
            msg_type: 消息类型 (text, post, interactive)
        
        Returns:
            发送结果
        """
        client = self._get_client()
        
        if not client:
            return {
                "success": False,
                "error": "飞书客户端未初始化",
                "source": "feishu_mcp"
            }
        
        try:
            if msg_type == "text":
                message_content = {
                    "text": content
                }
            else:
                message_content = {
                    "text": content
                }
            
            response = client.im.message.create(
                receive_id_type="chat_id",
                receive_id=chat_id,
                msg_type=msg_type,
                content=message_content
            )
            
            return {
                "success": True,
                "message_id": response.data.message_id,
                "source": "feishu_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "source": "feishu_mcp"
            }
    
    def _markdown_to_feishu_blocks(self, markdown: str) -> List[Dict]:
        """
        将 Markdown 转换为飞书块
        
        Args:
            markdown: Markdown 文本
        
        Returns:
            飞书块列表
        """
        # 简化实现，实际应使用更复杂的解析
        blocks = []
        
        lines = markdown.split("\n")
        for line in lines:
            if line.startswith("# "):
                blocks.append({
                    "block_type": 2,  # heading1
                    "heading1": {
                        "elements": [{"text_run": {"content": line[2:]}}],
                        "style": {}
                    }
                })
            elif line.startswith("## "):
                blocks.append({
                    "block_type": 3,  # heading2
                    "heading2": {
                        "elements": [{"text_run": {"content": line[3:]}}],
                        "style": {}
                    }
                })
            elif line.startswith("### "):
                blocks.append({
                    "block_type": 4,  # heading3
                    "heading3": {
                        "elements": [{"text_run": {"content": line[4:]}}],
                        "style": {}
                    }
                })
            elif line.startswith("-"):
                blocks.append({
                    "block_type": 12,  # bullet
                    "bullet": {
                        "elements": [{"text_run": {"content": line[1:].strip()}}],
                        "style": {}
                    }
                })
            elif line.strip():
                blocks.append({
                    "block_type": 2,  # paragraph
                    "paragraph": {
                        "elements": [{"text_run": {"content": line}}],
                        "style": {}
                    }
                })
        
        return blocks
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return [
            {
                "name": "create_doc",
                "description": "创建飞书文档",
                "parameters": {
                    "title": "文档标题",
                    "folder_token": "文件夹token (可选)"
                }
            },
            {
                "name": "append_doc",
                "description": "向文档追加内容",
                "parameters": {
                    "document_id": "文档ID",
                    "content": "内容 (Markdown格式)"
                }
            },
            {
                "name": "search_docs",
                "description": "搜索飞书文档",
                "parameters": {
                    "query": "搜索关键词",
                    "count": "返回数量"
                }
            },
            {
                "name": "send_message",
                "description": "发送飞书消息",
                "parameters": {
                    "chat_id": "群ID",
                    "content": "消息内容",
                    "msg_type": "消息类型"
                }
            },
        ]
