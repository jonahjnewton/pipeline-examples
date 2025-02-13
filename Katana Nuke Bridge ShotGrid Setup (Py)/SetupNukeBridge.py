"""
NAME: SetupNukeBridge
ICON: icon.png
SCOPE:
Setup Nuke Bridge from a ShotGrid Nuke project
"""

import os

from katana_pipeline.farm import tractor_job
from katana_pipeline import utils

from turret import resolver

from PyQt5 import (
    QtGui,
    QtWidgets,
)

from Katana import (
    UI4,
    FarmAPI,
    NodegraphAPI,
    CatalogAPI
)

class NukeScriptInfo():
    def __init__(self):
        self.path = ""
        self.task = ""
        self.step = ""
        self.user = ""
        self.area = ""
        self.shot = ""

    def setTaskInfo(self, task):
        self.task = task

        if task == 'lighting':
            self.step = 'light'
        elif task == 'comp':
            self.step = 'comp'
        else:
            raise Exception("Invalid value for task info. Must be 'lighting' or 'comp'.")
    

class ALASetupNukeBridge(QtWidgets.QDialog):
    
    def __init__(self):
        """
        Initializes an instance of the class.
        """
        QtWidgets.QDialog.__init__(self, UI4.App.MainWindow.GetMainWindow())

        self.setWindowTitle('Setup Nuke Bridge')
        self.move(QtGui.QCursor.pos())
        self.setMinimumWidth(400)

        self.root = NodegraphAPI.GetRootNode()
        self.nukeScriptInfo = NukeScriptInfo()

        #Get latest live/preview renders for each pass
        self.currentRenders = self.getLatestPassRenders()

        # Set up dialog layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addStretch()

        if len(self.currentRenders.keys()) == 0:
            errorText = QtWidgets.QLabel("No valid renders in catalog")
            self.layout.addWidget(errorText)
            closeButton = QtWidgets.QPushButton("Close")
            closeButton.clicked.connect(lambda: self.close())
            self.layout.addWidget(closeButton)
            self.setLayout(self.layout)
            return

        #TODO: Check if in ShotGrid context
            
        if self.root.getParameter('sgContext').getChild('firstname') == None or self.root.getParameter('sgContext').getChild('lastname') == None:
            errorText = QtWidgets.QLabel("You are not in a ShotGrid context.")
            self.layout.addWidget(errorText)
            closeButton = QtWidgets.QPushButton("Close")
            closeButton.clicked.connect(lambda: self.close())
            self.layout.addWidget(closeButton)
            self.setLayout(self.layout)
            return
        
        self.currentUserText = "%s.%s" % (self.root.getParameter('sgContext').getChild('firstname').getValue(0),self.root.getParameter('sgContext').getChild('lastname').getValue(0))

        self.shot_selector = QtWidgets.QComboBox()
        self.shot_selector.addItems(self.currentRenders.keys())
        self.shot_selector.activated.connect(self.uiChanged)

        self.area_selector = QtWidgets.QComboBox()
        self.area_selector.addItems(['publish','wips'])
        self.area_selector.activated.connect(self.areaChanged)
        self.currentArea = 'publish'

        self.task_selector = QtWidgets.QComboBox()
        self.task_selector.addItems(['lighting','comp'])
        self.task_selector.activated.connect(self.uiChanged)

        self.user_text = QtWidgets.QLineEdit()
        self.user_text.setText(self.currentUserText)
        self.user_text.textChanged.connect(self.uiChanged)

        self.version_selector = QtWidgets.QComboBox()

        self.options = QtWidgets.QVBoxLayout()
        self.global_options = QtWidgets.QFormLayout()
        self.global_options.addRow('Shot: ', self.shot_selector)
        self.global_options.addRow('Task: ', self.task_selector)
        self.global_options.addRow('Nuke Script Area: ', self.area_selector)

        self.wip_options = QtWidgets.QFormLayout()

        self.options.addLayout(self.global_options)
        self.options.addLayout(self.wip_options)

        self.layout.addLayout(self.options)

        findProjectButton = QtWidgets.QPushButton('Find Nuke Project')
        findProjectButton.clicked.connect(self.findProject)

        # Set up button layout
        findProjectButtonLayout = QtWidgets.QHBoxLayout()
        findProjectButtonLayout.addWidget(findProjectButton)

        statusLayout = QtWidgets.QHBoxLayout()
        self.statusText = QtWidgets.QLabel()
        statusLayout.addWidget(self.statusText)

        self.versionLayout = QtWidgets.QFormLayout()
        
        
        self.beginSetupLayout = QtWidgets.QHBoxLayout()
        self.beginSetupButton = QtWidgets.QPushButton('Begin Setup')
        self.beginSetupButton.clicked.connect(self.beginSetup)

        self.populatePassesLayout = QtWidgets.QHBoxLayout()
        self.populatePassesButton = QtWidgets.QPushButton('Populate Nuke Passes')
        self.populatePassesButton.clicked.connect(self.populatePasses)
        
        self.layout.addLayout(findProjectButtonLayout)
        self.layout.addLayout(self.versionLayout)
        self.layout.addLayout(self.beginSetupLayout)
        self.layout.addLayout(self.populatePassesLayout)

        nukeBridgeParam = self.root.getParameter('catalog').getChild('nuke')
        nukeScriptParam = nukeBridgeParam.getChild('script')

        if nukeScriptParam.getValue(0) != '':
            
            self.populateInfoFromScriptParam(nukeScriptParam)
            self.populatePassesLayout.addWidget(self.populatePassesButton)
            self.shot_selector.setCurrentText(self.nukeScriptInfo.shot)
            self.task_selector.setCurrentText(self.nukeScriptInfo.task)
            self.area_selector.setCurrentText(self.nukeScriptInfo.area)
            
            if self.nukeScriptInfo.user != '':
                self.user_text.setText(self.nukeScriptInfo.user)
            
            self.areaChanged()
        
        self.layout.addLayout(statusLayout)

        self.setLayout(self.layout)
    
    def populateInfoFromScriptParam(self,nukeScriptParam):
        nukeFields = resolver.filepath_to_fields(nukeScriptParam.getValue(0))

        self.nukeScriptInfo.path = nukeScriptParam.getValue(0)
        self.nukeScriptInfo.setTaskInfo(nukeFields['Task'])

        if nukeFields.get('HumanUser.firstname'):
            self.nukeScriptInfo.user = "%s.%s" % (nukeFields['HumanUser.firstname'], nukeFields['HumanUser.lastname'])
        self.nukeScriptInfo.shot = nukeFields['Shot']

        if '/wip/' in nukeScriptParam.getValue(0):
            self.nukeScriptInfo.area = 'wips'
        elif '/jobs/' in nukeScriptParam.getValue(0):
            self.nukeScriptInfo.area = 'publish'


    def findProject(self):
        # Populate Nuke Script info from UI
        self.nukeScriptInfo.shot = self.shot_selector.currentText()

        #Look for Nuke Script in wips or publish
        self.nukeScriptInfo.area = self.area_selector.currentText()

        if self.nukeScriptInfo.area == 'wips':
            self.nukeScriptInfo.user = self.user_text.text()

        

        #Look for Nuke Script for lighting or comp task
        self.nukeScriptInfo.setTaskInfo(self.task_selector.currentText())

        #Get latest ShotGrid Nuke projects for the given shot
        self.valid_projects = self.getLatestNukeBridgeProject(self.nukeScriptInfo)

        self.version_selector.clear()

        if self.valid_projects == None:
            self.statusText.setText('No valid project found')
            self.deleteItemsOfLayout(self.versionLayout)
            self.deleteItemsOfLayout(self.beginSetupLayout)
        else:
            self.statusText.setText('Successfully found valid projects')

            self.version_selector.addItems(self.valid_projects.keys())

            self.versionLayout.addRow('Version: ', self.version_selector)

            # Set up button layout
            self.beginSetupLayout.addWidget(self.beginSetupButton)

    def beginSetup(self):

        self.deleteItemsOfLayout(self.populatePassesLayout)

        nukeBridgeParam = self.root.getParameter('catalog').getChild('nuke')
        nukeScriptParam = nukeBridgeParam.getChild('script')
        
        
        #Load the Nuke project into Nuke Bridge
        nukeScriptParam.setValue(self.valid_projects[self.version_selector.currentText()],0)

        self.statusText.setText('Successfully loaded project\n' + self.valid_projects[self.version_selector.currentText()])

        # Set up button layout
        self.populatePassesLayout.addWidget(self.populatePassesButton)
        
        print("Successfully set up Nuke Bridge")

    def populatePasses(self):
        self.currentRenders = self.getLatestPassRenders()
        nukeBridgeParam = self.root.getParameter('catalog').getChild('nuke')
        inputParamGroup = nukeBridgeParam.getChild('mapping')

        #Route live renders to Nuke inputs
        for inputParam in inputParamGroup.getChildren():
            for passName in self.currentRenders[self.nukeScriptInfo.shot].keys():
                if "_".join(inputParam.getName().split("_")[1:]).startswith(passName):
                    inputParam.setValue(self.currentRenders[self.nukeScriptInfo.shot][passName].getShortDescription(),0)
        
        self.statusText.setText('Successfully populated passes in Nuke Bridge')

    def areaChanged(self):
        if self.area_selector.currentText() != self.currentArea:
            if self.area_selector.currentText() == 'publish':
                # self.options.removeItem(self.wip_options)
                self.currentUserText = self.user_text.text()
                self.deleteItemsOfLayout(self.wip_options)
            else:
                self.wip_options.addRow('User: ', self.user_text)
                
            self.currentArea = self.area_selector.currentText()
            
            self.uiChanged()

    def uiChanged(self):
        self.deleteItemsOfLayout(self.versionLayout)
        self.deleteItemsOfLayout(self.beginSetupLayout)

        self.statusText.setText('')

    def deleteItemsOfLayout(self,layout):
     if layout is not None:
         while layout.count():
             item = layout.takeAt(0)
             widget = item.widget()
             if widget is not None:
                 widget.setParent(None)
             else:
                 self.deleteItemsOfLayout(item.layout())
    def getLatestPassRenders(self):
        # currentRenders : {shot:{pass:catalogItem}}
        currentRenders = {}
        catalogItems = CatalogAPI.GetCatalogItems()

        for item in catalogItems:
            renderNodeName = item.getNodeName()

            if renderNodeName == 'Foundry_NukeBridge_Render':
                continue
            
            renderNode = NodegraphAPI.GetNode(renderNodeName)

            if not renderNode:
                continue

            if renderNode.getType() == 'Render':
                renderNode = tractor_job.get_render_manager_node(renderNodeName)
            
            if renderNode.getType() == 'Group' and renderNode.getParameter('user.macroType') and renderNode.getParameter('user.macroType').getValue(0) == 'alaRenderManager': 
                renderManagerNode = renderNode
            else:
                print("Skipping render " + renderNodeName + ' as no alaRenderManager can be associated to this render.')
                continue
            shot = renderManagerNode.getParameter('user.shot').getValue(0)
            if not shot in currentRenders.keys():
                currentRenders[shot] = {}

            passName = renderManagerNode.getParameter('user.passName').getValue(0)

            if not passName in currentRenders[shot].keys():
                currentRenders[shot][passName] = item
        
        return currentRenders

    def getLatestNukeBridgeProject(self,nukeScriptInfo):
        tk = utils.get_tk()
        shotgun = tk.shotgun

        projects = []
        if nukeScriptInfo.area == 'wips':
            nukeWipTemplate = 'nuke_wip_shot_build_path'
            nukeFields = resolver.filepath_to_fields(FarmAPI.GetKatanaFileName())
            nukeFields['Shot'] = nukeScriptInfo.shot
            nukeFields['Task'] = nukeScriptInfo.task
            nukeFields['Step'] = nukeScriptInfo.step
            nukeFields['HumanUser.firstname'] = nukeScriptInfo.user.split(".")[0]
            nukeFields['HumanUser.lastname'] = nukeScriptInfo.user.split(".")[1]
            del nukeFields['version']
            
            projects_paths = sorted(tk.paths_from_template(tk.templates[nukeWipTemplate],nukeFields))

            projects = []
            for p in projects_paths:
                version = p.split(".")[-2]
                projects += [(version,p)]

        elif nukeScriptInfo.area == 'publish':

            publishes = shotgun.find("PublishedFile", [['entity.Shot.code', "is", nukeScriptInfo.shot], ['name', 'contains', '_' + nukeScriptInfo.task], ['published_file_type.PublishedFileType.code', "is", 'Nuke Script'], ['project.Project.tank_name','is',os.getenv('SHOTGUN_PROJECT')]], fields = ["id", "version_number", "path"], order = [{'field_name':'version_number', 'direction':'asc'}])
            projects = [('v' + str(x['version_number']).zfill(3), x['path']['local_path']) for x in publishes]

        #Check latest SG publish that has KatanaReader nodes
        #projects = {}
        valid_projects = {}
        for projinfo in reversed(projects):
            with open(projinfo[1], 'r') as f:
                r = f.read()
                if 'KatanaReader' in r and 'KatanaWriter' in r:
                    valid_projects[projinfo[0]] = projinfo[1]
        
        if len(valid_projects.keys()) == 0:
            print("No projects found with KatanaReaders and KatanaWriter nodes")
            return None
        
        return valid_projects

alaSetupNukeBridge = ALASetupNukeBridge()
alaSetupNukeBridge.show()