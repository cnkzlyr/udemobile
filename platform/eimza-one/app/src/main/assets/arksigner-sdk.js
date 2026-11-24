////////////////////////////////////////////////////////////////////////////////
//
//  ArkSignerJS v2.2.3
//
//  - Different signature algorithms are supported
//
////////////////////////////////////////////////////////////////////////////////


/////////////////////////////////////////////////////////////////////
//  Utilities
/////////////////////////////////////////////////////////////////////


PWSigner.prototype.cypher = function(text, key) {
    var abc = "";

    for (var i = 0; i < text.length; i++) {
        abc += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }

    return Base64.encode(abc);
}

PWSigner.prototype.nonce = function(d, o) {
    if(!d) d = new Date();
    if(!o) o = 0;
    String.prototype.ra=function(i, r) {
        return this.substr(0, i) + r + this.substr(i + r.length);
    }
    var a = '';
    for (var i = 0; i < 28; i++) a += Math.random().toString(36).substr(2, 5);
    var cc = ((((d.getFullYear() * 100 + 
            d.getMonth() + 1) * 100 + 
           d.getDate()) * 100 +
          d.getHours()) * 100 + 
         d.getMinutes()) * 100 + 
        d.getSeconds() + o;

    var t = '' + cc;

    var c = Math.floor(Math.random() * 7) + 2;
    a = c.toString() + a;

    for (var x = 0; x < t.length; x++) a = a.ra((x+1) * c, '' + (9 - parseInt(t.charAt(x))));

    return a;       
}

PWSigner.prototype.isnonce = function(nonce) {
    var d = new Date();

    var uret = function(nonce, date, offset) {
        var cc = ((((date.getFullYear() * 100 + 
                date.getMonth() + 1) * 100 + 
               date.getDate()) * 100 +
              date.getHours()) * 100 + 
             date.getMinutes()) * 100 + 
            date.getSeconds() + offset;
        
        var t = '' + cc;
        var text = '';
        var c = nonce.charAt(0);

        for (var x = 0; x < 14; x++) {
            var digit = nonce.charAt((x+1) * c);
            var reverse = 9 - parseInt(digit);
            text += reverse;
        }

        return (t === text);
    }    

    var valid = false;
    for (var i = 0; i < 10 && !valid; i++) {
        valid = valid || uret(nonce, d, -i);
    }
    return valid;
}

/////////////////////////////////////////////////////////////////////
//  Configuration Parameters
/////////////////////////////////////////////////////////////////////

PWSigner.prototype.algorithms = {
    ALGORITHM_ID_RSA_PKCS1_15   : 1,
    ALGORITHM_RSAPSS            : 2,
    ALGORITHM_ECC               : 3
}

PWSigner.prototype.actions = {
    TASK_INITIALIZE : "initialize",
    TASK_LIST_SMART_CARDS : "listCardTypeAndSlots",
    TASK_LIST_CERTIFICATES : "listSignerCertificatesAsJSON",
    TASK_SIGN_PKCS1 : "signPKCS1Padding1.5",
    TASK_SIGN_CADES_BES : "signCAdES_BES",
    TASK_SIGN_CADES_BES_DIGEST : "signCAdES_BES_Digest",
    TASK_SIGN_XADES_BES_ENVELOPING : "signXaDES_BES_Enveloping",
    TASK_SIGN_XADES_BES_ENVELOPED : "signXaDES_BES_Enveloped",
    TASK_LIST_TCKK_READERS : "listTCKKReaders",
    TASK_RETRIEVE_TCKK_CERTIFICATE : "retrieveTCKKCertificate",
    TASK_SIGN_WITH_TCKK_CERTIFICATE : "sign_with_TCKK_Certificate",
    TASK_SIGN_RSA_WITH_TCKK_CERTIFICATE : "sign_RSA_with_TCKK_Certificate",
    TASK_SIGN_RSA_PSS_WITH_TCKK_CERTIFICATE_v1 : "signRSA_PSS",
    TASK_SIGN_RSA_PSS_WITH_TCKK_CERTIFICATE : "signRSA_PSS_WithTCKKCertificate"
}

PWSigner.prototype.codes = {
    RESPONSE_SUCCESSFUL : 0,
    ERROR_BROWSER_NOT_SUPPORTED_PLEASE_REFRESH : 901,           // kritik
    ERROR_NO_CLIENT : 1,                                        // kritik
    ERROR_TASK_TIMEOUT: 61,                                     // kritik

    ERROR_CANNOT_INITIALIZE_SIGNER : 2,                         // kritik
    ERROR_CANNOT_LOAD_LICENSE : 3,                              // kritik
    ERROR_CANNOT_START_PWSIGNER_CLIENT : 4,                     // kritik
    ERROR_INVALID_CERTIFICATE : 5,                              // kritik
    ERROR_INVALID_CERTIFICATE_SERIAL_NUMBER : 6,                // kritik
    ERROR_NO_SIGNING_CERTIFICATE_FOUND : 7,                     // kritik
    ERROR_NO_TERMINAL_FOUND : 8,
    ERROR_NO_TERMINAL_FOR_PROVIDED_SLOT_ID_AND_CARD_TYPE : 9,   // kritik
    ERROR_SIGNER_IS_NOT_INITIALIZED : 10,                       // kritik
    ERROR_SMART_CARD_EXCEPTION : 11,                            // kritik
    ERROR_UNDEFINED_SIGNER_EXCEPTION : 12,                      // kritik

    ERROR_CANNOT_LOAD_POLICY_FILE : 13,                         // kritik

    ERROR_INVALID_CMS_CONTENT_TO_SIGN : 14,
    ERROR_CANNOT_SET_SIGNING_TIME : 15,
    ERROR_CANNOT_LOGIN_TO_THE_SIGNER : 16,
    ERROR_CANNOT_SIGN_CMS_DOCUMENT : 17,
    ERROR_CANNOT_LOGOUT_SIGNER : 18,
    ERROR_CANNOT_VALIDATE_CERTIFICATE : 19,

    ERROR_CERTIFICATE_REVOCATION_CHECK_FAILURE : 21,
    ERROR_CERTIFICATE_SELF_CHECK_FAILURE : 22,
    ERROR_CERTIFICATE_NO_TRUSTED_CERT_FOUND : 23,
    ERROR_CERTIFICATE_PATH_VALIDATION_FAILURE : 24,
    ERROR_CERTIFICATE_NOT_CHECKED : 25,
    ERROR_INVALID_URL: 26,                                      // kritik
    ERROR_NO_DRIVER_FOUND: 28,                                  // kritik
    ERROR_NO_EXTENSION:29,
    ERROR_INVALID_SLOT_ID: 30,

    ERROR_PWSIGNER_CANNOT_LOAD_PKCS11_DRIVER: 31,
    ERROR_CANNOT_OPEN_CERTIFICATE_STORAGE: 32,
    ERROR_CANNOT_RETRIEVE_LIST_OF_CERTIFICATES: 33,
    ERROR_CANNOT_PARSE_CERTIFICATE_INFORMATION: 34,
    ERROR_CANNOT_CLOSE_CERTIFICATE_STORAGE: 35,

    ERROR_INVALID_LICENSE_FORMAT: 36,
    ERROR_CANNOT_LOAD_DRIVER: 37,

    ERROR_INVALID_PIN: 27,                                      // kritik
    ERROR_PIN_LOCKED: 38,                                       // kritik
    ERROR_PIN_EXPIRED: 39,                                      // kritik
    ERROR_CANNOT_LOGIN_TO_SMARTCARD: 40,                        // kritik

    ERROR_INVALID_DIGEST: 41,                                   // kritik
    ERROR_NO_PUBLIC_KEY_FOUND: 42,
    ERROR_UNDEFINED_ACTION: 43,
    ERROR_NO_PRIVATE_KEY_FOUND_CORRESPONDING_TO_PUBLIC_KEY: 44,

    ERROR_INVALID_XML_FORMAT: 51,
    ERROR_INVALID_XML_SIGNATURE_TARGET: 52,
    ERROR_INVALID_SIGNATURE_STRUCTURE: 53,

    ERROR_INVALID_NONCE: 62,                                    // kritik

    ERROR_NOT_BROWSER_CHROME : 900,                             // kritik
    ERROR_DISCONNECT: 1001,                                     // kritik
    ERROR_UNDEFINED : 1000                                      // kritik
};

PWSigner.prototype.criticalErrorCodes = [
    PWSigner.prototype.codes.ERROR_NO_CLIENT,
    PWSigner.prototype.codes.ERROR_CANNOT_INITIALIZE_SIGNER,
    PWSigner.prototype.codes.ERROR_CANNOT_LOAD_LICENSE,
    PWSigner.prototype.codes.ERROR_CANNOT_START_PWSIGNER_CLIENT,
    PWSigner.prototype.codes.ERROR_INVALID_CERTIFICATE,
    PWSigner.prototype.codes.ERROR_INVALID_CERTIFICATE_SERIAL_NUMBER,
    PWSigner.prototype.codes.ERROR_NO_SIGNING_CERTIFICATE_FOUND,
    PWSigner.prototype.codes.ERROR_NO_TERMINAL_FOR_PROVIDED_SLOT_ID_AND_CARD_TYPE,
    PWSigner.prototype.codes.ERROR_SIGNER_IS_NOT_INITIALIZED,
    PWSigner.prototype.codes.ERROR_SMART_CARD_EXCEPTION,
    PWSigner.prototype.codes.ERROR_UNDEFINED_SIGNER_EXCEPTION,
    PWSigner.prototype.codes.ERROR_CANNOT_LOAD_POLICY_FILE,
    PWSigner.prototype.codes.ERROR_INVALID_URL,
    PWSigner.prototype.codes.ERROR_INVALID_PIN,
    PWSigner.prototype.codes.ERROR_NOT_BROWSER_CHROME,
    PWSigner.prototype.codes.ERROR_DISCONNECT,
    PWSigner.prototype.codes.ERROR_UNDEFINED
];

/////////////////////////////////////////////////////////////////////
//  Actions
/////////////////////////////////////////////////////////////////////

PWSigner.prototype.processResponse = function(text) {
    if (pwsigner.inDebugMode === true) console.log("response text: " + text);
    var jsonObj = (JSON ? JSON.parse(text) : eval(text));
    PWSigner.prototype.processResponseObject(jsonObj);
}

PWSigner.prototype.processResponseObject = function(jsonObj, __text) {
    var text = (__text ? __text : JSON.stringify(jsonObj));
    var responseCode = jsonObj[0].responseCode;
    var transactionUUID = jsonObj[0].transactionUUID;
    var nonce = jsonObj[0].nonce;

    if (pwsigner.inDebugMode === true) console.log("nonce valid", PWSigner.prototype.isnonce(nonce));

    if (!responseCode) responseCode = PWSigner.prototype.codes.ERROR_NO_CLIENT;

    // call the corresponding callback function
    var cb = pwsigner.transactions[transactionUUID];
    if (cb) {
        cb.call(pwsigner, responseCode, text);
        delete pwsigner.transactions[transactionUUID];
        delete pwsigner.lastTransaction;
    } else {
        if (pwsigner.inDebugMode === true) console.log("Warning - No callback for the transaction UUID " + transactionUUID);
        pwsigner.lastTransaction.call(pwsigner, responseCode, text);
        delete pwsigner.lastTransaction;
    }
}

/////////////////////////////////////////////////////////////////////
//  ARKSIGNER METHODS
/////////////////////////////////////////////////////////////////////

    PWSigner.prototype.smartCard = {
        listCertificates : function(callback, config){
            var uuid = pwsigner.registerCallback(callback);
            
            config.action = PWSigner.prototype.actions.TASK_LIST_CERTIFICATES;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            pwsigner.connector.send(jsonStrEncoded);
        },

        listTerminals : function(callback, config){
            var uuid = pwsigner.registerCallback(callback);

            config.action = PWSigner.prototype.actions.TASK_LIST_SMART_CARDS;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();
            
            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            pwsigner.connector.send(jsonStrEncoded);
        },

        signPKCS1Padding1 : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);
          
            if (!config.library) {
                throw 'no library is provided';
            }
            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }
            // certSerialNumber
            if (!config.certSerialNumber) {
                throw 'no certSerialNumber is provided';
            }    
                  
            // pincode
            if (!config.pincode && config.library != "mobile") {
                throw 'no pinCode is provided';
            } 
            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            } 

            config.action = PWSigner.prototype.actions.TASK_SIGN_PKCS1;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.library === "mobile") {
                if (pwsigner.inDebugMode === true) console.log("Extended signing duration for mobile certificate");
                pwsigner.connector.send(jsonStrEncoded, 60);
            } else {
                if (config.timeoutDurationInSec) {
                    pwsigner.connector.send(jsonStrEncoded, config.timeoutDurationInSec);
                } else {
                    pwsigner.connector.send(jsonStrEncoded);
                }
            }
        }
    }

    PWSigner.prototype.tckk = {
        listReaders : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);

            config.action = PWSigner.prototype.actions.TASK_LIST_TCKK_READERS;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            pwsigner.connector.send(jsonStrEncoded);
        },

        retrieveCertificate : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);

            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }

            config.action = PWSigner.prototype.actions.TASK_RETRIEVE_TCKK_CERTIFICATE;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            pwsigner.connector.send(jsonStrEncoded);
        },


        signRSA : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);

            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }

            // pincode
            if (!config.pincode) {
                throw 'no pinCode is provided';
            }
            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            }

            config.action = PWSigner.prototype.actions.TASK_SIGN_RSA_WITH_TCKK_CERTIFICATE;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();
            config.algorithmID = PWSigner.prototype.algorithms.ALGORITHM_ID_RSA_PKCS1_15;

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.timeoutDurationInSec) {
                pwsigner.connector.send(jsonStrEncoded, config.timeoutDurationInSec);
            } else {
                pwsigner.connector.send(jsonStrEncoded);
            }
        },

        signRSA_PSS : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);

            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }

            // pincode
            if (!config.pincode) {
                throw 'no pinCode is provided';
            }
            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            }

            config.action = PWSigner.prototype.actions.TASK_SIGN_RSA_PSS_WITH_TCKK_CERTIFICATE_v1;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();
            config.algorithmID = PWSigner.prototype.algorithms.ALGORITHM_RSAPSS;

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.timeoutDurationInSec) {
                pwsigner.connector.send(jsonStrEncoded, config.timeoutDurationInSec);
            } else {
                pwsigner.connector.send(jsonStrEncoded);
            }
        }
    }

    /**
     *   Contains CaDES methods for signing and verification
     */
    PWSigner.prototype.cades = {

        counterSign: function(callback, config) {

        },

        /**
         *  Callback parameter contains
         *  
         *  library:    Refers to the card type
         *  slotId:     ID of the slot the certificate is on
         *  certSerialNumber:
         */
        sign : function(callback, config) {
            // config kontrol  
            // zorunlu alanlar var m   yok mu
            // library
            var uuid = pwsigner.registerCallback(callback);
            
            if (!config.library) {
                throw 'no library is provided';
            }
            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }
            // certSerialNumber
            if (!config.certSerialNumber) {
                throw 'no certSerialNumber is provided';
            }    
                  
            // pincode
            if (!config.pincode && config.library != "mobile") {
                throw 'no pinCode is provided';
            } 
            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            } 

            config.action = PWSigner.prototype.actions.TASK_SIGN_CADES_BES;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();
            
            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.library === "mobile") {
                if (pwsigner.inDebugMode === true) console.log("Extended signing duration for mobile certificate");
                pwsigner.connector.send(jsonStrEncoded, 60);
            } else {
                pwsigner.connector.send(jsonStrEncoded);
            }
        }, // end of sign

        signDigest: function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);
          
            if (!config.library) {
                throw 'no library is provided';
            }
            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }
            // certSerialNumber
            if (!config.certSerialNumber) {
                throw 'no certSerialNumber is provided';
            }    
                  
            // pincode
            if (!config.pincode && config.library != "mobile") {
                throw 'no pinCode is provided';
            } 

            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            } 

            config.action = PWSigner.prototype.actions.TASK_SIGN_CADES_BES_DIGEST;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.library === "mobile") {
                if (pwsigner.inDebugMode === true) console.log("Extended signing duration for mobile certificate");
                pwsigner.connector.send(jsonStrEncoded, 60);
            } else {
                if (config.timeoutDurationInSec) {
                    pwsigner.connector.send(jsonStrEncoded, config.timeoutDurationInSec);
                } else {
                    pwsigner.connector.send(jsonStrEncoded);
                }
            }
        } // end of sign digest
    }

    PWSigner.prototype.xades = {
        signEnveloping : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);
            
            // config kontrol  
            // zorunlu alanlar var m   yok mu
            // library
          
            if (!config.library) {
                throw 'no library is provided';
            }
            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }
            // certSerialNumber
            if (!config.certSerialNumber) {
                throw 'no certSerialNumber is provided';
            }    
                  
            // pincode
            if (!config.pincode) {
                throw 'no pinCode is provided';
            } 
            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            } 

            config.action = PWSigner.prototype.actions.TASK_SIGN_XADES_BES_ENVELOPING;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.timeoutDurationInSec) {
                pwsigner.connector.send(jsonStrEncoded, config.timeoutDurationInSec);
            } else {
                pwsigner.connector.send(jsonStrEncoded);
            }
        }, // end of enveloping

        signEnveloped : function(callback, config) {
            var uuid = pwsigner.registerCallback(callback);
            
            // config kontrol  
            // zorunlu alanlar var m   yok mu
            // library
          
            if (!config.library) {
                throw 'no library is provided';
            }
            // slotId
            if (!config.slotId) {
                throw 'no slotId is provided';
            }
            // certSerialNumber
            if (!config.certSerialNumber) {
                throw 'no certSerialNumber is provided';
            }    
                  
            // pincode
            if (!config.pincode) {
                throw 'no pinCode is provided';
            } 
            // dataBase64
            if (!config.dataBase64) {
                throw 'no dataBase64 is provided';
            } 

            config.action = PWSigner.prototype.actions.TASK_SIGN_XADES_BES_ENVELOPED;
            config.licenseKey = pwsigner.licenseKey;
            config.usedUrl = window.location.href;
            config.transactionUUID = uuid;
            config.nonce = PWSigner.prototype.nonce();

            var jsonStr = JSON.stringify(config);
            var jsonStrEncoded = Base64.encode(jsonStr);

            if (config.timeoutDurationInSec) {
                pwsigner.connector.send(jsonStrEncoded, config.timeoutDurationInSec);
            } else {
                pwsigner.connector.send(jsonStrEncoded);
            }
        } // end of signEnveloped
    }
