{
    'name':'Llave',
    'version':'12.0.1.0',
    'summary':'Validación para el motel',
    'author':'DevOn',
    'depends':['base','motgama'],
    'installable':True,
    'application':True,
    'data':[
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/parametros.xml',
        'data/automatizacion.xml',
        'views/parametros.xml',
        'views/log.xml',
        'views/rollback.xml',
        'views/validacion.xml',
        'views/ajustes.xml',
        'views/ftp.xml',
        'views/invoice.xml',
        'views/menu.xml'
    ]
}