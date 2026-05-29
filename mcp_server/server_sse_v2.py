#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Euclid Image Cutout Service - MCP Server (SSE Transport)
符合标准 MCP SSE 协议，支持 N8N MCP Client 节点
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from mcp.types import Tool
import mcp.types as types

# 导入工具处理函数
from mcp_server.tools.query_tools import handle_query_tile_id, handle_batch_query_tile_ids
from mcp_server.tools.catalog_tools import handle_get_catalog_info, handle_validate_catalog
from mcp_server.tools.cutout_tools import (
    handle_cutout_single,
    handle_cutout_batch,
    handle_get_cutout_status,
    handle_list_cutout_tasks
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定义工具列表
TOOLS = [
    Tool(
        name="query_tile_id",
        description="根据天体坐标（RA, DEC）查询对应的 Euclid TILE ID",
        inputSchema={
            "type": "object",
            "properties": {
                "ra": {
                    "type": "number",
                    "description": "赤经（度），范围 0-360"
                },
                "dec": {
                    "type": "number",
                    "description": "赤纬（度），范围 -90 到 90"
                },
                "tile_index_file": {
                    "type": "string",
                    "description": "TILE 坐标文件路径（可选，默认使用内置文件）"
                }
            },
            "required": ["ra", "dec"]
        }
    ),
    Tool(
        name="batch_query_tile_ids",
        description="批量查询多个坐标对应的 TILE ID",
        inputSchema={
            "type": "object",
            "properties": {
                "coordinates": {
                    "type": "array",
                    "description": "坐标数组，每个元素为 [ra, dec]",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2
                    }
                },
                "tile_index_file": {
                    "type": "string",
                    "description": "TILE 坐标文件路径（可选）"
                }
            },
            "required": ["coordinates"]
        }
    ),
    Tool(
        name="get_catalog_info",
        description="获取 FITS 或 CSV 格式星表文件的详细信息，包括行数、坐标范围、列信息等",
        inputSchema={
            "type": "object",
            "properties": {
                "catalog_path": {
                    "type": "string",
                    "description": "星表文件的完整路径"
                },
                "ra_col": {
                    "type": "string",
                    "description": "RA 列名（可选，自动检测）"
                },
                "dec_col": {
                    "type": "string",
                    "description": "DEC 列名（可选，自动检测）"
                },
                "id_col": {
                    "type": "string",
                    "description": "ID 列名（可选，自动检测）"
                }
            },
            "required": ["catalog_path"]
        }
    ),
    Tool(
        name="validate_catalog",
        description="验证星表文件的格式和内容，检查坐标有效性、行数限制等",
        inputSchema={
            "type": "object",
            "properties": {
                "catalog_path": {
                    "type": "string",
                    "description": "星表文件的完整路径"
                },
                "ra_col": {
                    "type": "string",
                    "description": "RA 列名（可选，自动检测）"
                },
                "dec_col": {
                    "type": "string",
                    "description": "DEC 列名（可选，自动检测）"
                },
                "max_rows": {
                    "type": "integer",
                    "description": "最大允许行数（默认 10000）",
                    "default": 10000
                }
            },
            "required": ["catalog_path"]
        }
    ),
    Tool(
        name="cutout_single",
        description="对单个天体坐标进行 Euclid 图像裁剪，支持多仪器、多波段、多文件类型",
        inputSchema={
            "type": "object",
            "properties": {
                "ra": {
                    "type": "number",
                    "description": "赤经（度），范围 0-360"
                },
                "dec": {
                    "type": "number",
                    "description": "赤纬（度），范围 -90 到 90"
                },
                "size": {
                    "type": "integer",
                    "description": "裁剪尺寸（像素），默认 128",
                    "default": 128
                },
                "instruments": {
                    "type": "array",
                    "description": "仪器列表，可选: VIS, NISP, DECAM 等，默认 ['VIS']",
                    "items": {"type": "string"},
                    "default": ["VIS"]
                },
                "file_types": {
                    "type": "array",
                    "description": "文件类型列表，可选: SCI(科学图像), WHT(权重图), RMS(噪声图), CATALOG-PSF(PSF星表)，默认 ['SCI', 'WHT']",
                    "items": {"type": "string"},
                    "default": ["SCI", "WHT"]
                },
                "bands": {
                    "type": "array",
                    "description": "波段列表（可选），如 ['NIR-Y', 'DES-G']",
                    "items": {"type": "string"}
                },
                "output_dir": {
                    "type": "string",
                    "description": "输出目录（可选，默认自动生成）"
                },
                "obj_id": {
                    "type": "string",
                    "description": "对象ID（可选，默认使用坐标生成）"
                }
            },
            "required": ["ra", "dec"]
        }
    ),
    Tool(
        name="cutout_batch",
        description="批量裁剪 Euclid 图像，从星表文件读取坐标列表，创建异步处理任务",
        inputSchema={
            "type": "object",
            "properties": {
                "catalog_path": {
                    "type": "string",
                    "description": "星表文件路径（FITS 或 CSV 格式）"
                },
                "ra_col": {
                    "type": "string",
                    "description": "RA 列名，默认 'RA'",
                    "default": "RA"
                },
                "dec_col": {
                    "type": "string",
                    "description": "DEC 列名，默认 'DEC'",
                    "default": "DEC"
                },
                "obj_id_col": {
                    "type": "string",
                    "description": "对象ID列名（可选）"
                },
                "size": {
                    "type": "integer",
                    "description": "裁剪尺寸（像素），默认 128",
                    "default": 128
                },
                "instruments": {
                    "type": "array",
                    "description": "仪器列表，默认 ['VIS']",
                    "items": {"type": "string"},
                    "default": ["VIS"]
                },
                "file_types": {
                    "type": "array",
                    "description": "文件类型列表，默认 ['SCI', 'WHT']",
                    "items": {"type": "string"},
                    "default": ["SCI", "WHT"]
                },
                "bands": {
                    "type": "array",
                    "description": "波段列表（可选）",
                    "items": {"type": "string"}
                },
                "n_workers": {
                    "type": "integer",
                    "description": "并行工作进程数，默认 4，最大 16",
                    "default": 4
                },
                "max_rows": {
                    "type": "integer",
                    "description": "最大处理行数，默认 10000",
                    "default": 10000
                }
            },
            "required": ["catalog_path"]
        }
    ),
    Tool(
        name="get_cutout_status",
        description="查询批量裁剪任务的状态和进度",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID（由 cutout_batch 返回）"
                }
            },
            "required": ["task_id"]
        }
    ),
    Tool(
        name="list_cutout_tasks",
        description="列出所有裁剪任务及其状态",
        inputSchema={
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "description": "状态过滤（可选），可选值: pending, processing, completed, failed",
                    "enum": ["pending", "processing", "completed", "failed"]
                }
            }
        }
    )
]

# 工具处理函数映射
TOOL_HANDLERS = {
    "query_tile_id": handle_query_tile_id,
    "batch_query_tile_ids": handle_batch_query_tile_ids,
    "get_catalog_info": handle_get_catalog_info,
    "validate_catalog": handle_validate_catalog,
    "cutout_single": handle_cutout_single,
    "cutout_batch": handle_cutout_batch,
    "get_cutout_status": handle_get_cutout_status,
    "list_cutout_tasks": handle_list_cutout_tasks
}

# 存储每个会话的消息队列
sessions: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 启动 Euclid Image Cutout MCP 服务器 (SSE Transport)")
    logger.info(f"📦 提供 {len(TOOLS)} 个工具:")
    for tool in TOOLS:
        logger.info(f"  - {tool.name}: {tool.description}")
    yield
    logger.info("🛑 关闭 MCP 服务器")


# 创建 FastAPI 应用
app = FastAPI(
    title="Euclid Image Cutout MCP Service",
    description="MCP 服务，提供天文图像裁剪和星表处理功能 (SSE Transport)",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """根路径 - 服务信息"""
    return {
        "service": "Euclid Image Cutout MCP Service",
        "version": "1.0.0",
        "protocol": "MCP over SSE",
        "transport": "sse",
        "endpoint": "/sse",
        "tools": [tool.name for tool in TOOLS],
        "mcp_version": "2024-11-05"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy", "service": "euclid-cutout-mcp", "transport": "sse"}


@app.get("/sse")
async def sse_endpoint(request: Request):
    """
    SSE 端点 - MCP 协议的 SSE 传输层

    客户端通过 GET 建立 SSE 连接，服务器通过此连接发送响应
    客户端通过 POST 到同一端点发送请求
    """
    session_id = str(uuid.uuid4())
    message_queue = asyncio.Queue()
    sessions[session_id] = message_queue

    logger.info(f"新的 SSE 连接: {session_id}")

    async def event_generator():
        try:
            # 发送 endpoint 事件（告诉客户端 POST 地址）
            yield {
                "event": "endpoint",
                "data": f"/sse?sessionId={session_id}"
            }

            # 保持连接并发送消息
            while True:
                if await request.is_disconnected():
                    logger.info(f"客户端断开连接: {session_id}")
                    break

                try:
                    # 等待消息，超时后发送心跳
                    message = await asyncio.wait_for(message_queue.get(), timeout=30.0)

                    # 发送消息事件
                    yield {
                        "event": "message",
                        "data": json.dumps(message)
                    }

                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield {
                        "event": "ping",
                        "data": ""
                    }

        except Exception as e:
            logger.error(f"SSE 流错误: {e}", exc_info=True)
        finally:
            # 清理会话
            if session_id in sessions:
                del sessions[session_id]
            logger.info(f"清理会话: {session_id}")

    return EventSourceResponse(event_generator())


@app.post("/sse")
async def sse_post_endpoint(request: Request):
    """
    SSE POST 端点 - 接收客户端的 JSON-RPC 请求
    """
    # 获取 session ID
    session_id = request.query_params.get("sessionId")

    if not session_id:
        logger.error("缺少 sessionId 参数")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Missing sessionId parameter"
                }
            }
        )

    if session_id not in sessions:
        logger.error(f"无效的 sessionId: {session_id}")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Invalid sessionId"
                }
            }
        )

    try:
        # 解析请求
        data = await request.json()
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")

        logger.info(f"收到请求 [session={session_id}]: {method}")
        logger.info(f"参数: {json.dumps(params, ensure_ascii=False)}")

        # 处理不同的 MCP 方法
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "euclid-cutout-service",
                        "version": "1.0.0"
                    }
                }
            }

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in TOOLS
                    ]
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            logger.info(f"调用工具: {tool_name}")

            if tool_name not in TOOL_HANDLERS:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"未知工具: {tool_name}"
                    }
                }
            else:
                try:
                    handler = TOOL_HANDLERS[tool_name]
                    result = await handler(arguments)

                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, indent=2)
                                }
                            ]
                        }
                    }
                except Exception as e:
                    logger.error(f"工具执行失败: {e}", exc_info=True)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"工具执行失败: {str(e)}"
                        }
                    }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"未知方法: {method}"
                }
            }

        # 将响应放入消息队列，通过 SSE 发送
        await sessions[session_id].put(response)

        # 返回 202 Accepted
        return JSONResponse(
            status_code=202,
            content={"status": "accepted"}
        )

    except Exception as e:
        logger.error(f"请求处理失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        )


if __name__ == "__main__":
    import uvicorn

    # 从配置文件读取端口
    try:
        from euclid_service.config import get_config
        config = get_config()
        host = config.get('mcp.host', '0.0.0.0')
        port = config.get('mcp.port', 8000)
    except:
        host = '0.0.0.0'
        port = 8000

    logger.info(f"🌐 启动 SSE 服务器: http://{host}:{port}")
    logger.info(f"📡 SSE 端点: http://{host}:{port}/sse")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
