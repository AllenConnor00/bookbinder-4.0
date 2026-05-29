#!/usr/bin/env jython
##		TO DO
##	unittextchange function
##	bug in setting booksizes ?? odd output not consistent
##	check output book smaller than pagesize ??
##	clean up PDFfilter, java-ise it
##	
##	


from javax.swing.event import DocumentListener
from javax.swing import *
from java.awt import *
from java.awt.event import *
from java.io import File, RandomAccessFile
from java.lang import Object

from java.nio import ByteBuffer
from java.nio.channels import FileChannel

from java.net import URL

import os,string,re,sys
import book

class combolistener(ActionListener):
	
	def __init__(self,parent):
	
		self.parent=parent
	
	def actionPerformed(self,event):

		source=event.getSource()

		targetsize=self.parent.targetsize.getSelection()
		target=targetsize.getActionCommand()

		if target=='Full paper size':
			
			initsizes=self.parent.papersizes[source.getSelectedItem()]

			self.parent.customx=initsizes[0]
			self.parent.customy=initsizes[1]*0.5



class inputListener(DocumentListener):
	
	def __init__(self,parent,function):
	
		#self.parent=parent
		self.function=function
	
	def insertUpdate(self,event):

		#source=event.getDocument()
		self.function(event)

	def removeUpdate(self,event):

		#source=event.getDocument()
		self.function(event)
		

class PDFfilter(filechooser.FileFilter):
	
	def __init__(self):

		filechooser.FileFilter.__init__(self)

		self.extensionlist=[]
	
	def addextension(self,extension):

		self.extensionlist.append(extension)
	
	def accept(self,file):

		if file.isDirectory():

			return 1

		filepath=str(file)

		filepath=os.path.split(filepath)

		filename=filepath[1]

		candidate=filename.split('.')

		if len(candidate)==1:

			#	probably a directory, ok it

			return 0

		elif len(candidate)>1:

			#	probably a file and extension

			extension=candidate[-1].lower()

			if  extension in self.extensionlist:

				return 1

			else:

				return 0
	def getDescription(self):
		
		#	only for this implementation...
		
		return "PDF File (*.pdf)"


class bookbind(JFrame):
	
	def __init__(self):

		JFrame.__init__(self,"Bookbinder 3.0")

		##      standard iso A series sheetsizes, plus some peculiar american ones
		self.papersizes={       'LETTER':[612,792],'NOTE':[540,720],'LEGAL':[612,1008],'TABLOID':[792,1224],'EXECUTIVE':[522,756],'POSTCARD':[283,416],
					'A0':[2384,3370],'A1':[1684,2384],'A3':[842,1191],'A4':[595,842],'A5':[420,595],'A6':[297,420],
					'A7':[210,297],'A8':[148,210],'A9':[105,148],'B0':[2834,4008],'B1':[2004,2834],'B2':[1417,2004],
					'B3':[1000,1417],'B4':[708,1000],'B6':[354,498],'B7':[249,354],'B8':[175,249],'B9':[124,175],
					'B10':[87,124],'ARCH_E':[2592,3456],'ARCH_C':[1296,1728],'ARCH_B':[864,1296],'ARCH_A':[648,864],
					'FLSA':[612,936],'FLSE':[648,936],'HALFLETTER':[396,612],'_11X17':[792,1224],'ID_1':[242.65,153],
					'ID_2':[297,210],'ID_3':[354,249],'LEDGER':[1224,792],'CROWN_QUARTO':[535,697],'LARGE_CROWN_QUARTO':[569,731],
					'DEMY_QUARTO':[620,782],'ROYAL_QUARTO':[671,884],'CROWN_OCTAVO':[348,527],'LARGE_CROWN_OCTAVO':[365,561],
					'DEMY_OCTAVO':[391,612],'ROYAL_OCTAVO':[442,663],'SMALL_PAPERBACK':[314,504],
					'PENGUIN_SMALL_PAPERBACK':[314,513],'PENGUIN_LARGE_PAPERBACK':[365,561]}

		self.filepath=None
		self.units='Points'
		self.duplex=0
		self.ratio=0
		self.spine=0
		self.customx=0
		self.customy=0
		self.encrypt=None
		self.customsiglist=[]

		self.sigregex=re.compile(r'\b[0-9]+\b')
		self.clist=combolistener(self)

		self.pnames=[]

		for key in self.papersizes:

			self.pnames.append(key)

		self.pnames.sort()

		# window decorations
		self.setDefaultLookAndFeelDecorated(1)
		self.setIconImage(Toolkit.getDefaultToolkit().getImage("icon.png"))
		#Create and set up the window.
		self.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE)

		##	get the screen size and set preferred size accordingly
		screensize=Toolkit.getDefaultToolkit().getScreenSize()

		urpanel=JPanel(BorderLayout())
		urpanel.setBorder(BorderFactory.createEmptyBorder(0,5,5,5))

		titlefont=Font("Dialog",Font.BOLD,16)
		self.bkgrdcolour=self.getBackground()

		panelcolour=Color(218,218,218)

#########################################################################################

		##	Input PDF
		input=JPanel()

		inputpanel=JPanel()
		inputpanel.setLayout(BoxLayout(inputpanel, BoxLayout.PAGE_AXIS))
		inputpanel.setPreferredSize(Dimension(230,100))
		inputpanel.setBorder(BorderFactory.createTitledBorder('Input PDF Info'))
		inputpanel.setBackground(panelcolour)
		inputpanel.border.setTitleFont(titlefont)
		inputpanel.border.setTitlePosition(1)
		inputpanel.border.setTitleJustification(2)
		
		

		self.nofiletext='No file selected'
		self.picked=JLabel(self.nofiletext,0)
		self.picked.setHorizontalAlignment(0)

		self.psizetext='Page Size : '
		self.psize=JLabel(self.psizetext)

		self.npagestext='No of Pages : '
		self.npages=JLabel(self.npagestext)
		
		self.proportiontext='Page ratio : '
		self.proportion=JLabel(self.proportiontext)

		#inputpanel.add(open)

		inputpanel.add(self.picked)
		inputpanel.add(self.psize)
		inputpanel.add(self.npages)
		inputpanel.add(self.proportion)

		input.add(inputpanel)
		
###########################################################

		uni=JPanel()

		unipanel=JPanel()
		unipanel.setLayout(BoxLayout(unipanel, BoxLayout.PAGE_AXIS))
		unipanel.setPreferredSize(Dimension(230,120))
		unipanel.setBorder(BorderFactory.createTitledBorder('Units'))
		unipanel.setBackground(panelcolour)
		unipanel.border.setTitleFont(titlefont)
		unipanel.border.setTitlePosition(1)
		unipanel.border.setTitleJustification(2)
		
		#self.unittext='Set units'
		#self.unitlabel=JLabel(self.unittext)
		self.unitbuttons = ButtonGroup()
		ubuttonpanel=JPanel(GridLayout(0,1))
		ubuttonpanel.setBackground(panelcolour)

		radioButton1=JRadioButton("Inches", 	actionPerformed=self.unitchange)
		radioButton1.setActionCommand('inches')
		radioButton1.setToolTipText('imperial units')
		radioButton1.setBackground(panelcolour)
		self.unitbuttons.add(radioButton1)
		ubuttonpanel.add(radioButton1)
		
		radioButton2=JRadioButton("Millimetres", 	actionPerformed=self.unitchange)
		radioButton2.setActionCommand('millimetres')
		radioButton2.setToolTipText('metric units')
		radioButton2.setBackground(panelcolour)
		self.unitbuttons.add(radioButton2)
		ubuttonpanel.add(radioButton2)
		
		radioButton3=JRadioButton('Points', 		actionPerformed=self.unitchange)
		radioButton3.setActionCommand('points')
		radioButton3.setToolTipText('publishing units')
		radioButton3.setBackground(panelcolour)
		self.unitbuttons.add(radioButton3)
		ubuttonpanel.add(radioButton3)
		
		##	millimetres as default
		radioButton3.setSelected(1)		

		
		#unipanel.add(self.unitlabel)
		unipanel.add(ubuttonpanel)
		uni.add(unipanel)
		########################################################

		##	Printer
		printing=JPanel()

		printerpanel=JPanel()
		printerpanel.setLayout(BoxLayout(printerpanel, BoxLayout.PAGE_AXIS))
		printerpanel.setPreferredSize(Dimension(240,160))
		printerpanel.setBorder(BorderFactory.createTitledBorder('Printer'))
		printerpanel.setBackground(panelcolour)
		printerpanel.border.setTitleFont(titlefont)
		printerpanel.border.setTitlePosition(1)
		printerpanel.border.setTitleJustification(2)

		paperlabel = JLabel('Paper size')

		paperlabel.setAlignmentX(Component.CENTER_ALIGNMENT)

		self.papersize=JComboBox(self.pnames)

		self.papersize.setSelectedIndex(3)
		
		#self.papsize=JLabel()
		#self.papsize.setAlignmentX(SwingConstants.LEFT)

		#self.paperx,self.papery=self.papersizes[self.papersize.getSelectedItem()]
		#print self.paperx,self.papery
		#self.papsize.setText('<html>width:'+str(int(self.paperx))+' <br>height:'+str(int(self.papery))+'</html>')
		##	split into width and height 


		printerlabel=JLabel('Printer type')
		printerlabel.setAlignmentX(Component.CENTER_ALIGNMENT)

		printer=['Single sided','Duplex']
		
		self.printertype=JComboBox(printer)
		self.printertype.setToolTipText('Set to Duplex if you have duplex printer')
		self.printertype.setSelectedIndex(0)

		rotatepanel=JPanel()
		rotatepanel.setBackground(panelcolour)
		rotatelabel=JLabel('Alternate Page Rotation')
		rotatelabel.setAlignmentX(Component.CENTER_ALIGNMENT)
		self.printerrotate=JCheckBox('',True)
		
		rotatelabel.setToolTipText('If checked, the back sides of the sheets will be rotated 180 degrees when printed')

		rotatepanel.add(rotatelabel)
		rotatepanel.add(self.printerrotate)

		printerpanel.add(paperlabel)
		printerpanel.add(self.papersize)
		#printerpanel.add(self.papsize)
		printerpanel.add(printerlabel)
		printerpanel.add(self.printertype)
		printerpanel.add(rotatepanel)
		rotatepanel.add(self.printerrotate)

		printing.add(printerpanel)

		################################################
		##	Generate - GO button
		action=JPanel()

		actionpanel=JPanel()
		actionpanel.setPreferredSize(Dimension(230,50))
		actionpanel.setBorder(BorderFactory.createTitledBorder(''))
		actionpanel.border.setTitleFont(titlefont)
		actionpanel.border.setTitlePosition(1)
		actionpanel.border.setTitleJustification(2)

		convertbutton=JButton('Generate Document',actionPerformed=self.generate)

		actionpanel.add(convertbutton)

		action.add(actionpanel)

################################################################################################

		##	Output  book size
		output=JPanel()

		outputpanel=JPanel()
		outputpanel.setLayout(BoxLayout(outputpanel, BoxLayout.PAGE_AXIS))
		outputpanel.setPreferredSize(Dimension(230,250))
		outputpanel.setBorder(BorderFactory.createTitledBorder('Book Size'))
		outputpanel.setBackground(panelcolour)
		outputpanel.border.setTitleFont(titlefont)
		outputpanel.border.setTitlePosition(1)
		outputpanel.border.setTitleJustification(2)

		#targetlabel = JLabel('Book size')
		#targetlabel.setAlignmentX(Component.CENTER_ALIGNMENT)

		target=['120mmx180mm','150mmx205mm','Full paper size','Custom']
		self.customx=None
		self.customy=None

		###############################
		self.targetsize = ButtonGroup()
		buttonpanel=JPanel(GridLayout(0,1))
		buttonpanel.setBackground(panelcolour)

		radioButton1=JRadioButton("Standard paperback", 	actionPerformed=self.targetchange)
		radioButton1.setActionCommand('120mmx180mm')
		radioButton1.setToolTipText('about 120mmx180mm')
		radioButton1.setBackground(panelcolour)
		self.targetsize.add(radioButton1)
		buttonpanel.add(radioButton1)
		
		radioButton2=JRadioButton("Large format paperback", 	actionPerformed=self.targetchange)
		radioButton2.setActionCommand('150mmx205mm')
		radioButton2.setToolTipText('about 150mmx205mm')
		radioButton2.setBackground(panelcolour)
		self.targetsize.add(radioButton2)
		buttonpanel.add(radioButton2)
		
		radioButton3=JRadioButton('Full paper size', 		actionPerformed=self.targetchange)
		radioButton3.setActionCommand('Full paper size')
		radioButton3.setToolTipText('Will fit 2 pages onto paper size specified for the printer')
		radioButton3.setBackground(panelcolour)
		self.targetsize.add(radioButton3)
		buttonpanel.add(radioButton3)
		
		radioButton4=JRadioButton('Custom', 			actionPerformed=self.targetchange)
		radioButton4.setActionCommand('Custom')
		radioButton4.setToolTipText('Set your own size in the boxes below')
		radioButton4.setBackground(panelcolour)
		self.targetsize.add(radioButton4)
		buttonpanel.add(radioButton4)

		##	set 'full paper size' as default
		radioButton3.setSelected(1)


		#################################
		self.customxtext=JTextField(4)#,actionPerformed=self.setcustomsize)	##	input boxes here
		self.customytext=JTextField(4)#,actionPerformed=self.setcustomsize)
		
		self.customxtext.setEnabled(0)
		self.customytext.setEnabled(0)

		self.customxtext.setBackground(self.bkgrdcolour)
		self.customytext.setBackground(self.bkgrdcolour)
		
		readx=inputListener(self,self.setcustomx)
		docx=self.customxtext.getDocument()
		docx.addDocumentListener(readx)

		ready=inputListener(self,self.setcustomy)
		docy=self.customytext.getDocument()
		docy.addDocumentListener(ready)


		initsizes=self.papersizes[self.papersize.getSelectedItem()]

		self.customx=initsizes[0]
		self.customy=initsizes[1]

		##	add automatic update from papersize combobox, when 'full paper size'
		self.papersize.addActionListener(self.clist)

		wpan=JPanel()
		wpan.setBackground(panelcolour)
		wpan.add(JLabel('Width'))
		wpan.add(self.customxtext)

		hpan=JPanel()
		hpan.setBackground(panelcolour)
		hpan.add(JLabel('Height'))
		hpan.add(self.customytext)

		cust=JPanel()
		cust.setBackground(panelcolour)
		cust.setPreferredSize(Dimension(230,30))
		#cust.setLayout(BoxLayout(cust, BoxLayout.PAGE_AXIS))
		cust.add(wpan)
		cust.add(hpan)

		###########################################

		offsetpanel=JPanel()
		offsetpanel.setBackground(panelcolour)

		offlabel=JLabel(('Centreline offset'))
		offset=JTextField(4,actionPerformed=self.setoffset)
		
		offsetpanel.add(offlabel)
		offsetpanel.add(offset)

		ratiolabel=JLabel('Page scaling')
		ratiolabel.setAlignmentX(Component.CENTER_ALIGNMENT)

		ratio=['Stretch to fit','Keep proportion']
		self.ratio=JComboBox(ratio)
		self.ratio.setSelectedIndex(1)

		#outputpanel.add(targetlabel)
		outputpanel.add(buttonpanel)
		outputpanel.add(cust)
		#outputpanel.add(offsetpanel)
		outputpanel.add(ratiolabel)
		outputpanel.add(self.ratio)

		output.add(outputpanel)

#################################################################################################

		##	signature format of book
		form=JPanel()

		formpanel=JPanel()
		formpanel.setLayout(BoxLayout(formpanel, BoxLayout.PAGE_AXIS))
		formpanel.setPreferredSize(Dimension(230,200))
		formpanel.setBorder(BorderFactory.createTitledBorder('Signature Format'))
		formpanel.setBackground(panelcolour)
		formpanel.border.setTitleFont(titlefont)
		formpanel.border.setTitlePosition(1)
		formpanel.border.setTitleJustification(2)

		self.targetformat=ButtonGroup()
		buttonpanel=JPanel(GridLayout(0,1))
		buttonpanel.setBackground(panelcolour)

		radioButton1=JRadioButton("Booklet", 		actionPerformed=self.formatchange)
		radioButton1.setActionCommand('booklet')
		radioButton1.setToolTipText('single signature')
		radioButton1.setBackground(panelcolour)
		self.targetformat.add(radioButton1)
		buttonpanel.add(radioButton1)
		
		radioButton2=JRadioButton("Perfect Bound", 	actionPerformed=self.formatchange)
		radioButton2.setActionCommand('perfect bound')
		radioButton2.setToolTipText('4 consecutive pages on one sheet')
		radioButton2.setBackground(panelcolour)
		self.targetformat.add(radioButton2)
		buttonpanel.add(radioButton2)
		
		radioButton3=JRadioButton('Standard Signatures', actionPerformed=self.formatchange)
		radioButton3.setActionCommand('standard sig')
		radioButton3.setToolTipText('Set by bookbinder')
		radioButton3.setBackground(panelcolour)
		self.targetformat.add(radioButton3)
		buttonpanel.add(radioButton3)
		
		radioButton4=JRadioButton('Custom Signatures', 	actionPerformed=self.formatchange)
		radioButton4.setActionCommand('custom sig')
		radioButton4.setToolTipText('Set your own sizes in the box below')
		radioButton4.setBackground(panelcolour)
		self.targetformat.add(radioButton4)
		buttonpanel.add(radioButton4)

		##	set 'standard signatures' as default
		radioButton3.setSelected(2)

		self.customsignature=JTextField(18)#,actionPerformed=self.sigcalc)
		
		self.customsignature.setEnabled(0)
		self.customsignature.setBackground(self.bkgrdcolour)

		#doclist=sigcalcListener(self)
		doclist=inputListener(self,self.sigcalc)
		doc=self.customsignature.getDocument()
		doc.addDocumentListener(doclist)

		siglab=JPanel()
		siglab.setBackground(panelcolour)
		siglab.setPreferredSize(Dimension(230,30))

		siglab.add(self.customsignature)

		#formpanel.add(formatlabel)
		formpanel.add(buttonpanel)
		formpanel.add(siglab)
		
		form.add(formpanel)

		################################################

		flyleaf=JPanel()

		flyleafpanel=JPanel()

		flyleafpanel.setLayout(BoxLayout(flyleafpanel, BoxLayout.PAGE_AXIS))
		flyleafpanel.setPreferredSize(Dimension(230,60))
		flyleafpanel.setBorder(BorderFactory.createTitledBorder('Flyleaf'))
		flyleafpanel.setBackground(panelcolour)
		flyleafpanel.border.setTitleFont(titlefont)
		flyleafpanel.border.setTitlePosition(1)
		flyleafpanel.border.setTitleJustification(2)

		panel=JPanel()
		panel.setBackground(panelcolour)
		flylabel=JLabel('Add Flyleaf')
		flylabel.setToolTipText('Adds blank pages at start and end of book')
		self.fly=JCheckBox('')
		self.fly.actionPerformed=self.setflyleaf
		panel.add(flylabel)
		panel.add(self.fly)
	
		flyleafpanel.add(panel)
		flyleaf.add(flyleafpanel)

		################################################
		##	Signature info
		siginfo=JPanel()

		siginfopanel=JPanel()
		siginfopanel.setLayout(BoxLayout(siginfopanel, BoxLayout.PAGE_AXIS))
		siginfopanel.setPreferredSize(Dimension(230,120))
		siginfopanel.setBorder(BorderFactory.createTitledBorder('Signature Info'))
		siginfopanel.setBackground(panelcolour)
		siginfopanel.border.setTitleFont(titlefont)
		siginfopanel.border.setTitlePosition(1)
		siginfopanel.border.setTitleJustification(2)

		#self.blankstext='Total Blank Pages : '
		#self.blanks=JLabel(self.blankstext)

		self.pagelengthtext='Total Pages : '
		self.pagelength=JLabel(self.pagelengthtext)
		
		self.sheetstext='Total Sheets : '
		self.sheets=JLabel(self.sheetstext)

		self.signumtext='No of Signatures : '
		self.signum=JLabel(self.signumtext)

		self.sigsizetext='Signature Sizes : '
		self.sigsize=JLabel(self.sigsizetext)

		#siginfopanel.add(self.blanks)
		siginfopanel.add(self.pagelength)
		siginfopanel.add(self.sheets)
		siginfopanel.add(self.signum)
		#siginfopanel.add(self.sigsize)

		siginfo.add(siginfopanel)

####################################################################################################

		##	file menu
		menubar=JMenuBar()

		file=JMenu('File')

		fileopen=JMenuItem('Open input PDF')
		fileopen.actionPerformed=self.filechoose

		fileclose=JMenuItem('Close input PDF')
		fileclose.actionPerformed=self.fileclose

		programexit=JMenuItem('Exit')
		programexit.actionPerformed=self.kill

		file.add(fileopen)
		file.add(fileclose)
		file.add(JSeparator())
		file.add(programexit)

		menubar.add(file)

####################################################################################################

		##	Basepanels
		
		##	
		basepanel=JPanel()
		basepanel.setLayout(BoxLayout(basepanel, BoxLayout.PAGE_AXIS))

		basepanel2=JPanel()
		basepanel2.setLayout(BoxLayout(basepanel2, BoxLayout.PAGE_AXIS))

		basepanel3=JPanel()
		basepanel3.setLayout(BoxLayout(basepanel3, BoxLayout.PAGE_AXIS))

		basepanel.add(input)
		basepanel.add(uni)
		basepanel.add(printing)

		basepanel2.add(output)
		basepanel3.add(form)
		
		basepanel2.add(flyleaf)
		basepanel3.add(siginfo)
		basepanel3.add(action)

		urpanel.add(menubar,BorderLayout.NORTH)
		urpanel.add(basepanel,BorderLayout.WEST)
		urpanel.add(basepanel2,BorderLayout.CENTER)
		urpanel.add(basepanel3,BorderLayout.EAST)

		self.setContentPane(urpanel)

		#Display the window.
		self.pack()
		self.setVisible(1)

######################################################################################


	def filechoose(self,event):

		source=event.getSource()
		
		id=source.getText()

		filter=PDFfilter()
		filter.addextension('pdf')

		chooser=JFileChooser()
		chooser.setFileFilter(filter)

		defaultPath = chooser.getCurrentDirectory()
		option = chooser.showOpenDialog(self)

		if option==0:

			filepath=chooser.getSelectedFile().getPath()			
			filename=chooser.getSelectedFile().getName()

			if id=='Open input PDF':
				
				self.filepath=filepath
				self.filename=filename
				self.loadfile()


	def loadfile(self):
		##	add check if file open, then close it
		self.bookobject=book.book()

		success=self.bookobject.openpdf(self.filepath)

		if success==None:	##	no problems

			#if self.bookobject.filelist:

			#	self.out.removeAll()
			#	self.out.add(self.outlist)

			self.picked.setText(self.filename)

			pagesize=self.bookobject.currentdoc.getBoxSize(1,'crop')
			
			if pagesize:
				print "crop pagesize",pagesize
				print "media pagesize",self.bookobject.currentdoc.getBoxSize(1,'media')
			
			if not pagesize:
				pagesize=self.bookobject.currentdoc.getBoxSize(1,'media')

			pagex,pagey=self.bookobject.getpagesize(str(pagesize))
			
			x=self.points2units(pagex)
			y=self.points2units(pagey)
			ratio=x/y
			ratstring=str(ratio)

			self.psize.setText(self.psizetext+str(int(self.points2units(x)))+' x '+str(int(self.points2units(y))))
			self.npages.setText(self.npagestext+str(self.bookobject.currentdoc.getNumberOfPages()))
			self.proportion.setText(self.proportiontext+ratstring[:4])#"%f" % ratio)#str(ratio))#

			self.setparameters(None)
			self.xpoints=x
			self.ypoints=y
			#print type(x) #it's a float

			self.repaint()

		else:	##	we have an error

			errorid=self.errorstring(success)
			print 'errorid',success
			print 'errorid',errorid

			if errorid=='Bad user Password':

				self.dialogbox=JDialog(self,' Password required',0)
				self.dia.setSize(200,100)
				x=self.getWidth()
				y=self.getHeight()

				xoff=(x/2)-100
				yoff=(y/2)-50
				self.dia.setLocation(xoff,yoff)

				label=JLabel('Enter User Password',0)
				self.passfield=JPasswordField(30,actionPerformed=self.passinput)

				panel=JPanel(GridLayout(0,1))
				panel.setBorder(BorderFactory.createEmptyBorder(5,5,5,5))
				panel.add(label)
				panel.add(self.passfield)
				self.dia.setContentPane(panel)

				self.dia.setVisible(1)

			elif errorid=='PDF header signature not found.':

				self.infodialog('Error loading PDF',"This file isn't a valid PDF")

			else:

				self.infodialog('Error loading PDF',"Undefined error ??"+errorid)


	def fileclose(self,event):

		source=event.getSource()

		id=source.getText()

		if id=='Close input PDF':

			self.bookobject.closepdf()
			self.encrypt=None
			self.password=None
			self.picked.setText(self.nofiletext)
			
			print "PDF closed"
			self.psize.setText(self.psizetext)
			self.npages.setText(self.npagestext)
			self.proportion.setText(self.proportiontext)
			self.pagelength.setText(self.pagelengthtext)
			self.sheets.setText(self.sheetstext)
			self.signum.setText(self.signumtext)
			self.sigsize.setText(self.sigsizetext)


		self.repaint()

	def infodialog(self,title,message):

		self.errordia=JDialog(self,title,0)
		self.errordia.setSize(300,100)

		x=self.getWidth()
		y=self.getHeight()

		xoff=(x/2)-100
		yoff=(y/2)-50
		self.errordia.setLocation(xoff,yoff)

		label=JLabel(message,0)

		panel=JPanel(GridLayout(0,1))
		panel.setOpaque(1)
		panel.setBorder(BorderFactory.createEmptyBorder(5,5,5,5))
		panel.add(label)

		self.errordia.setContentPane(panel)
		self.errordia.setVisible(1)
	
	def errorstring(self,estring):

		strlist=estring.split(':')
		message=(string.strip(strlist[1]))
		print len(message)

		return str(message)

	##	change to units2points and point2units, add unit setting method and variable
	def units2points(self,size):

		#       millimetres to points = 2.83464567
		#       points to millimetres = 0.352777778
		
		if self.units=='Inches':
			
			return size*72
			
		elif self.units=='Millimetres':
			
			return size*2.83464567
		else:
			return size

	def points2units(self,size):

		#       millimetres to points = 2.83464567
		#       points to millimetres = 0.352777778
		if self.units=='Inches':
			
			return size*0.013888889
			
		elif self.units=='Millimetres':
			
			return size*0.352777778
		else:
			return size


	def unitchange(self,event):

		id=event.getSource().getText()
		print 'units',id
		
		if id=="Inches":
			self.units='Inches'

		elif id=="Millimetres":
			self.units='Millimetres'
			
		elif id=="Points":
			self.units='Points'
			
		else:
			print "Wrong input for changing Units"
			
		self.unittextchange()

	def unittextchange(self):
		
		print "unittextchange"
		
		self.psize.setText(self.psizetext+str(int(self.points2units(self.xpoints)))+' x '+str(int(self.points2units(self.ypoints))))
		self.repaint()	
	#pass
		#	check file loaded, change page size,custom booksize,
		#	do papersize size readout and change that too

	def targetchange(self,event):

		id=event.getSource().getText()
		print 'booksize',id

		if id=="Standard paperback":

			self.customx=314
			self.customy=504

			self.customxtext.setEnabled(0)
			self.customytext.setEnabled(0)

			self.customxtext.setBackground(self.bkgrdcolour)
			self.customytext.setBackground(self.bkgrdcolour)

			text=self.customxtext.getText()
			text2=self.customytext.getText()

			if text!=None or text2!=None:
				self.customxtext.setText('')
				self.customytext.setText('')

		elif id=="Large format paperback":

			self.customx=365
			self.customy=561

			self.customxtext.setEnabled(0)
			self.customytext.setEnabled(0)

			self.customxtext.setBackground(self.bkgrdcolour)
			self.customytext.setBackground(self.bkgrdcolour)

			text=self.customxtext.getText()
			text2=self.customytext.getText()

			if text!=None or text2!=None:
				self.customxtext.setText('')
				self.customytext.setText('')

		elif id=='Full paper size':

			initsizes=self.papersizes[self.papersize.getSelectedItem()]

			self.customy=initsizes[0]
			self.customx=initsizes[1]*0.5

			self.customxtext.setEnabled(0)
			self.customytext.setEnabled(0)

			self.customxtext.setBackground(self.bkgrdcolour)
			self.customytext.setBackground(self.bkgrdcolour)

			text=self.customxtext.getText()
			text2=self.customytext.getText()

			if text!=None or text2!=None:
				self.customxtext.setText('')
				self.customytext.setText('')

		elif id=='Custom':

			self.customxtext.setEnabled(1)
			self.customytext.setEnabled(1)

			self.customxtext.requestFocus()

		print self.customx,self.customy

	def formatchange(self,event):

		id=event.getSource().getText()

		if id=="Booklet":

			self.customsignature.setEnabled(0)
			self.customsignature.setBackground(self.bkgrdcolour)

			text=self.customsignature.getText()

			if text!=None:
				self.customsignature.setText('')
				
			self.setparameters(None)

		elif id=="Perfect Bound":

			self.customsignature.setEnabled(0)
			self.customsignature.setBackground(self.bkgrdcolour)

			text=self.customsignature.getText()
			if text!=None:
				self.customsignature.setText('')

			self.setparameters(None)

		elif id=="Standard Signatures":

			self.customsignature.setEnabled(0)
			self.customsignature.setBackground(self.bkgrdcolour)

			text=self.customsignature.getText()

			if text!=None:
				self.customsignature.setText('')

			self.setparameters(None)

		elif id=="Custom Signatures":

			self.customsignature.setBackground(Color(1.0,1.0,1.0))
			self.customsignature.setEnabled(1)
			self.customsignature.requestFocus()

	def setoffset(self,event):

		self.spine=float(event.getSource().getText())

	def setcustomx(self,event):

		source = event.getDocument()
		length = source.getLength()
		string=source.getText(0, length)
		x=int(string)
		self.customx=self.units2points(x)

	def setcustomy(self,event):

		source = event.getDocument()
		length = source.getLength()
		string=source.getText(0, length)
		y=int(string)
		self.customy=self.units2points(y)

	def setflyleaf(self,event):

		self.setparameters(None)

	def sigcalc(self,event):

		source = event.getDocument()
		length = source.getLength()
		string=source.getText(0, length)

		numbers=self.sigregex.findall(string)

		self.customsiglist=[]
		total=0
		count=0
		sizelist=[]

		for num in numbers:

			count+=1
			total+=(int(num)*4)
			self.customsiglist.append(int(num))
			sizelist.append(int(num)*4)

		self.pagelength.setText(self.pagelengthtext+str(total))
		self.sheets.setText(self.sheetstext+str(total/4))
		self.signum.setText(self.signumtext+str(count))
		self.sigsize.setText(self.sigsizetext+str(sizelist))

	def passinput(self,event):

		passw=self.passfield.getPassword()
		password=''

		for i in range(len(passw)):

			password=password+passw[i]

		self.bookobject.setpassword(password)
		self.encrypt=1
		self.password=password
		self.dia.dispose()
		self.loadfile()

	def setparameters(self,event):

		if not self.filepath:

			print 'No File Loaded'
			self.infodialog('Error processing PDF',"Please open a PDF file first")

		##	printer papersize
		papertype=self.papersize.getSelectedItem()
		self.bookobject.setpapersize(papertype)

		##	booksize
		targetsize=self.targetsize.getSelection()
		target=targetsize.getActionCommand()

		self.bookobject.setbooksize(target,self.customx,self.customy)
		print "target size",target,self.customx,self.customy

		##	signature format
		format=self.targetformat.getSelection()
		ftext=format.getActionCommand()
		self.bookobject.setformat(ftext)

		if ftext=="custom sig":
			self.bookobject.setsigconfig(self.customsiglist)

		##	printer type
		printer=self.printertype.getSelectedItem()

		if printer=='Duplex':

			self.bookobject.setduplex(1)

		else:

			self.bookobject.setduplex(0)

		##	page rotation
		self.bookobject.setduplexrotate(self.printerrotate.isSelected())

		##	page proportion ratio
		ratio=self.ratio.getSelectedItem()
		
		if ratio=='Keep proportion':

			self.bookobject.setlockratio(1)
		else:
			self.bookobject.setlockratio(0)

		##	spine offset
		#self.bookobject.setspineoffset(self.spine)

		##	flyleaf
		self.bookobject.setflyleaf(self.fly.isSelected())

		##	sig info creation
		self.bookobject.createpagelist()
		self.bookobject.createpages()

		self.pagelength.setText(self.pagelengthtext+str(len(self.bookobject.orderedpages)))
		self.sheets.setText(self.sheetstext+str(len(self.bookobject.orderedpages)/4))
		self.signum.setText(self.signumtext+str(len(self.bookobject.book.sigconfig)))

	def generate(self,event):

		if self.filepath==None:

			pass

		else:

			self.setparameters(1)
			self.infodialog('Processing PDF',"Generating new PDF")
			self.repaint()
			self.bookobject.createoutputfiles()
			self.errordia.dispose()

	def kill(self,event):

		sys.exit()

if __name__=='__main__':

	bookbind().show()