import errno
from odoo import models, fields, api
from odoo.exceptions import Warning
# nuevo import 
import shutil
import zipfile
import pyzipper
try:
    import zlib
    compression = zipfile.ZIP_DEFLATED
except:
    compression = zipfile.ZIP_STORED

from datetime import datetime, timedelta
import logging, os, shutil, base64
_logger = logging.getLogger(__name__)

carpeta_temp = "/mnt/temp/" # carpeta donde se guarda todo 
#carpeta_temp = "/extra_addons/addons_resources/" # carpeta donde se guarda todo 

class GeneradorReportes(models.TransientModel):
    _name = "motgama.generareporte"
    _description = "Generador de reportes"

    # Para generación de reportes
    codigo_accion_automatica = fields.Integer(string="Código de acción automática")
    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    nombre_reporte = fields.Char(string="Nombre del reporte")

    # Ruta del zip generado
    path_archivo_zip = fields.Char(string="Ruta del archivo zip")

    # Para generar log
    error = fields.Text(string="Error")

    @api.model
    def ejecutar_proceso(self, codigo_accion_automatica=0, genera_interfaz=False, fecha_inicial=fields.Datetime.now() - timedelta(hours=24), fecha_final=fields.Datetime.now(), param=False, correoEnv="", numeroReporte = "", company = ""):
        _logger.info("Inicia proceso de generación de reportes, revisando hora")
       

        _logger.info("Hora de generar reporte, iniciando proceso")
        nuevo_proceso = self.create({
            "fecha_inicial": fecha_inicial,
            "fecha_final": fecha_final,
            "nombre_reporte": self.generar_nombre_reporte(fecha=fecha_final),
            "codigo_accion_automatica": codigo_accion_automatica
        })
        _logger.info("Reporte " + nuevo_proceso.nombre_reporte + " será generado")

        reporte_consumos_generado = False
        reporte_ventas_generado = False
        reporte_recaudo_generado = False
        interfaz_contable_generada = False
        zip_generado = False
        correo_enviado = False
        ftp_subido = False

        carpeta_creada = nuevo_proceso.create_carpeta()
        if carpeta_creada:
            _logger.info("se creo carpeta y se procede a realizar los otros procesos")
            reporte_consumos_generado = nuevo_proceso.generar_reporte_consumos(company)
           
            reporte_ventas_generado = nuevo_proceso.generar_reporte_ventas(numeroReporte, company)
            if numeroReporte=="1":
                _logger.info("Debo generar reporte recaudos")
                reporte_recaudo_generado = nuevo_proceso.generar_reporte_recaudos(company)

            interfaz_contable_generada = nuevo_proceso.generar_interfaz()

            zip_generado = nuevo_proceso.generar_zip()

            correo_enviado = nuevo_proceso.enviar_correo(correoEnv)

            ftp_subido = nuevo_proceso.enviar_ftp(param)
        

        nuevo_proceso.generar_log(datos_log={
            "reporte_ventas_ok": reporte_ventas_generado,
            "reporte_recaudo_ok": reporte_recaudo_generado,
            "reporte_consumos_ok": reporte_consumos_generado,
            "interfaz_contable_ok": interfaz_contable_generada,
            "archivo_zip_ok": zip_generado,
            "enviar_correo_ok": correo_enviado,
            "subir_ftp_ok": ftp_subido,
            "codigo_accion_automatica": codigo_accion_automatica,
            "nombre_reporte": self.nombre_reporte,
            "fecha_inicial": self.fecha_inicial,
            "fecha_final": self.fecha_final
        })

        _logger.info("Proceso de generación de reportes finalizado")
        return

    @api.model
    def get_hora(self):
        paramHora = self.env['motgama.parametros'].search([('codigo','=','HORACIERRE')],limit=1)
        fecha_actual = datetime.now()
        if not paramHora:
            raise Warning('No se ha definido el parámetro "HORACIERRE"')
        horaTz = datetime.strptime(paramHora.valor,'%H:%M')
        hora = horaTz + timedelta(hours=5)

        return datetime(fecha_actual.year,fecha_actual.month,fecha_actual.day,hora.hour,hora.minute)

    @api.model
    def revisar_hora(self, fecha):
        return bool(fecha < datetime.now() < fecha + timedelta(minutes=5))

    @api.model
    def generar_nombre_reporte(self, fecha=datetime.now()):
        fechaAct = datetime.now()
        nombre_report = str(fechaAct.year) + str(fechaAct.month) + str(fechaAct.day) + str(fechaAct.hour) + str(fechaAct.minute) + str(fechaAct.second)
        return nombre_report

    @api.multi
    def registrar_error(self, error):
        self.ensure_one()
        texto = error + "\n"
        if self.error:
            texto = self.error + texto
        self.write({"error": texto})
        return

    @api.multi
    def path_carpeta(self):
        self.ensure_one()
        return os.path.join(carpeta_temp, self.nombre_reporte)

    @api.multi
    def create_carpeta(self):
        self.ensure_one()
        _logger.info("Carpeta a crear "+ carpeta_temp + self.nombre_reporte)
        try:
            os.mkdir(os.path.join(carpeta_temp, self.nombre_reporte))
        except OSError as e: 
            if e.errno != errno.EEXIST:
                _logger.info("Carpeta a crear "+ carpeta_temp + self.nombre_reporte + "Ya existe")
            else:
                self.registrar_error("- No fue posible crear carpeta")
                _logger.info("Error desconocido")
                return False
        _logger.info("Carpeta a crear "+ carpeta_temp + self.nombre_reporte + "se ha creado correctamente")
        return True

    

    @api.multi
    def generar_reporte_ventas(self,numeroReporte="", company=""):
        _logger.info("Inicia generación de reporte de ventas:"+ numeroReporte)
        self.ensure_one()
        try:
            wizard_reporte = self.env['motgama.wizard.reporteventas'].create({
                'tipo_reporte': 'fecha',
                'fecha_inicial': self.fecha_inicial,
                'fecha_final': self.fecha_final,
                'company':company,
                'es_manual': False
            })
            wizard_reporte.get_report(numeroReporte)
            _logger.info("Datos guardados, procediendo a generar pdf Reporte de ventas")
            _logger.info(data_reporte.ids)
            data_reporte = self.env['motgama.reporteventas'].search([])
            _logger.info("Reporte  será generado")
            pdf_data = self.env.ref("motgama.reporte_ventas").sudo().render_qweb_pdf(data_reporte.ids)[0]
            _logger.info("PDF generado, procediendo a guardar en disco")
            path_reporte = os.path.join(self.path_carpeta(), "reporte_ventas.pdf")

            with open(path_reporte, "wb") as archivo:
                archivo.write(pdf_data)
        except:
            _logger.warning("No se pudo guardar el reporte de ventas")
            self.registrar_error("- No fue posible generar el reporte de ventas")
            return False
        _logger.info("Reporte de ventas guardado con éxito")
        return True

    @api.multi
    def generar_reporte_recaudos(self, company=""):
        _logger.info("Inicia generación de reporte de recaudos")
        self.ensure_one()
        try:
            wizard_reporte = self.env['motgama.wizard.reporterecaudos'].create({
                'fecha_inicial': self.fecha_inicial,
                'fecha_final': self.fecha_final,
                'company':company
            })
            wizard_reporte.get_report()
            _logger.info("Datos guardados, procediendo a generar pdf")

            data_reporte = self.env['motgama.reporterecaudos'].search([])
            _logger.info("Reporte  será generado")
            pdf_data = self.env.ref("motgama.reporte_recaudos").sudo().render_qweb_pdf(data_reporte.ids)[0]
            _logger.info("PDF generado, procediendo a guardar en disco")
            path_reporte = os.path.join(self.path_carpeta(), "reporte_recaudos.pdf")

            with open(path_reporte, "wb") as archivo:
                archivo.write(pdf_data)
        except:
            _logger.warning("No se pudo guardar el reporte de recaudos")
            self.registrar_error("- No fue posible generar el reporte de recaudos")
            return False
        _logger.info("Reporte de recaudos guardado con éxito")
        return True


   


    @api.multi
    def generar_reporte_consumos(self, company):
        _logger.info("Inicia generación de reporte de consumos")
        self.ensure_one()
        try:
            wizard_reporte = self.env['motgama.wizard.reporteconsumo'].create({
                'tipo_reporte': 'fecha',
                'fecha_inicial': self.fecha_inicial,
                'fecha_final': self.fecha_final,
                'company':company
            })
            wizard_reporte.get_report()
            _logger.info("Datos guardados, procediendo a generar pdf")

            data_reporte = self.env['motgama.reporteconsumos'].search([])
            _logger.info("encontro reporte consumos")
            _logger.info((data_reporte.ids))
            # Siempre falla en está instrucción 
            pdf_data = self.env.ref('motgama.reporte_consumo').sudo().render_qweb_pdf(data_reporte.ids)[0]
            _logger.info("PDF generado, procediendo a guardar en disco")
            path_reporte = os.path.join(self.path_carpeta(), "reporte_consumos.pdf")

            with open(path_reporte,"wb") as archivo:
                archivo.write(pdf_data)
        except:
            _logger.warning("No se pudo guardar el reporte de consumos")
            self.registrar_error("- No fue posible generar el reporte de consumos")
            return False
        _logger.info("Reporte de consumos guardado con éxito")
        return True

    

    @api.multi
    def generar_interfaz(self):
        _logger.info("Inicia generación de interfaz contable")
        self.ensure_one()
        #try:
        wizard_interfaz = self.env['motgama.wizard.interfazcontable'].create({
            'nueva': True,
            'fecha_inicial': self.fecha_inicial,
            'fecha_final': self.fecha_final,
            'genera_csv': True,
            'es_manual': False
        })
        data_reporte = wizard_interfaz.genera_reporte_csv()
        _logger.info("Interfaz generada, procediendo a guardar en carpeta")
        path_reporte = os.path.join(self.path_carpeta(), "interfaz_contable.csv")
        with open(path_reporte, 'wb') as archivo:
            archivo.write(data_reporte)
        #except:
            #_logger.warning("No se pudo guardar la interfaz contable")
            #self.registrar_error("- No fue posible generar la interfaz contable")
            #return False
        _logger.info("La interfaz contable fue guardada con éxito")
        return True


    @api.multi
    def generar_zip(self):
        try:
            path_origin = carpeta_temp  + "/" + self.nombre_reporte 
            path_archivo = carpeta_temp + self.nombre_reporte + ".zip"
            zip_file = pyzipper.AESZipFile(path_archivo,'w',compression=pyzipper.ZIP_DEFLATED,encryption=pyzipper.WZ_AES)
            _logger.info("Va a obtener password zip")
            server = self.env["app.ftpm"].search([("default","=",True)],limit=1)
            _logger.info("pass zip:"+server.pass_zip)
            zip_file.pwd= bytes(server.pass_zip.encode("utf-8"))# cambiar esto por self.password
            for archivo in os.listdir(path_origin):
                    zip_file.write(os.path.join(path_origin, archivo))
                    self.write({"path_archivo_zip": path_archivo})
        except:
            _logger.info("No se generó zip")
            return False
        zip_file.close()
        return True

    @api.multi
    def enviar_correo(self, correoEnviar):
        self.ensure_one()
        _logger.info("Inicia envío de correo")
        try:
            with open(self.path_archivo_zip, "rb") as archivo_zip:
                data_zip = archivo_zip.read()
                
                adjunto = self.env['ir.attachment'].create({
                    'name': self.nombre_reporte,
                    'type': 'binary',
                    'datas': base64.encodestring(data_zip),
                    'res_model': 'motgama.reporteventas',
                    'datas_fname': self.nombre_reporte+".zip",
                    'mimetype': 'application/zip'
                })
                _logger.info("Se creó el adjunto con el archivo zip")

                sucursal = self.env['motgama.sucursal'].search([], limit=1)
                _logger.info("Está a un paso de enviar el correo")
                #paramCorreo = self.env['motgama.parametros'].search([('codigo','=','EMAILINTERFAZ')],limit=1)
               # if not paramCorreo:
             #       _logger.warning('No se ha definido el parámetro "EMAILINTERFAZ"')
             #      return False
                email_to = correoEnviar
                mailserver = self.env['ir.mail_server'].sudo().search([],limit=1)
                if not mailserver:
                    email_from = ''
                else:
                    email_from = mailserver.smtp_user
                correo = self.env['mail.mail'].create({
                    'subject': sucursal.nombre + ': Envío de reporte ' + self.nombre_reporte,
                    'body_html': 'Motgama hace envío del reporte ' + self.nombre_reporte + ', el cual se encuentra adjunto a este correo',
                    'email_from': email_from,
                    'email_to': email_to,
                    'attachment_ids': [(6, 0, [adjunto.id])]
                    
                })
                correo.send()
        except:
            _logger.warning("Error al enviar el correo")
            self.registrar_error("- No se pudo enviar el correo")
            return False
        _logger.info("Se envió el correo")
        return True

    @api.multi
    def enviar_ftp(self,param):
        self.ensure_one()
        try:
            server = self.env["app.ftpm"].search(["&",("default","=",True),("regla_negocio","=",param)],limit=1)
            server.write({"save_name_local":self.nombre_reporte + ".zip"})
            server.upload_file()
            
        except:
            _logger.info("No subió ftp")
            return False
        _logger.info("Subió ftp ok")
        return True

    @api.multi
    def generar_log(self, datos_log):
        self.ensure_one()
        self.env["motgama.generareporte.log"].create(datos_log)
        _logger.info("Log de generación de reporte guardado")
        return

class GeneradorReportesLog(models.Model):
    _name = 'motgama.generareporte.log'
    _decription = 'Log de generación de reportes'

    reporte_recaudo_ok = fields.Boolean(string="Reporte de recaudos generado")
    reporte_ventas_ok = fields.Boolean(string="Reporte de ventas generado")
    reporte_consumos_ok = fields.Boolean(string="Reporte de consumos generado")
    interfaz_contable_ok = fields.Boolean(string="Interfaz contable generada")
    archivo_zip_ok = fields.Boolean(string="Archivo zip generado")
    enviar_correo_ok = fields.Boolean(string="Correo enviado")
    subir_ftp_ok = fields.Boolean(string="Archivo zip subido a ftp")

    codigo_accion_automatica = fields.Integer(string="Código de acción automática")
    nombre_reporte = fields.Char(string="Nombre del reporte")
    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
