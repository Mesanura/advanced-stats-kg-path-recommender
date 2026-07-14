# 高级统计课程知识图谱学习路径推荐系统

面向《高级统计方法》课程的本地演示原型，通过知识图谱、学习行为诊断和个性化路径推荐，形成“诊断-适配-引导-反馈”闭环。

## 功能范围

- 学生、教师、管理员三角色登录与权限控制
- 25 个核心知识点及前置关系管理
- 50 名学生的可复现模拟学习行为数据
- 规则法与贝叶斯知识追踪（BKT）学情诊断
- 基于知识图谱的个性化学习路径推荐
- 学生能力画像、教师班级概览和管理员用户管理

## 工程结构

```text
backend/     FastAPI 后端、算法与测试
frontend/    Vue 3 前端与组件测试
data/seed/   可审查的知识图谱和种子数据
scripts/     Windows 本地安装、开发、测试与运行脚本
docs/        迭代计划与运行手册
```

## 快速开始

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

浏览器访问 `http://127.0.0.1:8000`。完整安装、数据重置、测试、角色操作和故障排查见 [运行手册](docs/运行手册.md)。

## 演示账号

| 角色 | 用户名 | 密码 |
|---|---|---|
| 管理员 | `admin` | `Admin@123456` |
| 教师 | `teacher01` / `teacher02` | `Teacher@123456` |
| 学生 | `20260001` - `20260050` | `Student@123456` |

## 测试

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
Set-Location frontend
pnpm test:e2e
```

交付基线：后端 37 项测试通过、覆盖率 86%；前端 13 项测试通过、语句/行覆盖率 94.58%；Playwright 三角色工作流 3 项通过。

## 版本管理

项目采用 Conventional Commits，提交前缀使用英文，说明使用中文。每个功能在独立分支完成并通过测试后合并到 `main`。
