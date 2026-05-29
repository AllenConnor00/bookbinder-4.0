To compile bookbinder you will need Java and Jython installed and working and 
in your Java classpath you will need these packages:

	itext 1.4		-PDF manipulation library	http://www.lowagie.com/iText
	bouncycastle	-en/decryption framework	http://www.bouncycastle.org

The itext version is 1.4, not the latest, which is considerably different and won't work with bookbinder. Also, the redistribution license was changed, but I've stuck with the 1.4 licensing.
I generally unzip the jar files and place the directories in my Jython directory with book.py and bookgui.py

Call the jython compiler with the following:

jythonc --core  --all --addpackages="com.lowagie.text,org.jpedal,org.bouncycastle,javax.crypto,gfx" --jar bookgui.jar bookgui.py


If all has gone well there should now be a bookgui.jar. Non java files don't get compiled in, so the jar 
will be lacking fonts . We add these back in with a call to the jar utility.

jar uf bookgui.jar com\lowagie\text\pdf\fonts


It should now work.

