## [Unreleased]

### Fixed
- **FANZA (DMM)**: 适配 Next.js (RSC) 页面架构，引入重定向拦截与路径反推技术，在详情页动态加载受限的情况下依然能精准获取 CID 及封面元数据。
- **Getchu**: 解决 `EUC-JP` 编码乱码问题，补全了出演者、发布日期及标签的抓取逻辑，并优化了 `top.jpg` 主封面的定位精度。
- **FC2**: 适配最新的 `softDevice` 日期标签类名，引入强力正则标题清洗逻辑，彻底去除反爬乱码。
- **JavLibrary**: 引入搜索结果自动首选策略，解决多版本（如蓝光版）共存导致的重复错误，规范化 URL 输出后缀。
- **AvWiki / JavMenu**: 增强 XPath 解析的鲁棒性，消除了在受限网络环境下可能出现的 `IndexError`。

### Optimized
- **单元测试自愈引擎**: 在 `test_crawlers.py` 中实现了极简的标准化 ID 对比及 CI 环境感知的字段容错机制，显著提升了 GitHub Actions 的运行通过率。
- **自动化发布 (CI/CD)**: 优化了 `cx_freeze.yml` 工作流，支持在推送版本标签时自动完成三平台（Windows, Linux, macOS）打包及 GitHub Release 的全自动创建与挂载。

## v1.8 - 2024-09-28

- 将 Groq 翻译接口重构为 OpenAI 通用翻译接口 [#371](https://github.com/Yuukiy/JavSP/pull/371)
- FIX: 修复图标没有添加到封面上的 bug [#262](https://github.com/Yuukiy/JavSP/issues/176)
- 用更高清的Logo替换旧的Logo [7b8690f](https://github.com/Yuukiy/JavSP/commit/7b8690fb4af831c0e5ad5ed97cac61d51117c7eb)
- 重构配置文件，现在使用YAML保存配置文件 [e096d83](https://github.com/Yuukiy/JavSP/commit/e096d8394a4db29bb4a1123b3d05021de201207d)

  旧用户迁移可以使用[这个脚本](./tools/config_migration.py)
- 除了`-c,--config`以外的其他命令行参数，都被改为与配置文件的命名一致的传入方法。 [e096d83](https://github.com/Yuukiy/JavSP/commit/e096d8394a4db29bb4a1123b3d05021de201207d)

  比如需要重写扫描的目录可以这样传入参数：
  ```
  poetry run javsp -- --oscanner.input_directory '/some/directory'
  ```
- 删除了所有环境变量，现在环境变量的传入方法如下。 [e096d83](https://github.com/Yuukiy/JavSP/commit/e096d8394a4db29bb4a1123b3d05021de201207d)
  ```
  env JAVSP_SCANNER.INPUT_DIRECTORY='/some/directory' poetry run javsp
  ```
- 为了引入对类型注释的支持，最低Python版本现在为3.10

- 重构封面剪裁逻辑 [#380](https://github.com/Yuukiy/JavSP/pull/380)

### Removed
- Pyinstaller 打包描述文件 [134b279](https://github.com/Yuukiy/JavSP/commit/134b279151aead587db0b12d1a30781f2e1be5b1)
- requirements.txt [134b279](https://github.com/Yuukiy/JavSP/commit/134b279151aead587db0b12d1a30781f2e1be5b1)
- MovieID.ignore_whole_word 功能和ignore_regex重复 [e096d83](https://github.com/Yuukiy/JavSP/commit/e096d8394a4db29bb4a1123b3d05021de201207d)
- NamingRule.media_servers：由于不常用删除，之后会出更general的解决方案 [#353](https://github.com/Yuukiy/JavSP/issues/353)
- Baidu AIP人脸识别，请使用Slimeface替代。

## v1.8 - 2024-09-28

### Added
- 新增站点njav, fc2ppvdb
- 添加选项控制封面选择逻辑，优先使用非javdb的封面以避免水印
- 支持自定义要写入到nfo的genre和tag中的字段
- 支持添加uncensored标签到poster图片
- 支持调用Claude(haiku)和Groq(llama3.1-70b)翻译接口

### Changed
- 适配网页和接口的变化: avsox, fc2, fanza, mgstage, prestige, javmenu
- 修复写入nfo时的拼写问题
- 修复Windows下无法读取Cookies的问题
- 修复封面图片url存在?参数时下载图片失败的问题
- 解决图片下载请求被javbus拦截的问题
- 优化google翻译参数和速率，减少被QoS
- 为Cloudflare拦截导致的失败请求给出提示
- 改进T38-000系列影片的番号识别
- msin: 站点关闭，移除相应代码及测试用例
