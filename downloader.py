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
import webbrowser
import json
import time
import csv
import requests
import grequests
import time
import locale


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
class marketView(wx.Frame):

    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title)
        panel = wx.Panel(self, -1)
        self.panel = panel
        self.login=wx.Button(panel,id=wx.ID_ANY,label='Login')
        self.regionCombo = wx.ComboBox(panel,-1,"Login to populate regions",style=wx.CB_READONLY|wx.CB_SORT)
        self.getregion=wx.Button(panel,id=wx.ID_ANY,label='Dump Region')
        self.getregion.Disable()
        menubar = wx.MenuBar()
        login=wx.Menu()

        self.statusbar=self.CreateStatusBar(style=0)
        self.statusbar.SetFieldsCount(2)
        self.statusbar.SetStatusWidths([-2, -1])
        self.SetStatusText("Please Log in",0)   
        sizer = wx.FlexGridSizer(1, 3, 5, 5)
        sizer.Add(self.login)
        sizer.Add(self.regionCombo)
        sizer.Add(self.getregion)
        border = wx.BoxSizer()
        border.Add(sizer, 0, wx.ALL, 15)
        panel.SetSizerAndFit(border)
        self.Fit()
        self.Centre()

    def updateStatus(self,data,extra1=0):
        self.SetStatusText(data,extra1)
        
        
    def updateRegions(self,regions):
        self.regionCombo.Clear()
        for item in regions['items']:
            self.regionCombo.Append(item['name'],item)
        
        

class marketModel:
    def __init__(self,settings):
        self.settings=dict()
        self.settings['PORT'] = settings.getint('Config','Port')
        self.settings['CLIENTID'] = settings.get('Config','Clientid')
        self.settings['SECRET'] = settings.get('Config','Secret')
        self.settings['USERAGENT'] = settings.get('Config','UserAgent')
        self.settings['BASEURL'] = settings.get('Config','BaseUrl')
        self.settings['accessToken'] = ''
        self.settings['refreshToken'] =''
        self.settings['endPoints'] = ''
        self.settings['expires']=-1
        
        
    def getRegion(self,event):
        self.SetStatusText("Dump beginning.",0)
        itemCount=len(self.marketItems)
        count=0
        batch=0
        startTime=time.time()
        buyUrls=[]
        sellUrls=[]
        with open('orders.csv', 'wb') as csvfile:
            writer = csv.writer(csvfile,dialect='excel')
            writer.writerow(['Buy','typeid','volume','issued','duration','Volume Entered','Minimum Volume','range','price','locationid','locationname'])
            for item in self.marketItems:
                count+=1
                batch+=1
                wx.Yield()
                buyUrls.append(self.currentRegion['marketBuyOrders']['href']+"?type="+item['href'])
                sellUrls.append(self.currentRegion['marketSellOrders']['href']+"?type="+item['href'])
                if (itemCount==count) or (batch==20):
                    buy=self.getMultipleEndpoint(buyUrls, 'application/vnd.ccp.eve.MarketOrderCollection-v1+json; charset=utf-8')
                    sell=self.getMultipleEndpoint(sellUrls, 'application/vnd.ccp.eve.MarketOrderCollection-v1+json; charset=utf-8')
                    batch=0
                    now=time.time()
                    sofar=now-startTime
                    fraction=float(count)/float(itemCount)
                    total=sofar/fraction
                    remaining=total-sofar
                    self.SetStatusText("Completion: "+locale.format("%d",count,grouping=True)+'/'+locale.format("%d",itemCount,grouping=True),0)
                    self.SetStatusText(locale.format("%d",sofar,grouping=True)+'/'+locale.format("%d",remaining,grouping=True)+'/'+locale.format("%d",total,grouping=True),1)
                    wx.Yield()
                    buyUrls=[]
                    sellUrls=[]
                    for buyitem in buy:
                        writer.writerow([1,buyitem['type']['id'],buyitem['volume'],buyitem['issued'],buyitem['duration'],buyitem['volumeEntered'],buyitem['minVolume'],buyitem['range'],buyitem['price'],buyitem['location']['id'],buyitem['location']['name']])
                    for sellitem in sell:
                        writer.writerow([0,sellitem['type']['id'],sellitem['volume'],sellitem['issued'],sellitem['duration'],sellitem['volumeEntered'],1,sellitem['range'],sellitem['price'],sellitem['location']['id'],sellitem['location']['name']])
        self.SetStatusText("Complete.",0)
        self.SetStatusText("",1)
        pub.sendMessage('completedDump')
        
        
    def getMultipleEndpoint(self,endpoints,accept):
        if self.settings['expires']<time.time():
            self.refreshTokens()
        items=[]
        headers = {'Authorization':'Bearer '+ self.settings['accessToken'],
            'Accept':accept,
            'User-Agent':self.settings['USERAGENT']
            }
        rs = (grequests.get(u,headers=headers) for u in endpoints)
        responses=grequests.map(rs)
        for response in responses:
            add=response.json()
            items.extend(add['items'])
            response.close()
        return items
        
    def doLogin(self,message):
        headers = {'User-Agent':self.settings['USERAGENT']}
        query = {'grant_type':'authorization_code','code':message}
        r = requests.get(self.settings['BASEURL'],headers=headers)
        self.settings['endPoints']=r.json()
        headers = {'Authorization':'Basic '+ base64.b64encode(self.settings['CLIENTID']+':'+self.settings['SECRET']),'User-Agent':self.settings['USERAGENT']}
        r = requests.post(self.settings['endPoints']['authEndpoint']['href'],params=query,headers=headers)
        response = r.json()
        self.settings['accessToken']=response['access_token']
        self.settings['refreshToken']=response['refresh_token']
        self.settings['expires']=time.time()+float(response['expires_in'])-20
        self.loadBaseData()
        
    def refreshTokens(self):
        headers = {'Authorization':'Basic '+ base64.b64encode(self.settings['CLIENTID']+':'+self.settings['SECRET']),'User-Agent':self.settings['USERAGENT']}
        query = {'grant_type':'refresh_token','refresh_token':self.settings['refreshToken']}
        r = requests.post(endPoints['authEndpoint']['href'],params=query,headers=headers)
        response = r.json()
        self.settings['accessToken']=response['access_token']
        self.settings['refreshToken']=response['refresh_token']
        self.settings['expires']=time.time()+float(response['expires_in'])-20

        
    def loadBaseData(self):
        headers = {'Authorization':'Bearer '+ self.settings['accessToken'],'User-Agent':self.settings['USERAGENT']}
        self.SetStatusText("Loading Regions",0)
        r = requests.get(self.settings['endPoints']['regions']['href'],headers=headers)
        self.regions=r.json()
        pub.sendMessage('updateRegions')
        self.SetStatusText("Loading Market Types",0)
        self.marketItems=self.walkMarketTypes('application/vnd.ccp.eve.MarketTypeCollection-v1+json; charset=utf-8');
        self.SetStatusText("Select a region to continue.",0)
              
        
    
    def getEndpoint(self,endpoint,accept,parameters=None):
        if self.settings['expires']<time.time():
            self.refreshTokens()
        headers = {'Authorization':'Bearer '+ self.settings['accessToken'],
            'Accept':accept,
            'User-Agent':self.settings['USERAGENT']
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
        url=self.settings['endPoints']['marketTypes']['href']
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
        
    def SetStatusText(self,data,id):
        pub.sendMessage('updateStatus',data=data,extra1=id)

    




class marketController:
    
    def __init__(self,app,inifile):
        
        self.view = marketView(None, -1, "Market Loader")

        self.view.login.Bind(wx.EVT_BUTTON,self.onLogin)
        self.view.regionCombo.Bind(wx.EVT_COMBOBOX,self.onRegionSelect)
        

        self.view.Show(True)        
        app.SetTopWindow(self.view)
        settings = ConfigParser.ConfigParser()
        settings.read(inifile)
        self.model=marketModel(settings)
        
        self.view.getregion.Bind(wx.EVT_BUTTON,self.model.getRegion)
        
        server = HTTPServer(('', settings.getint('Config','Port')), authHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        pub.subscribe(self.doLoginController,'login')
        pub.subscribe(self.updateStatusController,'updateStatus')
        pub.subscribe(self.updateRegionsController,'updateRegions')
        pub.subscribe(self.completedDump,'completedDump')

    def onLogin(self,event):
        webbrowser.open('https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri=http://localhost:'+`self.model.settings['PORT']`+'/&client_id='+self.model.settings['CLIENTID']+'&scope=publicData&state=')

    def onRegionSelect(self,event):
        selected=self.view.regionCombo.GetClientData(self.view.regionCombo.GetSelection())
        self.model.currentRegion=self.model.getEndpoint(selected['href'], 'application/vnd.ccp.eve.Region-v1+json; charset=utf-8')
        self.view.getregion.Enable()
        self.view.SetStatusText("Ready.",0)
        
    def doLoginController(self,message):
        self.view.login.Disable()
        self.model.doLogin(message)

    def updateStatusController(self,data,extra1=0):
        self.view.updateStatus(data,extra1)
    
    def getRegionController(self,event):
        self.view.getregion.Disable()
        self.view.regionCombo.Disable()
        self.model.getRegion()
    
    def completedDump(self,event):
        self.view.getregion.Enable()
        self.view.regionCombo.Enable()

    def updateRegionsController(self):
        self.view.updateRegions(self.model.regions)

if __name__ == '__main__':
    inifile=os.path.dirname(__file__)+os.sep+"downloader.ini"
    inifile=inifile.strip('\\')
    app = wx.App(False)
    controller = marketController(app,inifile)     # Create an instance of the application class
    app.MainLoop()     # Tell it to start processing events







