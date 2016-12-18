#!/usr/bin/python
# $id$
# pyCVS sample CVS client
# by rad2k at mail dot ru (c) 2003

from wxPython.wx import *
from pycvs import BaseCVSClient
import threading
import os

ID_ABOUT = 101
ID_EXIT     = 102
ID_BUTTON1 = 110
g_title     = "pyCVS example"

class CSampleCVSClient(BaseCVSClient):
    def __init__(self, frameobj):
        self.frameobj = frameobj
        BaseCVSClient.__init__(self)

    def on_loginok(self, event):
        self.frameobj.on_cvsloginok(event)

    def on_loginfail(self, event):
        self.frameobj.on_cvsloginfail(event)

    def on_updatedfile(self, event):
        self.frameobj.on_cvsupdatedfile(event)

    def loop(self):
        self.cvs.checkio_loop_all()

    def quit(self):
        self.cvs.cleanup()


class CSampleFrame(wxFrame):
    def __init__(self, parent, ID, title):
        wxFrame.__init__(self, parent, ID, title,
            wxDefaultPosition,
            wxSize(400,250))

        ################ cvs library initialization
        self.cvsobj = CSampleCVSClient(self)
        # create a thread for the cvs library
        self.cvsthread = threading.Thread(target=self.cvsobj.loop)
        self.cvsthread.start()


        ############## create a status bar
        self.CreateStatusBar()
        self.SetStatusText(g_title)

        ############## create top menus
        menufile = wxMenu()
        menuabout = wxMenu()
        menufile.Append(ID_EXIT, "E&xit", "Terminate")
        menufile.AppendSeparator()
        menuabout.Append(ID_ABOUT, "&About pyCVS", "More info")
        menuabout.AppendSeparator()
        menuBar = wxMenuBar()
        menuBar.Append(menufile, "&File");
        menuBar.Append(menuabout, "&About");
        self.SetMenuBar(menuBar)

        ############## set event handlers
        EVT_MENU(self, ID_ABOUT, self.OnAbout)
        EVT_MENU(self, ID_EXIT, self.OnExit)

        ############# draw controls
        self.hostnamel = wxStaticText(self,
                        -1,
                        "hostname:",
                        wxPoint(20,10))

        self.hostnamet = wxTextCtrl(self,
                        -1,
                        "cvs.sourceforge.net",
                        wxPoint(150, 10),
                        wxSize(140, -1))

        self.portt = wxTextCtrl(self,
                        -1,
                        "2401",
                        wxPoint(300, 10),
                        wxSize(40, -1))

        self.cvsrootl = wxStaticText(self,
                        -1,
                        "CVSROOT:",
                        wxPoint(20,40))

        self.cvsroott = wxTextCtrl(self,
                        -1,
                        "/cvsroot/pycvs",
                        wxPoint(150, 40),
                        wxSize(140, -1))

        self.modulel = wxStaticText(self,
                        -1,
                        "module:",
                        wxPoint(20,70))

        self.modulet = wxTextCtrl(self,
                        -1,
                        "pycvs/",
                        wxPoint(150, 70),
                        wxSize(140, -1))


        self.usernamel = wxStaticText(self,
                        -1,
                        "username:",
                        wxPoint(20,100))

        self.usernamet = wxTextCtrl(self,
                        -1,
                        "anonymous",
                        wxPoint(150, 100),
                        wxSize(140, -1))


        self.passwordl = wxStaticText(self,
                        -1,
                        "password:",
                        wxPoint(20,130))

        self.passwordt = wxTextCtrl(self,
                        -1,
                        "",
                        wxPoint(150,130),
                        wxSize(140, -1))

        self.savepathl = wxStaticText(self,
                        -1,
                        "Destination path:",
                        wxPoint(20,160))

        self.savepatht = wxTextCtrl(self,
                        -1,
                        "/tmp",
                        wxPoint(150,160),
                        wxSize(140, -1))

        self.checkoutb = wxButton(self,
                    10,
                    "Checkout",
                    wxPoint(300,70))

        self.quitb = wxButton(self,
                    33,
                    "QUIT",
                    wxPoint(300,100))


        EVT_BUTTON(self, 10, self.OnCheckout)
        EVT_BUTTON(self, 33, self.OnExit)


    def OnCheckout(self, event):
        # check if the specified dest path exists
        self.destdir = self.savepatht.GetValue()
        if not os.path.exists(self.destdir) or os.path.isfile(self.destdir):
            dlg = wxMessageDialog(self,
            "Invalid destination path or path doesn't exist",
                    "destination path error",
                    wxOK)
            dlg.ShowModal()
            dlg.Destroy()
            return

        self.cvsroot     = self.cvsroott.GetValue()
        self.hostname = self.hostnamet.GetValue()
        self.port = self.portt.GetValue()
        self.module = self.modulet.GetValue()

        if not self.cvsroot or \
        not self.hostname or \
        not self.port or \
        not self.module:

            dlg = wxMessageDialog(self,
                    "Missing required values",
                    "missing CVSROOT/HOSTNAME/PORT",
                    wxOK)
            dlg.ShowModal()
            dlg.Destroy()
            return

        self.username = self.usernamet.GetValue()
        self.password = self.passwordt.GetValue()

        self.myserver = self.cvsobj.newserver(self.hostname,
                            int(self.port),
                            0)
        self.myserver.login(self.cvsroot)

        return

    def OnAbout(self, event):
        dlg = wxMessageDialog(self,
                    "made by rad2k at mail dot ru",
                    "About pyCVS",
                    wxOK | wxICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self, event):
        self.cvsobj.quit()
        self.Close(true)

    # cvs client events
    def on_cvsloginok(self, event):
        print("loginok!")
        self.myserver.checkout(self.module)

    def on_cvsloginfail(self, event):
        print("login failed")

    def on_cvsupdatedfile(self, event):
        file = event.get_params()

        # check all directories in the path exist
        fullpath = self.destdir

        parts, name, ext = self.ParseFile(file.get_path())
        # create directories if they don't exist
        for x in parts:
            fullpath += "/" + x
            if not os.path.exists(fullpath):
                os.mkdir(fullpath)

        fullpath += "/" + name + ext
        with open(fullpath, 'w') as fd:
            fd.write(file.get_data())

    def ParseFile(self, file):
        (root, ext) = os.path.splitext(file)
        (x, name) = os.path.split(root)

        # dummy value
        y = '-'
        parts = []
        while y != '':
            (x, y) = os.path.split(x)
            parts.append(y)

        parts = parts[:-1]
        if x:
            parts.append(x)
        parts.reverse()

        return (parts, name, ext)

class CSampleWindow(wxApp):
    def OnInit(self):
        self.frame = CSampleFrame(NULL, -1, g_title)
        self.frame.Show(true)
        self.SetTopWindow(self.frame)
        return true

myapp = CSampleWindow(0)
myapp.MainLoop()
