## with ... as ...
- 一种`上下文管理器` 语法
- 自动分配资源，并在代码块结束后自动释放资源、做善后

eg.
```python
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()
    print(content)
```
