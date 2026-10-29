# 第三方组件与素材说明 · Third-party notices

本仓库自己的代码和文档使用 MIT 许可证(见 `LICENSE`)。下面这些是**别人的作品**,各自遵守原许可证,随仓库一起分发的都附了许可证文件。

## 字体(`library/字体库/`)
全部可免费再分发;每个字体文件夹里有对应的许可证文件。

| 字体 | 位置 | 许可证 | 来源 |
|---|---|---|---|
| 思源黑体 Noto Sans SC | `library/字体库/NotoSansSC/` | SIL OFL 1.1 | https://github.com/notofonts/noto-cjk |
| Inter | `library/字体库/Inter/` | SIL OFL 1.1 | https://github.com/rsms/inter |
| 思源宋体 Noto Serif SC | `library/字体库/NotoSerifSC/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/notoserifsc |
| Fraunces | `library/字体库/Fraunces/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/fraunces |
| Instrument Serif | `library/字体库/InstrumentSerif/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/instrumentserif |
| DM Serif Display | `library/字体库/DMSerifDisplay/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/dmserifdisplay |
| 霞鹜文楷 LXGW WenKai | `library/字体库/LXGW-WenKai/` | SIL OFL 1.1 | https://github.com/lxgw/LxgwWenKai |
| 站酷庆科黄油体 | `library/字体库/ZCOOL-QingKe-HuangYou/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/zcoolqingkehuangyou |
| 站酷小薇体 | `library/字体库/ZCOOL-XiaoWei/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei |
| 得意黑 Smiley Sans | `library/字体库/SmileySans/` | SIL OFL 1.1 | https://github.com/atelier-anchor/smiley-sans |
| Space Grotesk | `library/字体库/SpaceGrotesk/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/spacegrotesk |
| Bricolage Grotesque | `library/字体库/BricolageGrotesque/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/bricolagegrotesque |
| JetBrains Mono | `library/字体库/JetBrainsMono/` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/jetbrainsmono |
| DejaVu Sans Mono | `library/字体库/DejaVuSansMono/` | Bitstream Vera / DejaVu 许可 | https://dejavu-fonts.github.io/ |

## UI 组件(`library/UI组件库/galaxy/`)
来自 Uiverse.io 开源组件库 galaxy(https://github.com/uiverse-io/galaxy),MIT 许可证,见该文件夹里的 `LICENSE`;每个组件的原作者记在组件文件里,使用时请保留。

## 模型(`tools/models/`)
`face_detection_yunet_2023mar.onnx`:OpenCV Zoo 的 YuNet 人脸检测模型(https://github.com/opencv/opencv_zoo),MIT 许可证。

## 样张截图(`episodes/_示例_规范v2_scrapling/assets/shots/`、`规范/`)
样张里的网页截图分别截自 GitHub(D4Vinci/Scrapling 仓库页)、PyPI、Scrapling 官方文档、quotes.toscrape.com,来源记在每张截图同名的 `.json` 里。
这些截图只作为教学示例;截图里的页面内容版权归原网站和原作者所有,不在本仓库 MIT 许可范围内。样张里引用的代码和 HTML 片段来自 Scrapling 官方文档。

## 没有放进仓库的
- **Real-ESRGAN**(可选的 AI 放大工具):请从 https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases 下载 macOS 版,解压到 `tools/bin/realesrgan/`(BSD-3-Clause)。
- **libTV**(可选的付费生图服务):需要自己的账号,见 `tools/gen.py` 开头;`brief.json` 里 `"gen_limit": 0` 就完全不用它。
- 素材库里的素材、参考视频截帧、口播录音和成片:涉及第三方版权或个人内容,不公开。
