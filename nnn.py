from tkinter import *
import keyboard
import socket
import os
import xml.etree.ElementTree as et



#СТАРТОВЫЕ ДАННЫЕ

UserName = os.environ["USERNAME"]
HostName = socket.gethostname()

po = ["$HOME", "$USER", "~", "ERROR"]

# ЛОГИКА



def xml(x):
    global com
    tree = None
    vfs = None
    startup = None
    sh = 0
    try:
        tree = et.parse("config.xml")
    except FileNotFoundError:
        output.insert(END, "ERROR")
        return
    except et.ParseError:
        output.insert(END, "ERROR\n")
        return
    root = tree.getroot()
    vfs = root.findtext("vfs")
    startup = root.findtext("startup")
    if vfs is None or startup is None:
        output.insert(END, "ERROR: vfs or startup not found")
        return
    for alement in x:
        if alement == "---config.xml" or alement == "---vfs" or alement == "---startup":
            sh+=1
            if sh < len(x):
                if x[sh] not in ("---config.xml","---vfs","---startup", "data") :
                    print(x[sh])
                    sh += 1
            sh -= 1
            match alement:
                case "---config.xml":
                    if tree == None or vfs == None or startup == None:
                        output.insert(END, "Error" + "\n")
                    else:
                        output.insert(END, vfs + "\n" + startup + com + "\n")
                case "---vfs":
                    if x[sh] != vfs:
                        x[sh] = vfs
                    output.insert(END, x[sh] + com + "\n")
                case "---startup":
                    if x[sh] != startup:
                        x[sh] = startup
                    c = open(x[sh])
                    for f in c:
                        st_com = f.strip()
                        output.insert(END, st_com + "\n")
                        work(st_com)


def press():
    work(txt.get())

def go(con):
    global com
    if len(con) > 2:
        output.insert(END, "ERROR!\n")
        return
    if len(con)==1:
        con += po[2]
    for i in po:
        if i in con[1]:
            match i:
                case "$HOME":
                    x = con[1].replace("$HOME", os.environ["USERPROFILE"] )
                    output.insert(END, x + com + "\n")
                    return
                case "$USER":
                    x = con[1].replace("$USER", UserName )
                    output.insert(END, x + com + "\n")
                    return
                case "~":
                    x = con[1].replace("~", os.path.expanduser("~") )
                    output.insert(END, x + com + "\n")
                    return
    output.insert(END, con[1] + com + "\n")

def pap(con):
    s =""
    output.insert(END, con[0] + f": args = [{s}]" + "\n")

def work(command):
    global com
    com = ""
    con = command.split()
    if not con:
        return

    for idx, token in enumerate(con):
        if token == ("#"):
            c = con[idx:]
            com = " ".join(c)
            con = con[:idx]
            break


    if con[0] == "exit" and len(con) == 1:
        root.destroy()
    elif con[0] == "ls":
        pap(con)
    elif con[0] == "cd":
        go(con)
    elif con[0] == "data":
        xml(con[1:])

    else:
        output.insert(END, "ERROR!\n")
        return



# ОКНО
root = Tk()
root.title(f" Эмулятор - {UserName}@{HostName}")
root.geometry("640x480")
hello = Label(root, fg="blue", text = "HELLO", font = (14))
hello.place(relx = 0.5, y = 75, anchor="center")

# РАБОЧИЕ ОБЛАСТ
txt = Entry(root, width=50)
txt.place(relx = 0.5, y =155, anchor ="center")

output = Text(root, height=10, width=67)
output.place(relx = 0.5, y=360, anchor = "center")
output.insert(END,f"Hello, {UserName}" "\n")

work("data ---startup")
keyboard.add_hotkey("enter", press)

wo = Button(root, text="Enter", command=lambda: work(txt.get()))
wo.place(relx = 0.5, y =220, width=100, height=45, anchor = "center")

root.mainloop()