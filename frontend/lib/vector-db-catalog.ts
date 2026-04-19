/**
 * 向量库类型展示目录：与 `build-test-ai.md` 附录 A.15 保持同步。
 * `/vector-dbs` 类型选择卡片、优缺点列表等 UI 从此处取文案。
 */

export const VECTOR_DB_TYPE_IDS = [
  "postgres_pgvector",
  "qdrant",
  "milvus",
  "weaviate",
  "pinecone",
  "chroma",
] as const;

export type VectorDbTypeId = (typeof VECTOR_DB_TYPE_IDS)[number];

export type VectorDbCatalogEntry = {
  id: VectorDbTypeId;
  /** 卡片标题 */
  name: string;
  /** 一句话定位 */
  tagline: string;
  pros: string[];
  cons: string[];
  /** 更适合的场景 */
  bestFor: string;
  /**
   * Phase 1 是否开放「填写连接 + 测试连接」向导。
   * 其余类型仅展示选型文案；后续接好 SDK 后改为 true。
   */
  connectorAvailable: boolean;
  /** 列表/卡片排序（越小越靠前） */
  sortOrder: number;
  docsUrl?: string;
};

const catalog: VectorDbCatalogEntry[] = [
  {
    id: "postgres_pgvector",
    name: "PostgreSQL（pgvector）",
    tagline: "与业务库同栈的向量扩展，事务与权限模型成熟。",
    pros: [
      "与业务数据同一套 Postgres，备份、监控、权限策略一致",
      "ACID 与行级安全，便于多租户隔离与审计追溯",
      "向量不出自有 VPC，合规与数据驻留友好",
    ],
    cons: [
      "亿级规模、极高 QPS 的纯向量检索成本与调优压力常高于专用向量库",
      "索引类型与参数（lists、probes 等）需要一定向量检索与 DBA 经验",
    ],
    bestFor: "MVP、中小数据量、希望少运维组件或强一致优先的团队。",
    connectorAvailable: true,
    sortOrder: 0,
    docsUrl: "https://github.com/pgvector/pgvector",
  },
  {
    id: "qdrant",
    name: "Qdrant",
    tagline: "面向过滤与 RAG 的向量数据库，部署与 API 相对轻量。",
    pros: [
      "Docker 友好，metadata + 向量过滤能力适合常见 RAG",
      "自托管与云产品可选，社区与工具链成熟",
    ],
    cons: [
      "多一套服务需要单独做监控、备份与容量规划",
      "与业务库分离时，跨系统一致性与灾备需单独设计",
    ],
    bestFor: "需要专用向量服务、又不想过早引入分布式复杂度的中等规模 RAG。",
    connectorAvailable: true,
    sortOrder: 1,
    docsUrl: "https://qdrant.tech/documentation/",
  },
  {
    id: "milvus",
    name: "Milvus",
    tagline: "面向海量向量与分布式检索，能力与运维复杂度都偏高。",
    pros: [
      "面向大规模向量与高吞吐，分布式与多种索引类型较全",
      "Zilliz Cloud 等托管形态可减轻部分运维负担",
    ],
    cons: [
      "组件与概念多，学习曲线与排障成本高于轻量向量库",
      "小规模场景容易「过重」",
    ],
    bestFor: "已明确有海量向量、多集合、高并发检索诉求的产品阶段。",
    connectorAvailable: false,
    sortOrder: 2,
    docsUrl: "https://milvus.io/docs",
  },
  {
    id: "weaviate",
    name: "Weaviate",
    tagline: "带模块生态的向量数据库，对象与向量一体建模。",
    pros: [
      "模块化与 GraphQL 对象模型，适合复杂 schema",
      "hybrid 等检索增强能力便于后续演进",
    ],
    cons: [
      "资源占用与部署拓扑相对重",
      "与 Postgres 业务事实源并存时需划清主数据与向量副本边界",
    ],
    bestFor: "需要丰富模块、对象级建模与 hybrid 检索路线的产品。",
    connectorAvailable: false,
    sortOrder: 3,
    docsUrl: "https://weaviate.io/developers/weaviate",
  },
  {
    id: "pinecone",
    name: "Pinecone",
    tagline: "托管向量索引服务，接入快、免索引运维。",
    pros: [
      "几乎零运维，弹性与 SLA 由厂商承担",
      "从 0 到可检索路径最短",
    ],
    cons: [
      "数据位于第三方，强 VPC 或行业合规需单独评估",
      "成本与网络依赖随规模上升",
    ],
    bestFor: "快速验证、无专职 infra、接受 SaaS 与按量计费的团队。",
    connectorAvailable: false,
    sortOrder: 4,
    docsUrl: "https://docs.pinecone.io/",
  },
  {
    id: "chroma",
    name: "Chroma",
    tagline: "偏原型与本地开发的轻量向量存储。",
    pros: ["开发体验好", "嵌入式模式极轻，适合 PoC"],
    cons: [
      "大规模生产下的持久化、高可用与多租户隔离需审慎选型部署模式",
    ],
    bestFor: "本地 demo、PoC；生产环境需明确容量与 HA 方案。",
    connectorAvailable: false,
    sortOrder: 5,
    docsUrl: "https://docs.trychroma.com/",
  },
];

catalog.sort((a, b) => a.sortOrder - b.sortOrder);

export const VECTOR_DB_CATALOG: readonly VectorDbCatalogEntry[] = catalog;

const byId = new Map<VectorDbTypeId, VectorDbCatalogEntry>(
  catalog.map((e) => [e.id, e]),
);

export function getVectorDbCatalogEntry(
  id: string,
): VectorDbCatalogEntry | undefined {
  if (!VECTOR_DB_TYPE_IDS.includes(id as VectorDbTypeId)) return undefined;
  return byId.get(id as VectorDbTypeId);
}

export function listVectorDbCatalogForUi(): VectorDbCatalogEntry[] {
  return [...catalog];
}
