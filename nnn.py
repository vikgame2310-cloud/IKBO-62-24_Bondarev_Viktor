from tkinter import *
import keyboard
import socket
import os

UserName = os.environ["USERNAME"]
HostName = socket.gethostname()

po = ["$HOME", "$USER", "~", "ERROR"]

# ЛОГИКА



def uncorrect():
    output.insert(END, "ERROR!\n")


def press():
    work(txt.get())

def go(con):
    if len(con)==1:
        con += po[2]
    for i in po:
        if i in con[1]:
            match i:
                case "$HOME":
                    x = con[1].replace("$HOME", os.environ["USERPROFILE"] )
                    output.insert(END, x + "\n")
                    return
                case "$USER":
                    x = con[1].replace("$USER", UserName )
                    output.insert(END, x + "\n")
                    return
                case "~":
                    x = con[1].replace("~", os.path.expanduser("~") )
                    output.insert(END, x + "\n")
                    return
    output.insert(END, con[1] + "\n")


def pap(con):
    s =""
    output.insert(END, con[0] + f": args = [{s}]" + "\n")

def work(command):
    con = command.split()
    if not con:
        return

    if len(con) > 2:
        uncorrect()
        return
    if con[0] == "exit" and len(con) == 1:
        root.destroy()
    elif con[0] == "ls":
        pap(con)
    elif con[0] == "cd":
        go(con)
    else:
        uncorrect()
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

keyboard.add_hotkey("enter", press)

wo = Button(root, text="Enter", command=lambda: work(txt.get()))
wo.place(relx = 0.5, y =220, width=100, height=45, anchor = "center")

root.mainloop()