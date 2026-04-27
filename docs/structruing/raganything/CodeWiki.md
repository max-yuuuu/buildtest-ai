# RAG-Anything Code Wiki

## 1. 项目概述

RAG-Anything是一个全功能的多模态RAG（检索增强生成）框架，基于LightRAG构建，支持处理文本、图像、表格、公式等多种内容类型。该项目提供端到端的文档处理管道，从文档解析到智能查询，为用户提供统一的多模态文档处理解决方案。

### 主要功能
- 端到端多模态处理管道
- 支持多种文档格式（PDF、Office文档、图像等）
- 专门的内容分析（图像、表格、数学公式）
- 多模态知识图谱
- 自适应处理模式
- 直接内容列表插入
- 混合智能检索

## 2. 项目架构

RAG-Anything采用模块化架构设计，通过mixin类扩展功能，主要包含以下核心模块：

```
raganything/
├── __init__.py          # 包初始化
├── raganything.py       # 核心类，整合所有功能
├── config.py            # 配置管理
├── processor.py         # 文档处理和多模态内容处理
├── query.py             # 查询功能
├── modalprocessors.py   # 多模态处理器
├── parser.py            # 文档解析器
├── batch.py             # 批处理功能
├── base.py              # 基础类和工具
├── callbacks.py         # 回调机制
├── enhanced_markdown.py # 增强Markdown支持
├── prompt.py            # 提示模板
├── prompt_manager.py    # 提示管理
├── prompts_zh.py        # 中文提示模板
├── resilience.py        # 弹性处理
└── utils.py             # 工具函数
```

### 核心模块关系

1. **RAGAnything**：核心类，整合了QueryMixin、ProcessorMixin和BatchMixin
2. **配置管理**：通过RAGAnythingConfig管理所有配置参数
3. **文档处理**：负责文档解析和多模态内容处理
4. **查询功能**：支持纯文本查询和多模态查询
5. **多模态处理**：针对不同类型的内容使用不同的处理器
6. **批处理**：支持批量处理多个文档

## 3. 核心类与函数

### RAGAnything 类

核心类，整合了查询、处理和批处理功能。

```python
@dataclass
class RAGAnything(QueryMixin, ProcessorMixin, BatchMixin):
    # 核心组件
    lightrag: Optional[LightRAG] = field(default=None)
    llm_model_func: Optional[Callable] = field(default=None)
    vision_model_func: Optional[Callable] = field(default=None)
    embedding_func: Optional[Callable] = field(default=None)
    config: Optional[RAGAnythingConfig] = field(default=None)
    
    # LightRAG配置
    lightrag_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # 内部状态
    modal_processors: Dict[str, Any] = field(default_factory=dict, init=False)
    context_extractor: Optional[ContextExtractor] = field(default=None, init=False)
    parse_cache: Optional[Any] = field(default=None, init=False)
    callback_manager: CallbackManager = field(default_factory=CallbackManager, init=False, repr=False)
    _parser_installation_checked: bool = field(default=False, init=False)
```

**主要方法**：
- `__post_init__()`: 初始化配置和设置
- `_ensure_lightrag_initialized()`: 确保LightRAG实例已初始化
- `process_document_complete()`: 完整处理文档
- `aquery()`: 异步纯文本查询
- `aquery_with_multimodal()`: 异步多模态查询
- `aquery_vlm_enhanced()`: 异步VLM增强查询
- `process_folder_complete()`: 完整处理文件夹中的文档

### RAGAnythingConfig 类

配置管理类，支持从环境变量加载配置。

```python
@dataclass
class RAGAnythingConfig:
    # 目录配置
    working_dir: str = field(default=get_env_value("WORKING_DIR", "./rag_storage", str))
    
    # 解析器配置
    parse_method: str = field(default=get_env_value("PARSE_METHOD", "auto", str))
    parser_output_dir: str = field(default=get_env_value("OUTPUT_DIR", "./output", str))
    parser: str = field(default=get_env_value("PARSER", "mineru", str))
    display_content_stats: bool = field(default=get_env_value("DISPLAY_CONTENT_STATS", True, bool))
    
    # 多模态处理配置
    enable_image_processing: bool = field(default=get_env_value("ENABLE_IMAGE_PROCESSING", True, bool))
    enable_table_processing: bool = field(default=get_env_value("ENABLE_TABLE_PROCESSING", True, bool))
    enable_equation_processing: bool = field(default=get_env_value("ENABLE_EQUATION_PROCESSING", True, bool))
    
    # 批处理配置
    max_concurrent_files: int = field(default=get_env_value("MAX_CONCURRENT_FILES", 1, int))
    supported_file_extensions: List[str] = field(default_factory=lambda: [...])
    recursive_folder_processing: bool = field(default=get_env_value("RECURSIVE_FOLDER_PROCESSING", True, bool))
    
    # 上下文提取配置
    context_window: int = field(default=get_env_value("CONTEXT_WINDOW", 1, int))
    context_mode: str = field(default=get_env_value("CONTEXT_MODE", "page", str))
    max_context_tokens: int = field(default=get_env_value("MAX_CONTEXT_TOKENS", 2000, int))
    include_headers: bool = field(default=get_env_value("INCLUDE_HEADERS", True, bool))
    include_captions: bool = field(default=get_env_value("INCLUDE_CAPTIONS", True, bool))
    context_filter_content_types: List[str] = field(default_factory=lambda: [...])
    content_format: str = field(default=get_env_value("CONTENT_FORMAT", "minerU", str))
    
    # 路径处理配置
    use_full_path: bool = field(default=get_env_value("USE_FULL_PATH", False, bool))
```

### ProcessorMixin 类

文档处理功能，包含文档解析和多模态内容处理方法。

**主要方法**：
- `parse_document()`: 解析文档，支持缓存
- `_process_multimodal_content()`: 处理多模态内容
- `_process_multimodal_content_batch_type_aware()`: 类型感知的批处理
- `_convert_to_lightrag_chunks_type_aware()`: 将多模态数据转换为LightRAG格式

### QueryMixin 类

查询功能，包含文本查询和多模态查询方法。

**主要方法**：
- `aquery()`: 异步纯文本查询
- `aquery_with_multimodal()`: 异步多模态查询
- `aquery_vlm_enhanced()`: 异步VLM增强查询
- `query()`: 同步纯文本查询
- `query_with_multimodal()`: 同步多模态查询

### 多模态处理器

针对不同类型的内容使用不同的处理器：

- `ImageModalProcessor`: 处理图像内容
- `TableModalProcessor`: 处理表格内容
- `EquationModalProcessor`: 处理公式内容
- `GenericModalProcessor`: 处理其他类型的内容

## 4. 主要功能模块

### 文档解析

支持多种文档格式的解析，包括PDF、Office文档、图像等。使用可配置的解析器（MinerU、Docling、PaddleOCR）。

**主要流程**：
1. 检测文件类型
2. 选择合适的解析器
3. 解析文档内容
4. 生成内容列表
5. 缓存解析结果

### 多模态内容处理

针对不同类型的内容使用专门的处理器，包括：

- **图像处理**：使用视觉模型生成描述
- **表格处理**：分析表格结构和数据
- **公式处理**：解析数学公式
- **通用内容处理**：处理其他类型的内容

### 智能查询

支持多种查询模式：

- **纯文本查询**：直接调用LightRAG的查询功能
- **多模态查询**：结合文本和多模态内容进行查询
- **VLM增强查询**：使用视觉语言模型分析检索到的图像内容

### 批处理

支持批量处理多个文档，提高处理效率。

**主要功能**：
- 并行处理多个文件
- 递归处理子文件夹
- 支持多种文件格式

## 5. 依赖关系

RAG-Anything依赖以下主要组件：

| 依赖 | 用途 | 来源 |
|------|------|------|
| LightRAG | 底层RAG框架 | <https://github.com/HKUDS/LightRAG> |
| MinerU | 文档解析 | <https://github.com/opendatalab/MinerU> |
| Docling | 文档解析 | 可选解析器 |
| PaddleOCR | OCR解析 | 可选解析器 |
| LibreOffice | Office文档处理 | 外部依赖 |
| Pillow | 图像处理 | 可选依赖 |
| ReportLab | 文本文件处理 | 可选依赖 |

## 6. 项目运行方式

### 安装

#### 从PyPI安装

```bash
# 基本安装
pip install raganything

# 带可选依赖
pip install 'raganything[all]'              # 所有可选功能
pip install 'raganything[image]'            # 图像格式支持
pip install 'raganything[text]'             # 文本文件处理
pip install 'raganything[image,text]'       # 多个功能
```

#### 从源码安装

```bash
# 安装uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并设置项目
git clone https://github.com/HKUDS/RAG-Anything.git
cd RAG-Anything

# 安装包和依赖
uv sync

# 安装可选依赖
uv sync --extra image --extra text  # 特定功能
uv sync --all-extras                 # 所有可选功能
```

### 基本使用

#### 端到端文档处理

```python
import asyncio
from functools import partial
from raganything import RAGAnything, RAGAnythingConfig
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

async def main():
    # 设置API配置
    api_key = "your-api-key"
    base_url = "your-base-url"  # 可选

    # 创建RAGAnything配置
    config = RAGAnythingConfig(
        working_dir="./rag_storage",
        parser="mineru",  # 解析器选择: mineru, docling, 或 paddleocr
        parse_method="auto",  # 解析方法: auto, ocr, 或 txt
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    )

    # 定义LLM模型函数
    def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        return openai_complete_if_cache(
            "gpt-4o-mini",
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    # 定义视觉模型函数
    def vision_model_func(
        prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs
    ):
        if messages:
            return openai_complete_if_cache(
                "gpt-4o",
                "",
                system_prompt=None,
                history_messages=[],
                messages=messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )
        elif image_data:
            return openai_complete_if_cache(
                "gpt-4o",
                "",
                system_prompt=None,
                history_messages=[],
                messages=[
                    {"role": "system", "content": system_prompt} if system_prompt else None,
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                },
                            },
                        ],
                    }
                ],
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )
        else:
            return llm_model_func(prompt, system_prompt, history_messages, **kwargs)

    # 定义嵌入函数
    embedding_func = EmbeddingFunc(
        embedding_dim=3072,
        max_token_size=8192,
        func=partial(
            openai_embed.func,
            model="text-embedding-3-large",
            api_key=api_key,
            base_url=base_url,
        ),
    )

    # 初始化RAGAnything
    rag = RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        vision_model_func=vision_model_func,
        embedding_func=embedding_func,
    )

    # 处理文档
    await rag.process_document_complete(
        file_path="path/to/your/document.pdf",
        output_dir="./output",
        parse_method="auto"
    )

    # 查询处理后的内容
    text_result = await rag.aquery(
        "What are the main findings shown in the figures and tables?",
        mode="hybrid"
    )
    print("Text query result:", text_result)

if __name__ == "__main__":
    asyncio.run(main())
```

#### 多模态查询

```python
# 多模态查询
multimodal_result = await rag.aquery_with_multimodal(
    "Explain this formula and its relevance to the document content",
    multimodal_content=[{
        "type": "equation",
        "latex": "P(d|q) = \\frac{P(q|d) \\cdot P(d)}{P(q)}",
        "equation_caption": "Document relevance probability"
    }],
    mode="hybrid"
)
print("Multimodal query result:", multimodal_result)
```

#### 批处理

```python
# 处理多个文档
await rag.process_folder_complete(
    folder_path="./documents",
    output_dir="./output",
    file_extensions=[".pdf", ".docx", ".pptx"],
    recursive=True,
    max_workers=4
)
```

## 7. 配置选项

### 环境变量

创建`.env`文件（参考`.env.example`）：

```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=your_base_url  # 可选
OUTPUT_DIR=./output             # 默认输出目录
PARSER=mineru                   # 解析器选择: mineru, docling, 或 paddleocr
PARSE_METHOD=auto              # 解析方法: auto, ocr, 或 txt
```

### 解析器配置

RAGAnything支持多种解析器：

- **MinerU解析器**：支持PDF、图像、Office文档等多种格式，具有强大的OCR和表格提取能力
- **Docling解析器**：针对Office文档和HTML文件优化，更好地保留文档结构
- **PaddleOCR解析器**：专注于OCR的解析器，支持图像和PDF

### 处理要求

- **Office文档** (.doc, .docx, .ppt, .pptx, .xls, .xlsx)：需要安装LibreOffice
- **扩展图像格式** (.bmp, .tiff, .gif, .webp)：安装 `pip install raganything[image]`
- **文本文件** (.txt, .md)：安装 `pip install raganything[text]`
- **PaddleOCR解析器**：安装 `pip install raganything[paddleocr]`，然后安装适合平台的paddlepaddle

## 8. 支持的内容类型

### 文档格式

- **PDFs** - 研究论文、报告、演示文稿
- **Office文档** - DOC, DOCX, PPT, PPTX, XLS, XLSX
- **图像** - JPG, PNG, BMP, TIFF, GIF, WebP
- **文本文件** - TXT, MD

### 多模态元素

- **图像** - 照片、图表、截图
- **表格** - 数据表、比较图表、统计摘要
- **公式** - LaTeX格式的数学公式
- **通用内容** - 通过可扩展处理器处理的自定义内容类型

## 9. 项目特点

1. **端到端多模态处理**：从文档解析到智能查询的完整工作流
2. **通用文档支持**：无缝处理PDF、Office文档、图像等多种格式
3. **专门的内容分析**：针对图像、表格、数学公式等不同内容类型的专门处理器
4. **多模态知识图谱**：自动实体提取和跨模态关系发现
5. **自适应处理模式**：灵活的解析或直接多模态内容注入工作流
6. **直接内容列表插入**：通过直接插入预解析的内容列表绕过文档解析
7. **混合智能检索**：跨文本和多模态内容的高级搜索能力

## 10. 总结

RAG-Anything是一个功能强大的多模态RAG框架，为处理和查询包含多种内容类型的文档提供了统一的解决方案。它通过模块化设计和灵活的配置，支持从简单的文本查询到复杂的多模态分析的各种场景。

该项目的核心优势在于其能够处理混合内容文档，将不同类型的内容（文本、图像、表格、公式）整合到一个统一的知识图谱中，并通过智能检索提供准确的答案。这使得RAG-Anything特别适合学术研究、技术文档、财务报告和企业知识管理等需要处理丰富混合内容文档的场景。