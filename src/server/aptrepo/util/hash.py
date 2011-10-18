from django.conf import settings
import pyme.core
import pyme.constants.sig

# constants
HASH_BLOCK_MULTIPLE = 128

def hash_file_by_fh(hashfunc, fh, from_start=True):
    """
    Returns a hexadecimal hash digest for a file using a hashlib algorithm
    """
    if from_start:
        fh.seek(0)
    
    for chunk in iter(lambda: fh.read(HASH_BLOCK_MULTIPLE * hashfunc.block_size), ''):
        hashfunc.update(chunk)
        
    return hashfunc.hexdigest()

def hash_file(hashfunc, filename):
    """
    Returns a hexadecimal hash digest for a file using a hashlib algorithm
    """
    with open(filename, 'rb') as fh:
        return hash_file_by_fh(hashfunc, fh)

def hash_string(hashfunc, data_string):
    """
    Returns a hexadecimal hash digest for a string
    """
    hashfunc.update(data_string)
    return hashfunc.hexdigest()


class GPGSigner:

    def __init__(self, secret_key_filename=None):
        """
        secret_key_filename - (optional) path to secret key, defaults to settings.GPG_SECRET_KEY 
        """
        if not secret_key_filename:
            secret_key_filename=settings.GPG_SECRET_KEY

        self.gpg_context = pyme.core.Context()
        self.gpg_context.set_armor(1)
        self.gpg_context.signers_clear()
        private_key_data = pyme.core.Data(file=secret_key_filename)
        self.gpg_context.op_import(private_key_data)
        gpgme_result = self.gpg_context.op_import_result()
        pyme.errors.errorcheck(gpgme_result.imports[0].result)
        
    def get_public_key(self):
        """
        Returns the GPG public key as a string
        """
        public_key_data = pyme.core.Data()
        self.gpg_context.op_export(None, 0, public_key_data)
        public_key_data.seek(0, 0)
        return public_key_data.read()
        
    def sign_data(self, data_to_sign):
        """
        Signs arbitrary string data
        
        data_to_sign - string data
        
        Returns the signature as a string
        """
        plain_data = pyme.core.Data(data_to_sign)
        signature_data = pyme.core.Data()
        modes = pyme.constants.sig.mode
        sign_result = self.gpg_context.op_sign(plain_data, 
                                               signature_data,
                                               modes.DETACH)
        pyme.errors.errorcheck(sign_result)
        signature_data.seek(0, 0)
        return signature_data.read()
