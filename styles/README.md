# 风格档案

一份风格档案 = 一种「片子的气质」的文字描述,供设计师参考。它描述**感觉和手法**,不是模板,也不规定具体坐标。
设计师按 brief.json 的 `style` 读对应档案;用户没指定就用 `compositor-v1`。

## 从用户投喂的参考视频新建档案
1. 视频太长先截一段:`ffmpeg -ss 0 -t 60 -i 原片.mp4 -c copy /tmp/clip.mp4`
2. 拆解:`bin/hz dissect <视频> styles/_拆解/<名字> [--ocr-fps 4]`(几分钟;产出 report.md、timeline.png、sheets/、moves/、events/)
3. **亲眼看图**,顺序:`timeline.png` → `sheets/overview_*.jpg` → `report.md` → 按需看 `moves/`(镜头运动条带)和 `events/`(元素动效条带)。报告里的数字只是线索,以眼睛看到的为准。
4. 按 `compositor-v1.md` 的结构写 `styles/<名字>.md`,每条都写「怎么做」和「为什么这样做好看」,并注明来源视频与时间点。
5. 拆解出的原始文件(`styles/_拆解/`)不备份,只备份写好的档案;**原片不备份**。

档案结构:气质一句话 / 背景与色彩 / 镜头与缓动 / 层级与空间感 / 文字(字体、字重、字号、出现方式)/ 素材呈现 / 节奏与口播的关系 / 音效 / 不要做的事。
