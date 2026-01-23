import logging
import sys
from datetime import datetime

def setup_logger():
    # Configurar el logger
    logger = logging.getLogger("AutoBlog")
    logger.setLevel(logging.INFO)
    
    # Formato del log
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Salida a consola
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # Salida a archivo (persistencia)
    fh = logging.FileHandler('autoblog.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

# Inicializar logger global
logger = setup_logger()