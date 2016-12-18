#!/usr/bin/python
# $id$
# pyCVS a python library for the Concurrent Versions System (CVS) protocol.
# Copyright (C) 2003 rad2k Argentina.
#
# pyCVS is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

# For Contact information read the AUTHORS file.

import socket
import select
import bisect
import time

"""
 _^_      -----------------------------------------------------------------
dO_ob   _/ hi there. I'm a monkey. I hope you find this library useful.   /
 (o)  <    Any complains or suggestions are appreciated. Please feed me. /
 <|>   \________________________________________________________________/
 2#         this monkey was ascii'ed by rad2k at mail dot ru (c) 2003
 / \          questions/suggestions/complains/money/bananas
               should be mailed to rad2k @ mail . ru

TODO:
    * check blocking version works as expected
"""

g_cvsevents = [    # list of supported cvs events
    "loginok",
    "loginfail",
    "updatedfile"
]


class BaseCVSClient:
    """
    Class name: BaseCVSClient
    Description:
        basic client, inherit from this class and define your own
        on_$event methods which will be registered as event handlers.
    """
    def __init__(self):
        # instance the main CVS class
        self.cvs = CVS()

        # register all callbacks/event handlers for all servers
        for eventname in g_cvsevents:
            m = "on_" + eventname
            self.cvs.addevent(eventname, getattr(self, m), 0)

    def newserver(self, address, port, sync):
        return self.cvs.newserver(address, port, sync)


class CVSException(Exception):
    """
    Class name: CVSException
    Description: CVS class exception

    """
    pass


class CVS:
    """
    Class name: CVS
    Description:
        newserver() returns a Cservercvs object.

    """
    def __init__(self):
        """ list of Cservercvs objs """
        self.cvsobjs = []
        """ global handlers dictionary """
        self.ghandlers = {}
        self.exiting = 0

    def checkio_all(self, timeout=0):
        """ calls checkio on every Cservercvs obj and returns. """
        if not self.cvsobjs:
            time.sleep(timeout)

        for srv in self.cvsobjs:
            try:
                if srv.asyncversion:
                    srv.checkio(timeout)
                else:
                    srv.checkio(-1)

            except:    # should we exit here? fix this later
                raise (CVSException, "checkio_all: checkio failed")
        return

    def checkio_loop_all(self, timeout=0.2):
        """ block looping inside checkio of every Cservercvs obj
        with a sleeping timeout. """
        while 1 and not self.exiting:
            try:
                self.checkio_all(timeout)
            except:
                return

    def cleanup(self):
        self.exiting = 1

    def newserver(self, address, port, sync=0):

        """ does the user want a sync. version? """
        if sync:
            newobj = Csyncservercvs(address, port)
        else:
            newobj = Casyncservercvs(address, port)

        self.cvsobjs.append(newobj)

        """ register the existing events in the new server """
        for en in g_cvsevents:
            for h in self.ghandlers.get(en, []):
                try:
                    newobj.addevent(en, h[1], h[0])
                except:    # should we exit here?
                    raise (CVSException, "newserver: srv.addevent failed")

        return newobj

    def addevent(self, eventname, handler, priority=0):
        """ used to globally add event handlers for all servers
        which are instanced through this CVS interface.
        The event handlers (callbacks) are stored locally in order
        to keep new servers (created after the call to this
        method) updated. """

        """
        check if the event name doesn't exist in the dictionary.
        if it doesn't add an entry as a list.
        """
        if eventname not in self.ghandlers:
            self.ghandlers[eventname] = []

        """ sort by priority inside the list by calling
        bisect.insort_right """

        bisect.insort(self.ghandlers[eventname], (priority, handler))

        """ register the existing events in each server dispatcher """
        for srv in self.cvsobjs:
            for en in g_cvsevents:
                for h in self.ghandlers.get(en, []):
                    try:
                        srv.addevent(en, h[1], h[0])
                    except:    # should we exit here?
                        raise (CVSException, "addevent: srv.addevent failed")

"""
Singleton implementation for python.
thanks to riq + TEG (teg.sourceforge.net) for sample code.

class Singleton:
    __single = None

    def __init__(self):
        if Singleton.__single:
            raise Singleton.__single
        Singleton.__single = self

def Handle(x = Singleton):
    try:
        # first time instance?
        single = x()
    except Singleton, s:
        # aha! already instanced
        single = s
    return single
"""


class Cevent:
    """
    Class name: Cevent
    Description: an event

    """
    def __init__(self, name, params, instance):
        self.eventname = name
        self.params = params
        self.instance = instance

    def get_name(self):
        return self.eventname

    def get_params(self):
        return self.params

    # returns the instance of the server it belongs to.
    def get_instance(self):
        return self.instance


class DispaException(Exception):
    """
    Class name: DispaException
    Description: Ceventdispa exception

    """
    pass


class Ceventdispa:
    """
    Class name: Ceventdispa
    Description:    * we create a dispatcher per servercvs instance.

    """
    def __init__(self):
        self.ehandlers = {}

    def addeventhook(self, eventname, handler, priority=0):
        """ adds 1 or more event handlers for eventname.
        if there are more than one handler for an event,
         they are sorted and called by $priority """

        """
        check if the event name doesn't exist in the dictionary.
        if it doesn't add an entry as a list.
        """
        if eventname not in self.ehandlers:
            self.ehandlers[eventname] = []

        """ sort by priority inside the list by calling
        bisect.insort_right """

        bisect.insort(self.ehandlers[eventname], (priority, handler))

    def calleventhook(self, event):
        for h in self.ehandlers.get(event.get_name(), []):
            """ is there a handler function? """
            h[1](event)


class NetworkException(Exception):
    """
    Class name: NetworkException
    Description: Cnetwork exception

    """
    pass


class Cnetwork:
    """
    Class name: Cnetwork
    Description: we create a network interface per servercvs instance

    """
    def __init__(self):
        self.socket = 0
        self.address = ""
        self.port = 0

        self.set_connected(0)

    def connect(self, address, port):
        """ connects to a given server address and port """
        self.address = address
        self.port = port

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        """ now try to connect """
        try:
            self.socket.connect((self.address, self.port))
            self.set_connected(1)

        except socket.error as x:
            self.set_connected(0)
            raise (NetworkException,
                   "Unable to connect to %s port %s: %s" %
                   (self.address, self.port, x))

        return

    def close(self):
        """ closes the local socket """
        self.set_connected(0)
        try:
            self.socket.close()
        except socket.error as x:
            raise NetworkException

    def send(self, data):
        try:
            self.socket.send(data)
        except socket.error as x:
            raise (NetworkException,
                   "Failed sending to %s port %s\n%s" %
                   (self.address, self.port, x))

    def read(self, size):
        readbuf = ""
        try:
            readbuf = self.socket.recv(size)
        except socket.error as x:
            raise (NetworkException,
                   "Failed reading from %s port %s\n%s" %
                   (self.address, self.port, x))

        if readbuf == "":
            raise (NetworkException,
                   "Failed reading from %s port %s\n"
                   "Error while reading from socket (EOF?)\n" %
                   (self.address, self.port))

        return readbuf

    def read_nl(self):
        # read until we meet a newline
        x = out = ""
        while x != "\n":
            out += x
            try:
                x = self.read(1)
            except:
                raise NetworkException
        return out

    def read_cmd(self):
        # read until we meet a 0x20
        out = x = ""
        while x != " ":
            out += x
            try:
                x = self.read(1)
            except:
                raise NetworkException
        return out

    def socketready(self, timeout=0):
        """
        select with $timeout on the cvs server socket.
        """

        if not self.socket:
            raise (NetworkException, "socket not connected.")

        r, w, e = select.select([self.socket], [], [], timeout)
        if self.socket not in r:
            raise (NetworkException, "socket not ready.")

        """ theres data to read in the socket """
        return

    # properties ################################################

    def get_connected(self):
        return self.connected

    def set_connected(self, value):
        self.connected = value


class Cfile:
    """
    Class name: Cfile
    Description: a file

    """
    def __init__(self, path, entries, mode, size, data):
        self.path = path
        self.entries = entries
        self.mode = mode
        self.size = size
        self.data = data

    def get_path(self):
        return self.path

    def get_entries(self):
        return self.entries

    def get_mode(self):
        return self.mode

    def get_size(self):
        return self.size

    def get_data(self):
        return self.data


class Crequest:
    """
    Class name: Crequest
    Description: a CVS request

    """
    def __init__(self, data=0):
        self.reqdata = data
        self.sent = 0
        self.retries = 5
        self.replied = 0

    def get_data(self):
        return self.reqdata

    def set_sent(self, value=1):
        self.sent = value

    def get_sent(self):
        return self.sent

    def set_retries(self, retries):
        self.retries = retries

    def get_retries(self):
        return self.retries

    def set_replied(self, value=1):
        self.replied = value

    def get_replied(self):
        return self.replied


class Cresponse:
    """
    Class name: Cresponse
    Description: a CVS response

    """
    def __init__(self, name, data=0):
        self.resname = name
        self.resdata = data

    def get_data(self):
        return self.resdata

    def get_name(self):
        return self.resname


class ProtocolException(Exception):
    """
    Class name: ProtocolException
    Description: Cprotocol exception

    """
    pass


class Cprotocvs:
    """
    Class name: Cprotocvs
    Description: takes care of the CVS protocol implementation.

    """
    def __init__(self, adaptercallback, address, port, replycallback=None):
        # our queue of outgoing Crequests
        self.sendqueue = []

        # create a network interface object
        self.objnet = Cnetwork()

        # store the adapter to use for notifying responses.
        self.adapter = adaptercallback

        # used mostly by synchronous server versions
        self.replycallback = replycallback

        self.set_loggedin(0)
        self.set_authorized(0)
        self.sent_authreq = 0

        self.address = address
        self.port = port

        self.workingpath = ""

        # dictionary for encoding the authentication password
        self.encoding = {'!': 120, '"': 53, '%': 109,
                         '&': 72, "'": 108, '(': 70,
                         ')': 64, '*': 76, '+': 67,
                         ',': 116, '-': 74, '.': 68,
                         '/': 87, ': ': 112, ';': 86,
                         '<': 118, '=': 110, '>': 122,
                         '?': 105, '_': 56,

                         '0': 111, '1': 52, '2': 75,
                         '3': 119, '4': 49, '5': 34,
                         '6': 82, '7': 81, '8': 95,
                         '9': 65,

                         'A': 57, 'B': 83, 'C': 43,
                         'D': 46, 'E': 102, 'F': 40,
                         'G': 89, 'H': 38, 'I': 103,
                         'J': 45, 'K': 50, 'L': 42,
                         'M': 123, 'N': 91, 'O': 35,
                         'P': 125, 'Q': 55, 'R': 54,
                         'S': 66, 'T': 124, 'U': 126,
                         'V': 59, 'W': 47, 'X': 92,
                         'Y': 71, 'Z': 115,

                         'a': 121, 'b': 117, 'c': 104,
                         'd': 101, 'e': 100, 'f': 69,
                         'g': 73, 'h': 99, 'i': 63,
                         'j': 94, 'k': 93, 'l': 39,
                         'm': 37, 'n': 61, 'o': 48,
                         'p': 58, 'q': 113, 'r': 32,
                         's': 90, 't': 44, 'u': 98,
                         'v': 60, 'w': 51, 'x': 33,
                         'y': 97, 'z': 62
                         }

    # cvs internal requests #######################################
    def encodepassword(self, input):
        """ used to encode the password the CVS way.
        Note: Control characters, space, and characters outside
        the invariant ISO 646 character set are ignored!.
        """
        output = "A"

        for ch in input:
            tmp = self.encoding.get(ch, [])
            output += chr(tmp)

        return output

    def req_auth(self):
        """
        sends a BEGIN_AUTH_REQUEST.
        This method is called by sendrequest() to request authorization
        before sending any requests.
        """

        """ generate the authorization request packet """
        authstring = "BEGIN AUTH REQUEST" + "\n" \
            + self.cvsroot + "\n" + self.username + "\n" \
            + self.encodedpassword + "\n" + \
            "END AUTH REQUEST" + "\n"

        print("\n", authstring)

        try:
            self.objnet.send(authstring)
            print("request authorization sent.")
        except NetworkException as x:
            print(x)
            return

    def req_login(self):
        """
        sends a BEGIN_VERIFICATION_REQUEST.
        """
        self.encodedpassword = self.encodepassword(self.password)

        """ generate the login packet """
        loginstring = "BEGIN VERIFICATION REQUEST" + "\n" \
            + self.cvsroot + "\n" + self.username + "\n" \
            + self.encodedpassword + "\n" + \
            "END VERIFICATION REQUEST" + "\n"

        print("\n", loginstring)

        try:
            self.objnet.send(loginstring)
        except NetworkException as x:
            print(x)
            return

    # more methods ##################################################

    def sendrequest(self, requestobj):
        """
        This is the method that should be called for
        sending requests to a cvs server. It first checks
        if we are connected to the server, then sends an
        authorization request if this set of requests
        isn't authorized, and finally queues the requests.
        """
        # are we connected and logged in? else it makes no sense.
        self.do_sessioncheck()

        # add the request to the send list.
        self.sendqueue.append(requestobj)
        print("request added to queue.")

        if not self.get_authorized() and not self.sent_authreq:
            # send an authorization request right now!.
            print("sending an authorization request..")
            self.req_auth()
            self.sent_authreq = 1

    def processrequests(self):
        # checks if we have pending requests to send

        for req in self.sendqueue:
            if not req.get_sent() and self.get_authorized():
                """ we have an authorized request."""
                print("sending an authorized request - ")
                print(req.get_data())
                self.objnet.send(req.get_data())
                req.set_sent()

    def timeoutrequests(self):
        """ called for removing timed out or replied requests """
        self.tempremoval = []

        # checks if we have pending requests to send
        for req in self.sendqueue:
            if req.get_sent() and req.get_replied():
                """ we have a replied request """
                self.tempremoval.append(req)

        # remove requests. we dont remove items from the
        # list during the for loop above because it screws things up
        # this is why we have a new temporal removal list
        for req in self.tempremoval:
            self.sendqueue.remove(req)

    def processresponse(self):
        # called when there is data to read in the socket
        cmd = rest = ""

        # read the incoming command
        try:
            cmd = self.objnet.read_cmd()
        except:
            return

        # read the rest of the response
        try:
            rest = self.objnet.read_nl()
        except:
            return

        if cmd == "I":
            if rest == "LOVE YOU":
                if self.get_loggedin():
                    """ authorization reply """
                    self.res_auth(1)
                    return
                else:
                    """ login successfull """
                    self.res_login(1)
                    return

            elif rest == "HATE YOU":
                if self.get_loggedin():
                    """ authorization denied """
                    self.res_auth(0)
                    return
                else:
                    """ login failed """
                    self.res_login(0)
                    return
            else:
                raise (ServerException,
                       "unknown answer during login: %s\n"
                       % (cmd + rest))

        elif cmd == "Valid-requests":
            self.res_validrequests(rest)

        elif cmd == "Updated":
            self.res_updated(rest)
        else:
            print("UNKNOWN - cmd: %s - data: %s" % (cmd, rest))
            raise(ServerException, "unknown response received.")

        # read the status of the reply (ok or error)
        try:
            reply = self.objnet.read_nl()
        except:
            print("error reading reply")
            return

        if reply == "ok":
            print("recibi un ok!! con rest", rest)
            if self.replycallback:
                self.replycallback(reply)

            # set the oldest non replied request to replied.
            for req in self.sendqueue:
                if req.get_sent() and not req.get_replied():
                    req.set_replied()
                    print("setting request to replied.")
                    print("req data is: ", req.get_data())
                    break

        elif reply == "error":
            print("recibi un error!!")
            self.replycallback(reply)

        else:
            print("unknown reply received!!!!: %s" % (reply))

    def cycle_check(self, timeout=0):
        # check if we have requests to send
        self.processrequests()

        # we use a timeout of -1 for blocking server versions
        if timeout >= 0:
            try:
                # is socket ready? else raise an exception
                self.objnet.socketready(timeout)
            except:
                return
        else:
            print("blocking version..")

        try:
            # socket is ready to be read.
            self.processresponse()

        except:
            pass

    def do_connection(self):
        # used to connect to a cvs server if not connected already
        if not self.address or not self.port:
            raise NetworkException

        if not self.objnet.get_connected():
            try:
                self.objnet.connect(self.address, self.port)
            except NetworkException as x:
                print(x)
                raise NetworkException

    def do_login(self, *args):
        # takes care of connecting and sending a login request
        self.username = args[1]
        self.password = args[2]
        self.cvsroot = self.workingpath = args[0]

        """ connect to the given server to initiate login """
        try:
            self.do_connection()
        except NetworkException as x:
            print(x)
            return

        """ connection ok, send a login request """
        try:
            self.req_login()
        except ProtocolException as x:
            print(x)
            return

    def do_sessioncheck(self):
        """ should be called to make sure
        we are logged in and connected to the server """

        if not self.get_loggedin():
            raise(NetworkException, "Not logged in.")

        """ we were logged in but the socket is down. """
        if not self.objnet.get_connected():
            self.do_connection()

    def do_listmodules(self):
        self.req_argument(".")
        self.req_directory(".")
        self.req_expandmodules()

    def do_checkoutall(self):
        self.req_argument("-N")
        self.req_argument(".")
        self.req_directory(".")
        self.req_co()

    def do_checkout(self, *args):
        modulename = args[0]
        self.req_argument("-N")
        self.req_argument(modulename)
        self.req_directory(".")
        self.req_co()

    # cvs requests ################################################

    def req_validresponses(self):
        # tell the server which responses we accept
        return

    def req_validrequests(self):
        # ask the server to send back what requests it accepts.
        # response expected?: yes
        myreq = "valid-requests " + "\n"

        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_root(self):
        # tell the server which CVSROOT path to use.
        # this request should be sent during init and only once.
        # response expected?: no
        myreq = "Root " + self.cvsroot + "\n"

        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_directory(self, workingdirectory):
        # tell the server what base directory to use.
        # we send the directory name and then attach the base path.
        # (the base directory is relative to the attached base path)
        # response expected?: no
        myreq = "Directory " + workingdirectory + "\n" + \
            self.workingpath + "\n"

        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_useunchanged(self):
        # a dummy request. If the server replies, we have an
        # incompatible CVS protocol version.
        # response expected?: no
        myreq = "UseUnchanged " + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_argument(self, arg):
        # store an argument in the server for future use
        # by an arguments-command request.
        # response expected?: no
        myreq = "Argument " + arg + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_argumentx(self, arg):
        # store an argument in the server for future use
        # by an arguments-command request. (tells the server
        # to append a '\n' + argument to the arguments stack)
        # response expected?: no
        myreq = "Argumentx " + arg + " " + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_set(self, variable, value):
        # set a user variable to value
        # response expected?: no
        myreq = "Set " + variable + "=" + value + " " + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_expandmodules(self):
        # ask the server to expand the given module names.
        # (arguments-command) arguments taken: module names
        # requests on server side.
        # response expected?: yes
        myreq = "expand-modules " + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_co(self):
        # get files from the repository.
        # (arguments-command) arguments taken: module names
        # response expected?: yes
        myreq = "co " + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    def req_export(self):
        # get files from the repository.
        # the sources retrieved using export dont have CVS information.
        # (arguments-command) arguments taken: module names
        # response expected?: yes
        myreq = "export " + "\n"
        try:
            self.sendrequest(Crequest(myreq))
        except ProtocolException as x:
            print(x)
            return

    # cvs responses ################################################

    def res_auth(self, authorized):
        # set ourselves as authorized for sending requests.
        print("authorization response received")

        if not self.get_authorized():
            if not authorized:
                print("authorization request DENIED")
            else:
                print("authorization request GRANTED")
                self.set_authorized(1)
        else:
            print("res_auth: received double authorization!")

    def res_login(self, reply):
        # close the connection to the server. we are authenticated.
        try:
            self.objnet.close()
        except:
            pass

        if reply == 1:
            self.set_loggedin(1)

            # finish the protocol negotiation..

            # send the Root request
            self.req_root()

            # send our accepted valid responses
            # self.req_validresponses()

            # ask for the server's valid requests
            self.req_validrequests()

            # check we have a compatible protocol version
            self.req_useunchanged()

            self.adapter(Cresponse("loginok"))
        else:
            self.set_loggedin(0)
            self.adapter(Cresponse("loginfail"))

    def res_validrequests(self, requestlist):
        # what requests the server is willing to accept.
        print("the server is willing to accept the "
              "following requests:\n%s" % (requestlist))

    def res_updated(self, pathname):
        # update the local client-side copy of the received files
        # with this new lastest revision.
        fullpath = self.objnet.read_nl()
        newentries = self.objnet.read_nl()
        mode = self.objnet.read_nl()
        filesize = self.objnet.read_nl()

        # read the whole incoming file data
        filedata = ""
        toread = int(filesize)
        while toread:
            try:
                tmp = self.objnet.read(toread)
                toread -= len(tmp)
                filedata += tmp
            except:
                pass

        # send the incoming file to the adapter
        self.adapter(Cresponse("updatedfile",
                               Cfile(fullpath, newentries, mode,
                                     filesize, filedata)))

    # properties ################################################

    def get_authorized(self):
        return self.authorized

    def set_authorized(self, value):
        self.authorized = value

    def get_loggedin(self):
        return self.loggedin

    def set_loggedin(self, value):
        self.loggedin = value


class ServerCVSException(Exception):
    """
    Class name: ServerCVSException
    Description: Cservercvs exception

    """
    pass


class Cservercvs:
    """
    Class name: Cservercvs
    Description: The father of a/sync. server versions.

    """
    def __init__(self, address, port, replycallback=None):

        # create an events dispatcher object
        self.objdispa = Ceventdispa()

        # create a protocol object
        self.objprotocvs = Cprotocvs(self.hprotocolin, address,
                                     port, replycallback)

        self.exiting = 0

    def addevent(self, eventname, handler, priority=0):
        """ wrapper for addeventhook in the dispatcher object """
        self.objdispa.addeventhook(eventname, handler, priority)

    def throwevent(self, eventname, data):
        """ wrapper for calleventhook in the dispatcher object """
        print("triggering event name: %s" % eventname)
        self.objdispa.calleventhook(Cevent(eventname, data, self))

    """ ADAPTER IN - called by the protocol obj """
    def hprotocolin(self, response):
        """ receives a response from the protocol obj and throws
        the respective events. """

        print(response.get_name(), response.get_data())
        # in our library implementation, we use the response names
        # as the same names of the events we trigger.
        self.throwevent(response.get_name(), response.get_data())

    """ ADAPTER OUT - calls protocol methods.
    This is a PURE VIRTUAL Method. Allows A/Sync. """
    def hprotocolout(self, reqname, *args):
        raise(ServerCVSException, "hprotocolout NOT IMPLEMENTED!")

    def checkio(self, timeout=0):
        """ add here any other methods to call """
        self.objprotocvs.cycle_check(timeout)

    def checkio_loop(self, timeout=0.2):
        """ block looping inside checkio with a sleeping timeout.  """
        while 1 and not self.exiting:
            try:
                self.checkio(timeout)
            except:
                """ if something happends, we quit the loop """
                return

    def cleanup(self):
        self.exiting = 1

    def login(self, cvsroot, username="anonymous", password=""):
        return self.hprotocolout("do_login", cvsroot, username, password)

    def logout(self):
        return

    def checkout(self, modulename):
        return self.hprotocolout("do_checkout", modulename)

    def checkoutall(self):
        return self.hprotocolout("do_checkoutall")

    def is_loggedin(self):
        return self.objcvsproto.get_loggedin()


class ServerException(Exception):
    """
    Class name: ServerException
    Description: Cserver exception

    """
    pass


class Casyncservercvs(Cservercvs):
    """
    Class name: Casyncservercvs
    Description: CVS Asynchronous version.

    """
    def __init__(self, address, port):
        self.asyncversion = 1
        Cservercvs.__init__(self, address, port)

    """ ADAPTER OUT - Implement the ASYNCHRONOUS version. """
    def hprotocolout(self, reqname, *args):
        print("ESTOY EN LA VERSION ASYNC!")
        funcp = getattr(self.objprotocvs, reqname)
        return funcp(*args)


class Csyncservercvs(Cservercvs):
    """
    Class name: Csyncservercvs
    Description: CVS Synchronous version.

    """
    def __init__(self, address, port):
        self.asyncversion = 0
        self.keepwaiting = 1

        """ the SYNCHRONOUS version registers an extra callback
        for receiving notices when a request is completely replied """
        Cservercvs.__init__(self, address, port, self.receivedreply)

    """ ADAPTER OUT - Implement the SYNCHRONOUS version. """
    def hprotocolout(self, reqname, *args):
        print("ESTOY EN LA VERSION SYNC!")
        funcp = getattr(self.objprotocvs, reqname)
        ret1 = funcp(*args)

        # we block on checkio
        while self.keepwaiting:
            try:
                self.checkio(-1)
            except:
                break

        print("termino un request!")
        self.keepwaiting = 1

    """ only for SYNCHRONOUS version. """
    def receivedreply(self, value):
        self.keepwaiting = 0
