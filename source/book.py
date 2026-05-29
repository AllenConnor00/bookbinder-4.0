#!/usr/bin/env jython
##           Priority bug-
##  
##	Crop scaling in calculateposition() definitely off. Investigate.
##


import os,string,re,sys

from javax.swing import *

from com.lowagie.text import Document
from com.lowagie.text import Rectangle
from com.lowagie.text.pdf import PdfWriter
from com.lowagie.text.pdf import PdfReader
from com.lowagie.text.pdf import PdfName
from com.lowagie.text import Chunk

class book:

	'''     A class to convert a PDF document into signatures for traditional bookbinding.'''

	def __init__(self):

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

		##      2 standard paperback sizes and full paper size
		self.targetbooksize={   '120mmx180mm':[314.5,502.0],
					'150mmx205mm':[368.5,558.5],
					'Full paper size':[None,None]   }

		self.inputpdf=          None    #  string with pdf filepath
		self.input=             None    #  opened pdf file
		self.currentdoc=        None    #  Itext PDFReader object
		self.password=          None    #  if necessary
		self.pagecount=         None
		self.cropbox=           None
	
		self.duplex=            0
		self.duplexrotate=	True
		self.papersize=         self.papersizes['A4']   #  default for europe

		self.lockratio=         1
		self.flyleaf=           0
		self.spineoffset=       0
		self.format=            'standard sig'
		self.booksize=          self.targetbooksize['Full paper size']
		self.sigsize=           8       #  preferred signature size
		self.customsig=		None
		self.signatureconfig=	[]	#  signature configuration

		self.directoryname=     None

		self.orderedpages=      []      #  ordered list of page numbers (consecutive)
		self.rearrangedpages=   []      #  reordered list of page numbers (signatures etc.)

		self.filelist=          []      #  list of ouput filenames and path

	def openpdf(self,inputpdf):

		self.inputpdf=inputpdf

		self.input=open(self.inputpdf, "rb")

		try:
			self.currentdoc=PdfReader(self.input,self.password)
			print 'loaded PDF successfully'

		except IOError,errorout:

			stringer=str(errorout)

			return stringer

		except:

			return 'error:undefined error'

		self.input.close()              

	def closepdf(self):

		## closes PDFReader object
		if self.currentdoc:

			self.currentdoc.close()
			self.inputpdf=None

	def setpassword(self,password):

		self.password=password

	def setduplex(self,dup):

		self.duplex=dup

	def setduplexrotate(self,duplexrotate):

		self.duplexrotate=duplexrotate

	def setpapersize(self,papersize):

		self.papersize=self.papersizes[papersize]

	def setlockratio(self,ratio):

		self.lockratio=ratio

	def setflyleaf(self,fly):

		self.flyleaf=fly

	def setspineoffset(self,offset):
		
		self.spineoffset=offset

	def setbooksize(self,targetsize,customx=0,customy=0):

		if targetsize=='Full paper size':

			self.booksize=[self.papersize[1]*0.5,self.papersize[0]]

		elif targetsize=='Custom':

			x=customx
			y=customy
			self.booksize=[x,y]

		else:

			self.booksize=self.targetbooksize[targetsize]
			print 'in book self.booksize',self.booksize

	def setformat(self,format):

		self.format=format

	def setsigsize(self,size):

		self.sigsize=size

	def setsigconfig(self,config):

		self.signatureconfiguration=config
		self.customsig=1

	def getnumberpages(self):
		
		return self.pagecount

	def mm2point(self,millimetres):

		#       millimetres to points = 2.83464567
		#       points to millimetres = 0.352777778

		return millimetres*2.83464567

	def createpagelist(self):## change to pagenumbers

		self.orderedpages=[]
		self.pagecount=self.currentdoc.getNumberOfPages()

		for i in range(1,self.pagecount+1):

			self.orderedpages.append(i)

		if self.flyleaf:

			self.orderedpages.insert(0,'b')
			self.orderedpages.insert(0,'b')
			self.orderedpages.append('b')
			self.orderedpages.append('b')

		##      padding calculations if needed
		pagetotal=len(self.orderedpages)

		##      calculate how many sheets of paper the output document needs
		sheets=pagetotal/4

		##      pad out end of document if necessary
		if  pagetotal%4>0:

			sheets+=1

			padding=sheets*4-pagetotal

			for i in range(padding):

				self.orderedpages.append('b')


	##	this is the function which starts the final conversion to signatures
	##	parameters should have been set by default or the gui

	def createpages(self):  ## change to pagelist

		if self.orderedpages==[]:

			self.createpagelist()
		#print "book:orderedpages ",self.orderedpages
		
		#print "book:self.format ",self.format
		if self.format=='booklet':

			self.book=booklet(self.orderedpages,self.duplex)
			self.rearrangedpages=self.book.pagelist

		elif self.format=='perfect bound':

			self.book=perfectbound(self.orderedpages,self.duplex)
			self.rearrangedpages=self.book.pagelist

		elif self.format=='standard sig' or self.format=='custom sig':
			print "signatures creation"
			self.book=signatures(self.orderedpages,self.duplex,self.sigsize)
			
			if self.customsig:
				print "customsig branch"

				self.book.setsigconfig(self.signatureconfiguration)
			else:
				self.book.createsigconfig()

			self.rearrangedpages=self.book.pagelist

		#print "book:createpages ",self.rearrangedpages

	def createoutputfiles(self):
		
		##	create a directory named after the input pdf and fill it with
		##	the signatures

		#print "in book:createoutputfiles",  self.format
		#print 'opening pdf and making directory'

		filestuff=os.path.split(self.inputpdf)

		self.filename=self.removespaces(filestuff[1])
		self.directorypath=filestuff[0]

		self.directoryname=self.filename[:-4]+'-files'

		test=os.path.dirname(self.inputpdf)

		self.outputpath=os.path.join(test,self.directoryname)

		##      put some try/except code here
		if os.path.exists(self.directoryname):

			pass

		else:
			os.mkdir(self.directoryname)

		if self.format=='booklet':

			self.createsignatures(self.rearrangedpages,'booklet')

		elif self.format=='perfect bound':

			self.createsignatures(self.rearrangedpages,'perfectbound')

		elif self.format=='standard sig' or self.format=='custom sig':

			for i in range(len(self.rearrangedpages)):
				
				#print " outputfile",i

				self.createsignatures(self.rearrangedpages[i],'signature'+str(i))

		print 'Finished ',self.filename

	def removespaces(self,filename):

		'''     removes spaces from filename for cross platform chaos reduction         '''

		newname=''
		for letter in filename:

			if letter==' ' or letter==',':

				pass

			else:

				newname=newname+letter

		return newname

	def createsignatures(self,pages,id):

		#print "in book:createsignatures"
		##      duplex printers print both sides of the sheet, 
		if self.duplex:

			outduplex=self.directoryname+'/'+id+'duplex'+'.pdf'

			self.writepages(outduplex,pages[0],0)

			self.filelist.append(outduplex)

		##      for non-duplex printers we have two files, print the first, flip 
		##      the sheets over, then print the second. damned inconvenient

		else:

			outname1=self.directoryname+'/'+id+'side1.pdf'
			outname2=self.directoryname+'/'+id+'side2.pdf'
			#print outname1,outname2
			self.writepages(outname1,pages[0],0)
			self.writepages(outname2,pages[1],1)

			self.filelist.append(outname1)
			self.filelist.append(outname2)

	def writepages(self,outname,pagelist,side2flag):
		
		side='front'
		imposedpage='left'

		outPDF = Document(Rectangle(self.papersize[0],self.papersize[1]))
		outstream=open(outname,'wb')
		output=PdfWriter.getInstance(outPDF, outstream)
		outPDF.open()

		pagedata=output.getDirectContent()

		#print "in book:writepages"
		for i in range(len(pagelist)):

			if i%2==0:

				outPDF.newPage()
				outPDF.add(Chunk.NEWLINE)

			pagenumber=pagelist[i]

			##	scaling code here
			if pagenumber=='b':
				#print 'blank'
				pass

			else:

				if i%2==0:

					imposedpage='left'

					if side2flag or ((i+2)%4==0 and self.duplex):

						side='back'

					else:

						side='front'
				else:


					imposedpage='right'
				#print 'adding page'
				baseline,leftstart,scale1,scale2=self.calculateposition(pagenumber,imposedpage,side)

				page = output.getImportedPage(self.currentdoc, pagenumber)

				pagedata.addTemplate(page, -0, scale1, scale2, 0, baseline, leftstart)

			#print i,pagenumber,side,imposedpage
		outPDF.close()
		outstream.close()

	def calculateposition(self,pagenumber,imposedpage,side):

		'''     calculate scaling, and the x and y translation values for the 2up output        '''

		cropbox=self.getcropbox(pagenumber)

		if cropbox:

			pagex=cropbox[2]-cropbox[0]
			pagey=cropbox[3]-cropbox[1]
			
			print 'c',pagex,pagey,cropbox[0],cropbox[1]

		else:

			currentpagesize=self.currentdoc.getBoxSize(pagenumber,'media')

			pagex,pagey=self.getpagesize(str(currentpagesize))

		targetratio=self.booksize[1]/self.booksize[0]           #       targetpage ratio
		inputratio=pagey/pagex                                  #       inputpage ratio

		##      Keep the page proportions (lockratio=1) or stretch to fit target page (lockratio=0)
		if self.lockratio:

			if targetratio>inputratio:            #       input page is fatter than target page
				#       scale with width
				scale=self.booksize[0]/pagex

			else:                                 #       input page is thinner than target page
				#       scale with height
				scale=self.booksize[1]/pagey

			scale1=scale
			scale2=scale

		else:

			scale1=self.booksize[0]/pagex
			scale2=self.booksize[1]/pagey

		sheetwidth=self.papersize[0]
		sheetheight=self.papersize[1]

		bookwidth=pagex*scale1             #       width of imposed page
		bookheight=pagey*scale2            #       height of imposed page

		centreline=sheetheight*0.5              #       centreline of page

		xpad=(sheetwidth-bookwidth)/2.0        #       horizontal centering
		ypad=(sheetheight-(2.0*bookheight))/2.0 #       vertical centering for two-up

		##      sheet guidelines: side 1 

		if not self.duplexrotate or side=='front':

			baseline=xpad	#       x translation value for 2up

			if imposedpage=='left':

				leftstart=centreline+ypad+self.spineoffset # y translation for top page

			elif imposedpage=='right':

				leftstart=ypad-self.spineoffset        # y translation for bottom page

		##      sheet guidlines: side2

		elif side=='back':
		
			baseline=sheetwidth-xpad                  	# x translation for 2up 

			if imposedpage=='left':

				leftstart=ypad+self.spineoffset		# y translation for top page

			elif imposedpage=='right':

				leftstart=centreline-self.spineoffset	# y translation for bottom page


		if cropbox:

			xoffset=cropbox[0]*abs(scale1)
			yoffset=cropbox[1]*abs(scale2)

			if not self.duplexrotate or side=='front':

				baseline=baseline-yoffset
				leftstart=leftstart+xoffset
				

			elif side=='back':

				baseline=baseline+yoffset
				leftstart=leftstart-xoffset

		if not self.duplexrotate or side=='front':

			scale1=-scale1

		elif side=='back':

			scale2=-scale2

		return baseline,leftstart,scale1,scale2

	def getcropbox(self,index):
	
		page=self.currentdoc.getPageN(index)            #       get the PdfDictionary object for the page
		diclist=page.getKeys()                          #       get the keys to the dictionary

		if page.contains(PdfName.CROPBOX):              #       search keys for cropbox using 'contains'

			cb4=self.currentdoc.getPdfObject(page.get(PdfName.CROPBOX)) #  fetch the 4 values we want
			#(PdfName.MEDIABOX) (PdfName.BLEEDBOX) (PdfName.TRIMBOX) PdfName.ARTBOX)


			string=str(cb4)                         #       convert from JavaInstance to PyString
			string=string[1:-1]                     #       remove brackets
			splitstr=string.split(',')              #       split around commas
			
			colist=[]                               #       list to hold float converted coordinates
			
			for val in splitstr:

				colist.append(float(val))       #       convert strings to floats
								#       coordinates now available to use
			#print colist
			return colist

		else:


			return None

	def getpagesize(self,pagestring):

		'''     extract the page size from the string input, convert to integers        '''

		pagesize=string.strip(pagestring[11:])  #       cut out word 'rectangle'
		pagesize=string.split(pagesize,'x')     #       split around 'x', get a list of two numbers

		pattern=re.compile(r'[0-9]+')           #       number pattern

		sizes=[]

		for number in pagesize:

			hit=pattern.findall(number)     #       extract just the numbers, 
			sizes.append(hit[0])

		pagesizex=float(sizes[0])       
		pagesizey=float(sizes[1])

		return pagesizex,pagesizey


class perfectbound:

	'''     Duplex printer pages are arranged in a 4-1-2-3 pattern.
		Single-sided pages are arranged in two sets, 4-1 and 2-3.
		After printing two to a page, each sheet is folded in half
		and all the sheets collated into a block for gluing. 
		self.pagelist holds the rearranged index numbers that the 
		book class uses to create a finished document
	'''

	def __init__(self,pages,duplex):

		#print 'perfectbound: pages',pages
		self.duplex=duplex

		self.sigconfig=[4]*(len(pages)/4)

		if self.duplex:

			self.pagelist=[[]]

		else:

			self.pagelist=[[],[]]

		for i in range(0,len(pages),4):

			if self.duplex:

				self.pagelist[0].append(pages[i+3])
				self.pagelist[0].append(pages[i])
				self.pagelist[0].append(pages[i+1])
				self.pagelist[0].append(pages[i+2])

			else:

				self.pagelist[0].append(pages[i+3])
				self.pagelist[0].append(pages[i])
				self.pagelist[1].append(pages[i+1])
				self.pagelist[1].append(pages[i+2]) 

class booklet:

	'''     The basic rearrangement of pages, such that printing out and folding
		the sheets in half creates a correctly ordered booklet. 
	'''

	def __init__(self,pages,duplex):

		self.duplex=duplex
		
		self.sigconfig=[1]

		if self.duplex:

			self.pagelist=[[]]

		else:

			self.pagelist=[[],[]]

		length=len(pages)
		
		

		forwards=0
		backwards=length-1
		backwards2=length-2
		forwards2=1

		for i in range(0,length,4):

			if self.duplex:

				self.pagelist[0].append(pages[backwards])
				self.pagelist[0].append(pages[forwards])
				self.pagelist[0].append(pages[forwards2])
				self.pagelist[0].append(pages[backwards2])

			else:

				self.pagelist[0].append(pages[backwards])
				self.pagelist[0].append(pages[forwards])
				self.pagelist[1].append(pages[forwards2])
				self.pagelist[1].append(pages[backwards2])      

			backwards=backwards-2
			forwards=forwards+2
			backwards2=backwards2-2
			forwards2=forwards2+2


class signatures:

	'''     Takes a list of pagenumbers, splits them evenly, then rearranges the pages in each chunk.

	'''

	def __init__(self,pages,duplex,sigsize):

		#print "signatures class"
		self.sigsize=sigsize
		self.duplex=duplex
		self.inputpagelist=pages
		
		self.pagelist=[]

		self.sheets=len(pages)/4

		self.sigconfig=[]
		self.signaturepagelists=[]

		##      preset configurations for documents less than 192 pages
		self.signatureconfigurations=[  
				(1,),(1,),(2,),(3,),(4,),(5,),(6,),(7,),(8,),(9,),(10,),(11,),
				(12,),(13,),(14,),(15,),(16,),(9,8),(9,9),(10,9),(10,10),
				(7,7,7),(8,7,7),(8,8,7),(8,8,8),(9,8,8),(9,9,8),(9,9,9),
				(7,7,7,7),(8,7,7,7),(8,8,7,7),(8,8,8,7),(8,8,8,8),(9,8,8,8),
				(9,9,8,8),(7,7,7,7,7),(8,7,7,7,7),(8,8,7,7,7),(8,8,8,7,7),
				(8,8,8,8,7),(8,8,8,8,8),(9,8,8,8,8),(7,7,7,7,7,7),(8,7,7,7,7,7),
				(8,8,7,7,7,7),(8,8,8,7,7,7),(8,8,8,8,7,7),(8,8,8,8,8,7),(8,8,8,8,8,8)
				]

	def setsigconfig(self,config):

		self.sigconfig=config
		
		targetlength=len(self.inputpagelist)
		
		##	calculatelength given by multiplying config values by 4
		##	 and ensuring padding if longer than self.inputlist
		total=0

		for num in self.sigconfig:

			total+=(int(num)*4)

		if total>targetlength:

			diff=total-targetlength

			for i in range(diff):

				self.inputpagelist.append('b')

		self.pagelist=[]
		self.signaturepagelists=[]

		self.splitpagelist()

	def createsigconfig(self):

		'''     Calculate signatures and points to split text into chunks'''

		##      if document is longer than 192 pages, calculate number and length of signatures
		if self.sheets>48:

			self.sigconfig=self.generatesignatureindex()
			#print "signatures:sigconfig,generate",self.sigconfig

		##      if document is less than 192 pages use lookup table
		else:

			self.sigconfig=self.signatureconfigurations[self.sheets]
			#print "signatures:sigconfig,sheets",self.sigconfig
			
		self.pagelist=[]
		self.signaturepagelists=[]
		
		self.splitpagelist()


	def splitpagelist(self):

		point=0
		splitpoints=[0]

		##      calculate the points at which to split the document
		for number in self.sigconfig:

			point=point+(number*4)
			splitpoints.append(point)

		for i in range(len(self.sigconfig)):

			pagerange=[]    
			start=splitpoints[i]
			end=splitpoints[i+1]

			##      grab the chunk of page indices
			pagerange=self.inputpagelist[start:end]

			self.signaturepagelists.append(pagerange)

		newsigs=[]

		##      Use the booklet class for each signature
		for pagerange in self.signaturepagelists:

			newlist=booklet(pagerange,self.duplex)
			newsigs.append(newlist.pagelist)

		self.pagelist=newsigs

	def generatesignatureindex(self):

		'''     Calculate the number and length of the signatures required. 
			Called if text is longer than 192 pages .
		'''

		preliminarytotal=self.sheets/self.sigsize
		modulus=self.sheets%self.sigsize

		if modulus>0:

			##      need an extra signature
			signaturetotal=preliminarytotal+1
			flag=1

		else:

			##      signature amount and pagelength match perfectly first time.
			signaturetotal=preliminarytotal
			flag=0

		##      calculate how many signatures are the full size and how many are one sheet short.
		factor=signaturetotal-(self.sigsize-1)
		factor+=(modulus-1)

		result=[]

		##      lay down the pattern
		for i in range(signaturetotal):

			if i>=factor and flag:

				result.append(self.sigsize-1)

			else:

				result.append(self.sigsize)

		return result
