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