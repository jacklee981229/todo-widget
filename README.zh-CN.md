<div align="center">

# To-do widget

[English](README.md) | **简体中文**

放在 Windows 桌面上的小待办清单，Claude 也能往里写：<br>你一开口它就加上，相关的工作推送后它就打勾。

<img src=".github/readme/grouped.png" width="300" alt="小组件：四条未完成的待办，按三个项目分组，每个项目一种颜色">

</div>

## 长什么样

<table>
  <tr>
    <td align="center" width="25%"><img src=".github/readme/list.png" alt="一个列表，每条待办带着彩色的项目标签"></td>
    <td align="center" width="25%"><img src=".github/readme/ticked.png" alt="打过勾的待办在分隔线下面，带删除线"></td>
    <td align="center" width="25%"><img src=".github/readme/adding.png" alt="新增待办的表单：内容、项目和备注"></td>
    <td align="center" width="25%"><img src=".github/readme/undo.png" alt="刚打勾后，底部出现 Undo"></td>
  </tr>
  <tr>
    <td align="center"><b>一个列表</b><br>关掉 Group：最早的在前，每条带项目。</td>
    <td align="center"><b>做完的</b><br>Expand 显示打过勾的，最新的在前。</td>
    <td align="center"><b>新增</b><br>待办、项目和备注。</td>
    <td align="center"><b>撤销</b><br>打勾后 5 秒内可以 Undo。</td>
  </tr>
</table>

## 功能

- **Claude 帮你更新。** 任何 Claude Code 会话都能用一条命令新增或勾掉待办，小组件 2 秒内就会显示。
- **每个项目一种颜色，** 用在分组标题和项目标签上。顶部的下拉框可以显示全部项目或只看一个。
- **不挡路。** 它待在桌面上、所有窗口后面，按 Win+D 时才到前面来；不在任务栏，也不在 Alt+Tab 里。
- **什么都不用装。** 只用 Python 和 tkinter，没有第三方包。你的清单就是一个文件：`data\todos.json`。

## 快速开始

在这个文件夹里打开 PowerShell：

```powershell
pythonw widget.py
```

点 **+** 新增待办（Enter 保存，Esc 取消），点待办前面的方框打勾。拖动标题栏可以移动它，右键标题栏可以退出。

从 Claude 或任何终端新增、打勾：

```powershell
python C:\path\to\todo-widget\todos.py add jacks-space 'Write up the trip' --notes 'Photos picked'
python C:\path\to\todo-widget\todos.py done jacks-space 'Write up the trip'
```

登录 Windows 时自动启动：

```powershell
python startup.py
```

<details>
<summary><b>怎么用</b></summary>

- **新增：** 点 **+**，输入待办，选一个或输入一个项目，想写就加备注。只看一个项目时，项目会自动填好。项目框会建议你的项目文件夹（和这个文件夹同级、有 CLAUDE.md、README.md 或 TESTING.md 的文件夹）和你用过的名字；什么名字都可以。
- **打勾：** 点方框。打过勾的会移到一条线下面，带删除线，最新的在前；**Expand** 显示它们，**Collapse** 收起来，小组件每次启动都是收起的。打勾一周后，待办会移到 `data\archive.json` 保存。
- **修改或删除：** 点那条待办。删除要再点一次确认。
- **分组还是一个列表：** 点标题栏的 **Group**。小组件会照你上次的样子、在你上次放的位置打开。

</details>

<details>
<summary><b>从 Claude 会话新增或打勾</b></summary>

用完整路径，这样在哪个文件夹都能运行；项目就用会话所在的项目文件夹名。`add` 会显示 `Added to jacks-space: …`；`done` 需要和某一条未完成待办一字不差的内容，会显示 `Ticked in jacks-space: …`。如果文件读不了，或找不到唯一一条对得上的，它会显示 `Not added: …` 或 `Not ticked: …`，什么都不改。

在 PowerShell 里，用单引号包住内容，里面的单引号要写两次（`'Jack''s list'`）。

</details>

<details>
<summary><b>开机自动启动</b></summary>

`python startup.py` 会在你的「启动」文件夹放一个叫 `To-do widget` 的快捷方式（Win+R，输入 `shell:startup`）。删掉它就不会自动启动。

这个快捷方式运行 `To-do.exe`，是 Python 的 `pythonw.exe` 改名后的副本，所以任务管理器里显示为「To-do」。它运行的还是这个文件夹里的 `widget.py`，所以改了代码只要重启它。重装 Python 或移动这个文件夹会让快捷方式失效：退出小组件，再运行一次 `python startup.py`。同一时间只会有一个在运行。

</details>

<details>
<summary><b>开发</b></summary>

| 命令 | 作用 |
|---|---|
| `python -m unittest discover -s tests` | 运行测试 |
| `python scratch\shoot.py .github\readme` | 用一份带测试待办的小组件副本，重拍这些截图 |

字体是 Hanken Grotesk（SIL Open Font License），从 `fonts\` 加载，只给小组件用；没有这些文件时用 Segoe UI。它和 [Claude usage widget](https://github.com/jacklee981229/claude-usage-widget) 用同一套样式。

</details>
