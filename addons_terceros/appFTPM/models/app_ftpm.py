#from email.policy import default
from openerp import api,fields,models
import ftplib
from ftplib import FTP_TLS
import os
import socket
import time
import ssl
from os import remove
from os import path
from datetime import datetime, timedelta
import logging, os, shutil, base64
_logger = logging.getLogger(__name__)



carpeta_temp = "/mnt/temp/"

class appHV(models.Model):
    _name="app.ftpm"
    _description="Carga de archivos ftp"
    
    # fields 
    def get_value_port(self):
        return str('21')
    puerto = fields.Integer(default=get_value_port)
    server = fields.Char(string="Servidor")
    user = fields.Char(string="Usuario")
    pass_user = fields.Char(string="Contraseña")
    resultado = fields.Text(string="Resultado")
   # conexion = fields.Boolean(string = "Conexión pasiva?")
    save_name=fields.Char(string="Nombre de archivo en el servidor")
    save_name_local=fields.Char(string="Nombre de archivo local")
    pass_zip=fields.Char(string="Clave para el zip")
    ssl_certif=fields.Boolean(string = "SSL")
    default=fields.Boolean(string = "Default")
    regla_negocio=fields.Boolean(string = "Regla de negocio")
    def get_value_directoy(self):
        return str('./')
    resultado_local = fields.Text(string="Resultado proceso")
    directory_save = fields.Char(string="Directorio FTP", default=get_value_directoy)
    directory_save_local = fields.Char(string="Directorio Local", default=get_value_directoy)

            #raise Warning()

    #def create_company(self):
        # instructions_before
     #   res=super().descargar()
        # instruction_after
      #  self.resultado = res
       # return res

    #  * **************************************** Procesos Servidor *********************************** *

    def ssl_true(self):
        if self.ssl_certif == True:
            ctx = ssl._create_stdlib_context(ssl.PROTOCOL_TLSv1_2)
            ftp = ftplib.FTP_TLS(context=ctx)
            ftp = FTP_TLS(self.server)
            ftp = ftplib.FTP_TLS(timeout=60)
        else:
            ftp = ftplib.FTP(timeout=60)
        return ftp

    def conect_server_ftp(self):
        ftp = self.ssl_true()
        try:
            ftp.connect(self.server, self.puerto)
        except (socket.error, socket.gaierror)as e:
            self.resultado = 'Error al encontrar el servidor'
        else:
            try:
                ftp.login(self.user, self.pass_user)
                if self.ssl_certif == True:
                    ftp.prot_p()

            except (socket.error, socket.gaierror)as e:
                    self.resultado ='Error user o clave'
            else:
                self.resultado = 'Se conecto correctamente al servidor'
        return ftp
    

    def list_files_directory(self):
        ftp = self.conect_server_ftp()
        files = []
        directory_list = self.directory_save
        ftp.cwd(directory_list)
        try:
            files = ftp.nlst()
        except ftplib.error_perm as resp:
            if str(resp) == "550 Archivos no encontrados":
                    self.resultado ="No hay archivos en este directorio"
            else:
                raise
        for f in files:
            self.resultado = str("Directorio: {}".format(ftp.nlst()))
        ftp.close()


    def download_files(self):
        ftp = self.conect_server_ftp()
        fileN = self.save_name
        remotefile = fileN
        directory_user = self.directory_save
        os.chdir(carpeta_temp + directory_user + "/")
        local_path = os.getcwd()
        if not os.path.exists(local_path):
            os.makedirs(local_path)
        filename = os.path.join(local_path, remotefile)
        file = open(filename, "wb")
        ftp.retrbinary("RETR " + remotefile, file.write)
        self.resultado = "Descargó el archivo " + fileN + " correctamente"
        ftp.close() 


    def upload_file(self):
        _logger.info("empece a subir ftp")
        ftp = self.conect_server_ftp()
        fileN =  self.save_name_local
        directory_user = self.directory_save_local
        _logger.info("ya obtuve estos valores " + fileN + " " + directory_user)
        os.chdir(carpeta_temp + directory_user + "/")
        local_path = os.getcwd()
        filename = os.path.join(local_path, fileN)
        file = open(filename,'rb')              
        name_save_ftp = self.save_name_local
        try:
            ftp.storbinary('STOR %s' % self.directory_save + "/" + name_save_ftp, file) 
        except:
            _logger.info("Error al subir el archivo en el directorio " + self.directory_save + "/" + name_save_ftp)      
        self.resultado = "Subió " + name_save_ftp + " al servidor correctamente" + self.directory_save + "/" + name_save_ftp
        file.close()                                    
            
    
    def delete_file(self):
        ftp = self.conect_server_ftp()
        directoryS =  self.directory_save
        ftp.cwd(directoryS)
        name_delete_ftp = self.save_name
        ftp.delete(name_delete_ftp)
        self.resultado = "Se eliminó "+ name_delete_ftp + " correctamente del servidor"
        ftp.close()   

    def close_connection(self):
        ftp = self.conect_server_ftp()
        try:
            ftp.close()
        except (socket.error, socket.gaierror)as e:
            self.resultado = "No existe conexión activa"
            return False
        else:
            self.resultado = "Se cerró la conexión del servidor"
        return True

    #  * **************************************** Procesos locales *********************************** *
    
    def list_local_files(self):
        directory_user = self.directory_save_local
        dirlocal = os.listdir(carpeta_temp + directory_user + "/")
        self.resultado_local = "Directorio: {}".format(dirlocal)#str(dirlocal)


    def delete_local_files(self):
        directory_user = self.directory_save_local
        dirlocal = carpeta_temp + directory_user + "/"
        file_name = self.save_name_local
        if path.exists(dirlocal + file_name):
            remove(dirlocal + file_name)
            self.resultado_local = "Se eliminó correctamente el archivo " + file_name + " del directorio local"
        else:
            self.resultado_local = "El archivo " + file_name + " no existe en el directorio local"
            return False
        return True

   
