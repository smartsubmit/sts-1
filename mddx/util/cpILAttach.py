# coding=utf8
# Test pyodbc connection. Result is 42.
# Note parameters in connection string, <PARAMETER>.

import pyodbc
import sys
import os
import os.path
import re
import string
import boto3
import zipfile
from botocore.exceptions import ClientError
import botocore.session
import binascii
#import psutil

#for pid in psutil.pid():
#	p = psutil.Process(pid)
#	if p.name() == "python" and len(p.cmdline()) > 1 and "cpILAttach.py" in p.cmdline()[1]:
#		exit
#
string_types = str
conn = pyodbc.connect('DRIVER=FreeTDS;SERVER=DBHost;PORT=1433;DATABASE=MDDXIT;UID=sa;PWD=aiHwZ2!Qp2Xf;TDS_Version=8.0;', autocommit=True)
resource = boto3.resource('s3')
bucket = resource.Bucket('iqctest')
client = boto3.client('s3', 'us-west-2')
exist = True
AttachPath = '/attachments/'
#    print(bucket.name)


def CRC32_from_file(mergeFile):
    buf = open(mergeFile,'rb').read()
    buf = (binascii.crc32(buf) & 0xFFFFFFFF)
    return "%08X" % buf

def file_size(mergFile):
    size = os.stat(mergeFile)
    return size.st_size

with conn:

     cursor = conn.cursor()
     while True:
	cursor.execute("select CaseId from dbo.[PendingTransferQue] where IsAttachmentTransferred is NULL or IsAttachmentTransferred = 0")

	row = cursor.fetchone()
        print row
        if row is not None:
		Case = row[0]
                print Case
		cursor.execute("select c.CopyToCl, c.CustomFieldID, cf.FileName, cf.FileServerName From dbo.[CaseFileUpload] cf join dbo.[CustomField] c on cf.CustomFieldID = c.CustomFieldID where cf.CaseID = '%d' and cf.CaseType = 'UploadItf' and cf.FileServerName is not NULL and c.CopyToCl = 1" %(Case))
   		rows = cursor.fetchall()
                print rows, row, Case
#		cursor.execute("UPDATE dbo.[PendingTransferQue] SET IsAttachmentTransferred = 1 where CaseId = '%d'" %(Case))
                while True:
			cursor.execute("select DownloaderBucket from  CaseFileNamesInBucket where caseid = '%d' " % (Case))
			attachBucket = cursor.fetchone()[0]
			if attachBucket is None:
				break
			#if (len(attachBucket.split(' ')) == 0:
			if len(attachBucket.split()) == 0:
                                break
	      	        if rows == []:
				attachZip = attachBucket
			else:
				attachZip = string.replace(str(attachBucket), '.zip', '_attachment.zip')
			print attachBucket, attachZip
			srcZipFile = str(Case) + '.zip'
			dstZip = str(Case) + '.zip'
			cursor.execute("select a.AccountName from CaseDetailsByfnFarthestFields cf join [Account] a on cf.AccountID = a.AccountID where cf.Case_Id = '%d' " % (Case))
			AccountName = cursor.fetchone()[0]
                        cursor.execute("select cf.Trial_id from CaseDetailsByfnFarthestFields cf join [Account] a on cf.AccountID = a.AccountID where cf.Case_Id = '%d' " % (Case))
			CaseID = cursor.fetchone()[0]
	                srcZipPath = os.path.join('/tmp/', str(attachBucket))
	                mergeFile = os.path.join('/tmp/', str(attachZip))
                        print AccountName, CaseID
	                #srcCase = os.path.join('autopxfolder/', str(AccountName), '/', str(CaseID), '/', str(attachBucket))
	                srcCase = 'autopxfolder/' + str(AccountName) + '/' + str(CaseID) + '/' + str(attachBucket)
	                print rows, srcZipPath, srcZipFile, srcCase
			print 'iqctest', srcCase, srcZipPath
			try:
				client.download_file('iqctest', srcCase, mergeFile)
			except Exception as e:
				cursor.execute("UPDATE dbo.[PendingTransferQue] SET IsAttachmentTransferred = 1 where CaseId = '%d'" %(Case))
				break
				
			#if os.path.isfile(srcZipPath):
			#	z = zipfile.ZipFile(mergeFile, "w")
			#	#z.write(srcZipPath)
			#	z.printdir()
			#	z.close()

	   		for row in rows:
				srcZipFile = zipfile.ZipFile(mergeFile,"a",allowZip64=True)
				#srcZipFile = zipfile.ZipFile("mergeFile","a",zipfile.ZIP_DEFLATED)
	      			src = '/attachments/' + row.FileServerName
				if row.FileName is not None:
		      			srcOrig = row.FileName
					srcOrig = re.sub(r'~.*?~', '', srcOrig)
				else:
					srcOrig = row.FileServerName
				if not os.path.isfile(src):
					print("ERROR: %s Does not exist in UploadedFiles, even though it's in the database." % (src))
	           			continue
		        	dst = 'uiqcfolder' + '/attachments/' + srcOrig
				print mergeFile
				if os.path.isfile(mergeFile):
					srcZipFile = zipfile.ZipFile(mergeFile,"a",allowZip64=True)
					print src, dst, srcZipPath, srcZipFile, Case, row.FileServerName
					srcZipFile.write(src,'/attachments/' + srcOrig)
					srcZipFile.close()
	        		try:
					client.upload_file(src, 'iqctest', dst)
				except ClientError as ce:
					print(ce.response)
					print(ce.response['Error']['Code'])
					if ce.response['Error']['Code'] == "NoSuchKey":
						exist = False
						print("ERROR: %s Does not exist in S3, even though it's in the database." % (src))
		                       		continue	
               				else:
               					raise ce
      #if 'exist' == "True":
			if os.path.isfile(mergeFile):
				dstAttachZip = 'autopxfolder/' + str(AccountName) + '/' + str(CaseID) + '/' + attachZip                                
				crc32 = CRC32_from_file(mergeFile)
				size = file_size(mergeFile)
				cursor.execute("select Case_Pre_Post_Id from Case_Pre_Post where Case_Id = '%d' and case_type ='post-anon'" %(Case))
				PrePostId = cursor.fetchone()[0]
				cursor.execute("insert into dbo.[CaseFileMD5CheckSum](FileCheckSum, CasePrePostID, FileSize) values ('%s', '%d', '%d')" %(crc32,PrePostId,size))
                                print mergeFile, crc32, PrePostId, size 
				client.upload_file(mergeFile, 'iqctest', dstAttachZip)
				cursor.execute("UPDATE dbo.[PendingTransferQue] SET IsAttachmentTransferred = 1 where CaseId = '%d'" %(Case))
			break
		cursor.execute("UPDATE dbo.[PendingTransferQue] SET IsAttachmentTransferred = 1 where CaseId = '%d'" %(Case))
	if row is None:
		break
conn.close()
#                cursor.execute("UPDATE dbo.[CustomFieldAttachmentToBeTransfered] SET IsTransfered = 'false' where FileName = '%s'" %(row.FileName))
      #s3.Object(src).delete()
