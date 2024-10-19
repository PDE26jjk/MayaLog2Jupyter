# MayaLog2Jupyter
A simple Jupyter Kernel for interacting with the Autodesk Maya command line using the Jupyter Notebook and capturing output.

一个简单的 Jupyter Kernel，用于使用 Jupyter Notebook 与 Autodesk Maya 命令行交互并捕获输出。

没有debug功能。

![image-20241019195227161](https://raw.githubusercontent.com/PDE26jjk/misc/main/img/image-20241019195227161.png)

## 用法

下载后，将mayaKernel放到一个目录，将kernel.json里面的mayaLogKernel.py改成这个目录的路径，然后在你使用Jupyter的环境里将其安装为kernel

```cmd
jupyter kernelspec install /path/to/mayaKernel
```

打开maya，输入python指令，也许你可以放到userSetup.py中

```python
import maya.cmds as cmds

if not cmds.commandPort(":4434", query=True):
    cmds.commandPort(name=":4434")
```

4434是连接的端口号。接着将mayaKernel里面maya.json里的default_port也改成这个端口号。

这样之后，在Jupyter里选择maya内核，应该能连接到maya了。输入并运行python代码，将同步在maya中运行。

## 其他

为了方便使用，我设置了一些指令，在cell里面可以运行。

- 设置端口，这个指令将设置连接到maya的端口，同时也会重新绑定日志文件

```
%setPort 4435
```

- 输入mel代码，这个指令将%mel 之后的视作mel代码发送到maya

```
%mel // """ mel代码可以这么写
string $ll[] = `ls -dag -long`;
print $ll;
// """
```



  ## 参考

- [cmcpasserby/MayaCharm](https://github.com/cmcpasserby/MayaCharm)

- [制作简单的Python包装器内核](https://daobook.github.io/jupyter_client/wrapperkernels.html)
