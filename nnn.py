from tkinter import *
import csv
import keyboard
import socket
import os
import xml.etree.ElementTree as et
import sys

#СТАРТОВЫЕ ДАННЫЕ

UserName = os.environ["USERNAME"]
HostName = socket.gethostname()

po = ["$HOME", "$USER", "~", "ERROR"]

# ЛОГИКА

CLI_VFS = None
CLI_STARTUP = None
CONFIG_PATH = "config.xml"

CSV_LIST = []

def parse_argv():
    global CLI_VFS, CLI_STARTUP, CONFIG_PATH
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        t = args[i]
        if t == "--vfs" and i+1 < len(args):
            CLI_VFS = args[i+1]; i += 2
        elif t == "--startup" and i+1 < len(args):
            CLI_STARTUP = args[i+1]; i += 2
        elif t == "--config" and i+1 < len(args):
            CONFIG_PATH = args[i+1]; i += 2
        else:
            i += 1

parse_argv()

def xml(x):
    global com, CSV_LIST
    tree = None
    vfs = None
    startup = None
    sh = 0
    try:
        tree = et.parse(CONFIG_PATH)
    except FileNotFoundError:
        output.insert(END, "ERROR")
        return
    except et.ParseError:
        output.insert(END, "ERROR\n")
        return
    root = tree.getroot()
    vfs = root.findtext("vfs")
    startup = root.findtext("startup")

    if CLI_VFS is not None:
        vfs = CLI_VFS
    if CLI_STARTUP is not None:
        startup = CLI_STARTUP

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
                    try:
                        with open(f"{x[sh]}\\file_sys.csv", "r") as file:
                            reader = csv.reader(file, delimiter = ";")
                            for row in reader:
                                if row[0] not in ("type", "dir", "file"):
                                    output.insert(END, f"ERROR: invalid type '{row[0]}'\n")
                                    return
                                CSV_LIST.append(row)
                                output.insert(END, ",".join(row))
                                output.insert(END, "\n")
                    except FileNotFoundError:
                        output.insert(END, "ERROR, File not found")
                        return
                    print(CSV_LIST) # ЭТО ЧТОБЫ ПОСМОТРЕТЬ, РОБИТ ИЛИ НЕ РОБИТ


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
output.insert(END, f"ARGV: {' '.join(sys.argv[1:])}\n")

work("data ---startup")
keyboard.add_hotkey("enter", press)

wo = Button(root, text="Enter", command=lambda: work(txt.get()))
wo.place(relx = 0.5, y =220, width=100, height=45, anchor = "center")

root.mainloop()