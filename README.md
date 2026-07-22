# 高级统计课程知识图谱学习路径推荐系统

面向《高级统计方法》课程的本地演示原型，通过知识图谱、学习行为诊断和个性化路径推荐，形成“诊断-适配-引导-反馈”闭环。

## 功能范围

- 学生、教师、管理员三角色登录与权限控制
- 25 个核心知识点及前置关系管理
- 50 名学生的可复现模拟学习行为数据
- 规则法与贝叶斯知识追踪（BKT）学情诊断
- 全前置必修、拓扑排序和均衡分阶段的个性化学习路径推荐
- 学生能力画像、建议学习方向、分阶段路径交互和练习后自动更新
- 教师与管理员共用的知识图谱治理和推荐策略配置
- 管理员账号详情、编辑、删除和教学组织管理

## 工程结构

```text
backend/     FastAPI 后端、算法与测试
frontend/    Vue 3 前端与组件测试
data/seed/   可审查的知识图谱和种子数据
scripts/     PowerShell/Bash 本地安装、开发、测试与运行脚本
docs/        迭代记录、运行手册与验收截图
```

## 快速开始

PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Windows Git Bash、Linux 或 macOS：

```bash
./scripts/setup.sh
./scripts/run.sh
```

浏览器访问 `http://127.0.0.1:8000`。面向学生、教师和管理员的图文步骤见 [用户操作手册](docs/用户操作手册.md)；完整安装、数据库升级、数据重置、测试和故障排查见 [运行手册](docs/运行手册.md)。版本目标与验收证据见 [迭代计划](docs/迭代计划.md)，发布内容见 [变更日志](CHANGELOG.md)。

## 演示账号

| 角色 | 用户名 | 密码 |
|---|---|---|
| 管理员 | `admin` | `Admin@123456` |
| 教师 | `teacher01` / `teacher02` | `Teacher@123456` |
| 学生 | `20260001` - `20260050` | `Student@123456` |

## 测试

PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

Bash：

```bash
./scripts/test.sh
```

端到端测试：

```bash
cd frontend
pnpm test:e2e
```

`v1.2.0` 验收门槛为：后端覆盖率不低于 85%；前端语句/行不低于 90%、分支不低于 85%、函数不低于 70%；Playwright 在 `1440x900` 和 `390x844` 下覆盖学生、教师、管理员真实流程；单次路径生成低于 500ms。当前实测证据记录在 [迭代计划](docs/迭代计划.md)。

## 版本管理

当前发布版本为 `1.2.0`。项目采用 Conventional Commits，提交前缀使用英文，说明使用中文；功能必须在对应版本的自动化与视觉验收通过后，才能在迭代记录中标记为完成。
