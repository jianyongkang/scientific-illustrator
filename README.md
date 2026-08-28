# scientific-illustrator v2.0

面向 **Windows + Adobe Illustrator + ChatGPT/Codex** 的纯本地科研矢量重绘 Skill。

v2 的核心不再是“把整张 SVG 一次导入 Illustrator”，而是：

**AI 理解参考图并写 Master SVG -> Master SVG 只解析一次 -> 缓存成按绘制顺序排列的 path/text atoms -> 保持同一个 Illustrator 连接 -> 分批创建原生 PathItem / live text -> 中断后从未完成批次继续。**

## v2 新架构

- **AI 语义矢量化**：由当前模型自己识别文字、箭头、框、圆、细胞/机制关系并构造 Master SVG；脚本不会再次调用模型，也不需要第三方矢量化 API。
- **Master SVG 几何缓存**：`prepare_geometry_cache.py` 对每个 Master SVG 版本只解析一次，并绑定 SHA256。
- **原生对象播放**：`play_batch.jsx` 把缓存 atom 逐个创建成 Illustrator 原生路径和 live text，而不是整张 SVG 作为一个 placed item。
- **固定 paint order**：按照 Master SVG 文档顺序恢复前后层级。
- **20-50 atom 分批**：默认 30；真正复杂的单个 path 可以独立成批。
- **单 Illustrator 会话**：`run_playback.ps1` 只获取一次已经打开的 Illustrator COM 对象，并贯穿所有批次。
- **断点续画**：每批有 pending/completed 标记；中断后保留已完成批次，只重画当前未完成批次。
- **状态防串文档**：`playback-state.json` 绑定当前 Illustrator 文档与 cache id，避免恢复到错误文件。
- **Master 改动自动失效**：Master SVG SHA 改变后旧 cache 会被判定 stale，必须重建并安全重置 Skill 自己的 `SI_` 图层。
- **无网络依赖**：不需要 API Key，不上传参考图。

## 推荐流程

```powershell
python scripts\prepare_job.py .\work
python scripts\svg_qa.py .\work\si_job_0001\master.svg --strict --playback
python scripts\prepare_geometry_cache.py .\work\si_job_0001\master.svg --cache-dir .\work\si_job_0001\cache --batch-size 30
python scripts\cache_qa.py .\work\si_job_0001\cache --master-svg .\work\si_job_0001\master.svg --strict
powershell -ExecutionPolicy Bypass -File scripts\run_playback.ps1 -CacheDir .\work\si_job_0001\cache -LayerName SI_redraw -FitMode contain
```

如果 Illustrator/Codex 在绘图中断，直接再次运行最后一条命令即可续画。不要加 `-ResetGeneratedLayer`。

如果你修改了 `master.svg`，重新做 QA + `prepare_geometry_cache.py --replace`，然后：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_playback.ps1 -CacheDir .\work\si_job_0001\cache -LayerName SI_redraw -FitMode contain -ResetGeneratedLayer
```

## 查看断点状态

```powershell
python scripts\playback_status.py .\work\si_job_0001\cache
```

## 离线自检

```powershell
python scripts\self_test.py
```

## 推荐提示词

```text
使用 $scientific-illustrator，根据我上传的论文图在我已经打开的 Illustrator 文档中重画。你自己理解图中结构并构造可编辑 Master SVG，不用第三方矢量化 API。先做文字清单和 playback-safe QA，再把 Master SVG 只解析一次为几何缓存，通过同一个 Illustrator 会话按 paint order 分批创建原生 PathItem 和 live text；中断则从未完成批次继续。导出预览后对照修正，最后输出新的 AI 副本和 PDF，不覆盖原文件。
```
