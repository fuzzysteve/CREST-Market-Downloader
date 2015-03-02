import select
import wx
from wx.lib.pubsub import setupkwargs
from wx.lib.pubsub import pub
import ConfigParser
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
from SocketServer import ThreadingMixIn
import threading
import urlparse
import base64
import os
import requests
import webbrowser
import json
import time
import csv

import pprint

inifile=os.path.dirname(__file__)+os.sep+"downloader.ini"

class authHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            return;
        parsed_path = urlparse.urlparse(self.path)
        parts=urlparse.parse_qs(parsed_path.query)
        self.send_response(200)
        self.end_headers()
        self.wfile.write('Login successful. you can close this window now')
        wx.CallAfter(pub.sendMessage, 'login', message=str(parts['code'][0]))
    def log_message(self, format, *args):
        return
    
 
# Create a new frame class, derived from the wxPython Frame.
class MyFrame(wx.Frame):

    def __init__(self, parent, id, title):
        # First, call the base class' __init__ method to create the frame
        wx.Frame.__init__(self, parent, id, title)


        # Add a panel and some controls to display the size and position
        panel = wx.Panel(self, -1)
        self.panel = panel
        self.regionCombo = wx.ComboBox(panel,-1,"Login to populate regions",style=wx.CB_READONLY|wx.CB_SORT)

        # Use some sizers for layout of the widgets

        
        self.getregion=wx.Button(panel,id=wx.ID_ANY,label='Dump Region')
        self.getregion.Bind(wx.EVT_BUTTON,self.getRegion)
        self.getregion.Disable()
        
        

        
        
        menubar = wx.MenuBar()
        login=wx.Menu()
        login.Append(101,'&Login','Log into Eve SSO');
        menubar.Append(login, '&Login')
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU,self.onLogin,id=101)
        self.regionCombo.Bind(wx.EVT_COMBOBOX,self.onRegionSelect)
        self.statusbar=self.CreateStatusBar(style=0)
        self.statusbar.SetFieldsCount(2)
        self.statusbar.SetStatusWidths([-3, -1])
        self.SetStatusText("Please Log in",0)
        
        sizer = wx.FlexGridSizer(2, 2, 5, 5)
        pub.subscribe(self.doLogin,'login')
        
        sizer.Add(self.regionCombo)
        sizer.Add(self.getregion)
        
        
        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.ALL, 15)
        panel.SetSizerAndFit(border)
        
        
        
        self.Fit()
        self.Centre()

    def getRegion(self,event):
        self.SetStatusText("Dump beginning.",0)
        itemCount=str(len(self.marketItems))
        count=0
        with open('orders.csv', 'wb') as csvfile:
            writer = csv.writer(csvfile,dialect='excel')
            writer.writerow(['Buy','typeid','volume','issued','duration','Volume Entered','Minimum Volume','range','price','locationid','locationname'])
            for item in self.marketItems:
                count+=1
                self.SetStatusText("Dumping "+item['name'],0)
                self.SetStatusText(str(count)+"/"+itemCount,1)
                wx.Yield()
                buy=self.getEndpoint(self.currentRegion['marketBuyOrders']['href'], 'application/vnd.ccp.eve.MarketOrderCollection-v1+json; charset=utf-8',{'type':item['href']})
                sell=self.getEndpoint(self.currentRegion['marketBuyOrders']['href'], 'application/vnd.ccp.eve.MarketOrderCollection-v1+json; charset=utf-8',{'type':item['href']})
                for buyitem in buy['items']:
                    writer.writerow([1,buyitem['type']['id'],buyitem['volume'],buyitem['issued'],buyitem['duration'],buyitem['volumeEntered'],buyitem['minVolume'],buyitem['range'],buyitem['price'],buyitem['location']['id'],buyitem['location']['name']])
                for sellitem in sell['items']:
                    writer.writerow([0,sellitem['type']['id'],sellitem['volume'],sellitem['issued'],sellitem['duration'],sellitem['volumeEntered'],1,sellitem['range'],sellitem['price'],sellitem['location']['id'],sellitem['location']['name']])
        self.SetStatusText("Complete.",0)        
        
        
        
        
        
        
     
    def onLogin(self,event):
        global PORT
        global CLIENTID
        webbrowser.open('https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri=http://localhost:'+`PORT`+'/&client_id='+CLIENTID+'&scope=publicData&state=')
        
    def doLogin(self,message):
        global CLIENTID
        global SECRET
        global BASEURL
        global USERAGENT
        global accessToken
        global refreshToken
        global expires
        global endPoints
        headers = {'User-Agent':USERAGENT}
        query = {'grant_type':'authorization_code','code':message}
        r = requests.get(BASEURL,headers=headers)
        endPoints=r.json()
        headers = {'Authorization':'Basic '+ base64.b64encode(CLIENTID+':'+SECRET),'User-Agent':USERAGENT}
        r = requests.post(endPoints['authEndpoint']['href'],params=query,headers=headers)
        response = r.json()
        accessToken=response['access_token']
        refreshToken=response['refresh_token']
        expires=time.time()+float(response['expires_in'])-20
        self.loadBaseData()
        
    def refreshTokens(self):
        global CLIENTID
        global SECRET
        global BASEURL
        global USERAGENT
        global accessToken
        global refreshToken
        global expires
        global endPoints
        headers = {'Authorization':'Basic '+ base64.b64encode(CLIENTID+':'+SECRET),'User-Agent':USERAGENT}
        query = {'grant_type':'refresh_token','refresh_token':refreshToken}
        r = requests.post(endPoints['authEndpoint']['href'],params=query,headers=headers)
        response = r.json()
        accessToken=response['access_token']
        refreshToken=response['refresh_token']
        expires=time.time()+float(response['expires_in'])-20

        
    def loadBaseData(self):
        global accessToken
        global refreshToken
        global expires
        global endPoints
        global USERAGENT
        headers = {'Authorization':'Bearer '+ accessToken,'User-Agent':USERAGENT}
        self.SetStatusText("Loading Regions",0)
        r = requests.get(endPoints['regions']['href'],headers=headers)
        self.regions=r.json()
        self.regionCombo.Clear()
        for item in self.regions['items']:
            self.regionCombo.Append(item['name'],item)
        self.SetStatusText("Loading Market Types",0)
        self.marketItems=self.walkMarketTypes('application/vnd.ccp.eve.MarketTypeCollection-v1+json; charset=utf-8');
        self.SetStatusText("Select a region to continue.",0)
              
        
    
    def getEndpoint(self,endpoint,accept,parameters=None):
        global accessToken
        global refreshToken
        global expires
        global USERAGENT
        if expires<time.time():
            self.refreshTokens()
        headers = {'Authorization':'Bearer '+ accessToken,
            'Accept':accept,
            'User-Agent':USERAGENT
            }
        if parameters is not None:
            r = requests.get(endpoint,params=parameters,headers=headers)
        else:
            r = requests.get(endpoint,headers=headers)
        return r.json()
    
    
    
    def walkEndpoint(self,endpoint,collection,accept,parameters=None):
        returnCollection=[]
        url=endpoint
        while True:
            walker=self.getEndpoint(url,accept,parameters)
            for item in walker[collection]:
                returnCollection.append(item)
            if walker.has_key('next'):
                url=walker['next']['href']
            else:
                break
        return returnCollection
        
        
    def walkMarketTypes(self,accept):
        returnCollection=[]
        global endPoints
        url=endPoints['marketTypes']['href']
        page=0
        while True:
            page=page+1
            self.SetStatusText("Loading Market Types:",0)
            self.SetStatusText(str(page),1)
            wx.Yield()
            walker=self.getEndpoint(url,accept)
            for item in walker['items']:
                returnCollection.append(item['type'])
            if walker.has_key('next'):
                url=walker['next']['href']
            else:
                break
        self.SetStatusText('',1)
        return returnCollection
        
        

    
    def onRegionSelect(self,event):
        selected=self.regionCombo.GetClientData(self.regionCombo.GetSelection())
        self.currentRegion=self.getEndpoint(selected['href'], 'application/vnd.ccp.eve.Region-v1+json; charset=utf-8')
        self.getregion.Enable()
        self.SetStatusText("Ready.",0)


# Every wxWidgets application must have a class derived from wx.App
class MyApp(wx.App):

    # wxWindows calls this method to initialize the application
    def OnInit(self):

        # Create an instance of our customized Frame class
        frame = MyFrame(None, -1, "Market Loader")
        frame.Show(True)

        # Tell wxWindows that this is our main window
        self.SetTopWindow(frame)

        # Return a success flag
        return True



    
if __name__ == '__main__':
    settings = ConfigParser.ConfigParser()
    settings.read(inifile)
    PORT = settings.getint('Config','Port')
    CLIENTID = settings.get('Config','Clientid')
    SECRET = settings.get('Config','Secret')
    USERAGENT = settings.get('Config','UserAgent')
    BASEURL = settings.get('Config','BaseUrl')
    accessToken = ''
    refreshToken =''
    endPoints = ''
    expires=-1
    server = HTTPServer(('', PORT), authHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    app = MyApp(0)     # Create an instance of the application class
    app.MainLoop()     # Tell it to start processing events







