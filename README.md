# hubozmt-skill · 用代码把口播做成动效视频

一个给 AI 编程助手(Claude Code / Codex 等)用的「做一期视频」技能:把一段口播(音频或真人口播视频)做成知识/科技类动效短视频。
画面全部由代码生成,在浏览器里逐帧渲染:AE 式 3D 摄像机(图层分远近、缓动急停运镜、景深)+ 中文文字排版动效 + 真实网页截图上的 UI 交互动画(框选、终端敲命令、浏览器加载、代码逐字、前后对比……)。只做音效,不做配乐。

*An AI-agent skill that turns a voice-over into a motion-graphics video, generated entirely in code and rendered frame by frame in a headless browser (3D camera + depth of field, Chinese typography animation, UI interaction animation on real screenshots). Docs are in Chinese.*

![规范 v2 样张,每段一帧](规范/img/合格样张_9格.jpg)

## 能做什么
- **两个角色接力**:策划设计师(分段、设计、备齐素材,产出段表)→ 合成师(写场景页、查版面、混音效、渲染)。角色说明在 `roles/`,总流程在 `SKILL.md`。
- **3D 空间引擎**(`engine/web/`):摄像机绑空对象、图层分前中后景、景深与移焦、文字出现/强调/消失动效。
- **动画库存** `hz.k.*`(`engine/web/hz_kit.js`):截图窗、框选扫过、高亮脉冲、浏览器转圈→出内容、改版前后闪切、pills 逐项点亮、代码逐字 + 行高亮、满幅暗场……
- **自动检查**:文字被挡、出画、重叠、展示时间不足;规范 v2 的期还会查「案例段是不是以真实截图 + UI 动画为主」,不合格不让渲染。
- **截图工具**:`hz capture` 截网页并量出要框选的区域位置(写进截图同名 `.json`)。
- 还能拆解参考视频的镜头运动和动效(`hz dissect`),沉淀成风格档案(`styles/`)。

## 运行环境
- macOS(脚本里写的是 macOS 版 Google Chrome 的路径;其他系统要改 `tools/_common.py` 和 `tools/_cdp.py` 里的 `CHROME`)
- Python 3.12、ffmpeg、Google Chrome

```bash
git clone https://github.com/leizixin41-tech/hubozmt-skill.git
cd hubozmt-skill
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
brew install ffmpeg            # 没装过的话
```
作为技能给 Claude Code 用:`ln -s "$(pwd)" ~/.claude/skills/hubozmt-skill`,然后对它说「用 hubozmt 做一期视频」。

## 先跑样张
仓库带了一期按规范 v2 做的样张(`episodes/_示例_规范v2_scrapling/`,27.6 秒,介绍开源项目 Scrapling)。不含口播录音,但段表、场景页、截图、逐词时间轴都在:
```bash
bin/hz plan  _示例_规范v2_scrapling                    # 段表门禁
bin/hz check _示例_规范v2_scrapling                    # 版面 + 画面构成检查
bin/hz web_render _示例_规范v2_scrapling still 9.0 16.6  # 渲两张静帧到 out/
```
要出完整成片,换上你自己的口播:建一期新的文件夹,`bin/hz ingest <本期> <口播文件>`,然后按 `SKILL.md` 的流程走。

## 从哪读起
| 路径 | 内容 |
|---|---|
| `SKILL.md` | 总流程、建期、硬规矩(技能入口) |
| `规范/` | 规范 v2:策划检查清单、合成师动画与素材库、合格 vs 不合格对照、段表模板 |
| `roles/` | 策划设计师、合成师的工作说明 |
| `engine/web/SPACE3D.md` `UI3D.md` | 引擎速查 |
| `styles/` | 风格档案(默认 `space3d`) |
| `tools/` | 命令行工具,每个文件开头有用法;统一用 `bin/hz <工具>` 调用 |
| `library/字体库/` | 免费可商用字体(OFL)和按角色取字体的脚本 |
| `library/UI组件库/` | Uiverse galaxy 开源 UI 组件(MIT) |

## 没有放进仓库的
- 素材库里的素材、参考视频截帧、各期的口播录音和成片(第三方版权或个人内容);`library/素材库/` 只留了登记工具和空索引。
- Real-ESRGAN 放大工具(可选):自行下载,放到 `tools/bin/realesrgan/`,见 `THIRD_PARTY_NOTICES.md`。
- libTV 生图(可选的付费服务):要用就在 `config.json` 填自己的工作区;`brief.json` 写 `"gen_limit": 0` 就完全不用。
- 截图工具默认先试本机代理 `127.0.0.1:7897`,连不上就直连;可用环境变量 `HZ_PROXY` 改。

## 许可证
本仓库的代码和文档:MIT(见 `LICENSE`)。字体、UI 组件、模型、样张截图等第三方内容各自遵守原许可证,见 `THIRD_PARTY_NOTICES.md`。
