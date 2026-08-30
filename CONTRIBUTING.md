# Contributing to Kioxus

欢迎贡献代码！

## 如何贡献

1. Fork 本仓库
2. 创建你的分支：`git checkout -b feature/your-feature`
3. 提交你的改动：`git commit -m "add your feature"`
4. 推送到你的分支：`git push origin feature/your-feature`
5. 提交 Pull Request

## 开发环境

```bash
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 运行测试

```bash
pytest test/
```

## 代码规范

- 遵循 PEP 8
- 新功能需要有对应测试
- 提交前确保所有测试通过
