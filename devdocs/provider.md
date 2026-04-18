## 问题1
最致命的三点：
  1. provider_service.py:42, 71 里 get/update 把 p.api_key_encrypted（密文）当作 plain_key_hint 传给 mask_api_key，生成的 mask 是"密文前后 4 位"——既不是真正的 key
  掩码，还反向暴露了密文特征。通常 mask 应该在加密前从明文算出来并单独存一列（如 api_key_mask）。
  2. 没有连通性测试接口（如 POST /providers/{id}/test）。用户填完 key 只有等用的时候才知道对不对，这对评测链路很不友好。
  3. 按 buildtest-ai.md 设计，providers 下要挂 models（llm / embedding），但现在 provider CRUD 跟 models 完全没打通——既没有"创建 provider 后拉取可用模型"，也没有删除时校验是否被
  models / knowledge_bases 引用。

  次要但也欠账的：base_url 对不同 provider 类型语义不同（azure 必填、openai 可选），schema 没区分；缺 (user_id, name) 唯一约束可建重名；软删有 deleted_at 但没 restore
  接口；没有默认 provider 标记；key 轮换没审计日志。

  建议先修 1（安全）+ 3（阻塞后续里程碑），2 可以放到 models 接口一起做

## 解决进度

- **问题 1** ✅ 已解决(commit `eab6a62`):`providers` 表新增 `api_key_mask` 列,迁移 `0002_provider_mask_and_models` 对存量数据一次性回填;`provider_service.py` 在 create/update 时从明文派生 mask,密文不再进入 mask 计算路径。
- **问题 2** ✅ 已解决:新增 `POST /api/v1/providers/{id}/test`,走 `provider_probe` 统一抽象按 `provider_type` 分派调上游 `/models` 接口。连通性失败返回 `200 + ok=False`(含 `latency_ms` / `message`),仅 provider 不存在或未授权才 4xx。
- **问题 3** ✅ 已解决:
  - 已有 `models` 表 + `count_models_referencing` 删除阻塞(commit `eab6a62`)。
  - 新增 Models CRUD:`GET/POST/PUT/DELETE /api/v1/providers/{provider_id}/models`,`ModelRepository` 通过 join `providers.user_id` 强制多租户隔离(路径参 `provider_id` 不属当前 user → 404,不泄漏存在性)。
  - 新增 `GET /api/v1/providers/{provider_id}/models/available`:实时拉取上游模型列表并用 `is_registered` 标记已登记项,与 `/test` 共用 probe 层,避免重复调上游。
  - 迁移 `0003_models_unique_model_id` 加 `UNIQUE(provider_id, model_id)`,防重复登记同一模型。
  - embedding 模型强制 `vector_dimension` 必填(`ModelCreate.model_validator` + update 时二次校验)。

## 未处理的次要欠账

按原建议,下列仍未处理,后续视优先级再做:

- `base_url` 按 `provider_type` 区分必填/可选(现在仅在 probe 层运行时校验,schema 层未强约束)。
- `(user_id, name)` 唯一约束,防同一用户建重名 provider。
- 软删 `restore` 接口。
- 默认 provider 标记。
- api_key 轮换审计日志。
