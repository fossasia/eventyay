"""
Copyright (c) 2017-2023 Raphael Michel and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import datetime
import xml.etree.ElementTree as ET

from .shared import SepaPaymentInitn
from .utils import ADDRESS_MAPPING, int_to_decimal_str, make_id


class SepaTransfer(SepaPaymentInitn):
    """
    This class creates a Sepa transfer XML File.
    """
    root_el = "CstmrCdtTrfInitn"

    def __init__(self, config, schema="pain.001.001.03", clean=True):
        super().__init__(config, schema, clean)

    def check_config(self, config):
        """
        Check the config file for required fields and validity.
        @param config: The config dict.
        @return: True if valid, error string if invalid paramaters where
        encountered.
        """
        validation = ""
        required = ["name", "currency", "IBAN"]

        for config_item in required:
            if config_item not in config:
                validation += config_item.upper() + "_MISSING "

        if not validation:
            return True
        else:
            raise Exception("Config file did not validate. " + validation)

    def check_payment(self, payment):
        """
        Check the payment for required fields and validity.
        @param payment: The payment dict
        @return: True if valid, error string if invalid paramaters where
        encountered.
        """
        validation = ""
        required = ["name", "IBAN", "amount", "description", "execution_date"]

        for config_item in required:
            if config_item not in payment:
                validation += config_item.upper() + "_MISSING "

        if not isinstance(payment['amount'], int):
            validation += "AMOUNT_NOT_INTEGER "

        if 'execution_date' in payment:
            if not isinstance(payment['execution_date'], datetime.date):
                validation += "EXECUTION_DATE_INVALID_OR_NOT_DATETIME_INSTANCE"
            payment['execution_date'] = payment['execution_date'].isoformat()

        if validation == "":
            return True
        else:
            raise Exception('Payment did not validate: ' + validation)

    def add_payment(self, payment):
        """
        Function to add payments
        @param payment: The payment dict
        @raise exception: when payment is invalid
        """
        # Validate the payment
        self.check_payment(payment)

        if self.clean:
            from text_unidecode import unidecode

            payment['name'] = unidecode(payment['name'])[:70]
            payment['description'] = unidecode(payment['description'])[:140]

        # Get the CstmrDrctDbtInitnNode
        if not self._config['batch']:
            # Start building the non batch payment
            PmtInf_nodes = self._create_PmtInf_node()
            PmtInf_nodes['PmtInfIdNode'].text = make_id(self._config['name'])
            PmtInf_nodes['PmtMtdNode'].text = "TRF"
            PmtInf_nodes['BtchBookgNode'].text = "false"
            PmtInf_nodes['NbOfTxsNode'].text = "1"
            PmtInf_nodes['CtrlSumNode'].text = int_to_decimal_str(
                payment['amount']
            )
            if not self._config.get('domestic', False):
                PmtInf_nodes['Cd_SvcLvl_Node'].text = "SEPA"
            if 'execution_date' in payment:
                if self.schema == "pain.001.001.03":
                    PmtInf_nodes['ReqdExctnDtNode'].text = payment['execution_date']
                else:
                    PmtInf_nodes['ReqdExctnDt_Dt_Node'].text = payment['execution_date']
            else:
                del PmtInf_nodes['ReqdExctnDtNode']

            PmtInf_nodes['Nm_Dbtr_Node'].text = self._config['name']
            if payment.get('address', {}):
                for d, n in ADDRESS_MAPPING:
                    if self._config['address'].get(d):
                        n = ET.Element(n)
                        n.text = self._config['address'][d]
                        PmtInf_nodes['PstlAdr_Dbtr_Node'].append(n)
                for line in self._config.get('lines', []):
                    n = ET.Element('AdrLine')
                    n.text = line
                    PmtInf_nodes['PstlAdr_Dbtr_Node'].append(n)

            PmtInf_nodes['IBAN_DbtrAcct_Node'].text = self._config['IBAN']
            if 'BIC' in self._config:
                PmtInf_nodes['BIC_DbtrAgt_Node'].text = self._config['BIC']

            PmtInf_nodes['ChrgBrNode'].text = "SLEV"

        if 'BIC' in payment:
            bic = True
        else:
            bic = False

        TX_nodes = self._create_TX_node(bic)
        TX_nodes['InstdAmtNode'].set("Ccy", payment.get('currency', self._config['currency']))
        TX_nodes['InstdAmtNode'].text = int_to_decimal_str(payment['amount'])
        TX_nodes['EndToEnd_PmtId_Node'].text = payment.get('endtoend_id', 'NOTPROVIDED')
        if bic:
            TX_nodes['BIC_CdtrAgt_Node'].text = payment['BIC']
        TX_nodes['Nm_Cdtr_Node'].text = payment['name']
        if payment.get('address', {}):
            for d, n in ADDRESS_MAPPING:
                if payment['address'].get(d):
                    n = ET.Element(n)
                    n.text = payment['address'][d]
                    TX_nodes['PstlAdr_Cdtr_Node'].append(n)
            for line in payment['address'].get('lines', []):
                n = ET.Element('AdrLine')
                n.text = line
                TX_nodes['PstlAdr_Cdtr_Node'].append(n)

        TX_nodes['IBAN_CdtrAcct_Node'].text = payment['IBAN']
        TX_nodes['UstrdNode'].text = payment['description']

        if self._config['batch']:
            self._add_batch(TX_nodes, payment)
        else:
            self._add_non_batch(TX_nodes, PmtInf_nodes)

    def _create_header(self):
        """
        Function to create the GroupHeader (GrpHdr) in the
        CstmrCdtTrfInitn Node
        """
        # Retrieve the node to which we will append the group header.
        CstmrCdtTrfInitn_node = self._xml.find('CstmrCdtTrfInitn')

        # Create the header nodes.
        GrpHdr_node = ET.Element("GrpHdr")
        MsgId_node = ET.Element("MsgId")
        CreDtTm_node = ET.Element("CreDtTm")
        NbOfTxs_node = ET.Element("NbOfTxs")
        CtrlSum_node = ET.Element("CtrlSum")
        InitgPty_node = ET.Element("InitgPty")
        Nm_node = ET.Element("Nm")

        # Add data to some header nodes.
        MsgId_node.text = self.msg_id
        CreDtTm_node.text = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        Nm_node.text = self._config['name']

        # Append the nodes
        InitgPty_node.append(Nm_node)
        GrpHdr_node.append(MsgId_node)
        GrpHdr_node.append(CreDtTm_node)
        GrpHdr_node.append(NbOfTxs_node)
        GrpHdr_node.append(CtrlSum_node)
        GrpHdr_node.append(InitgPty_node)

        # Append the header to its parent
        CstmrCdtTrfInitn_node.append(GrpHdr_node)

    def _create_PmtInf_node(self):
        """
        Method to create the blank payment information nodes as a dict.
        """
        ED = dict()  # ED is element dict
        ED['PmtInfNode'] = ET.Element("PmtInf")
        ED['PmtInfIdNode'] = ET.Element("PmtInfId")
        ED['PmtMtdNode'] = ET.Element("PmtMtd")
        ED['BtchBookgNode'] = ET.Element("BtchBookg")
        ED['NbOfTxsNode'] = ET.Element("NbOfTxs")
        ED['CtrlSumNode'] = ET.Element("CtrlSum")
        ED['PmtTpInfNode'] = ET.Element("PmtTpInf")
        if not self._config.get('domestic', False):
            ED['SvcLvlNode'] = ET.Element("SvcLvl")
            ED['Cd_SvcLvl_Node'] = ET.Element("Cd")
        ED['ReqdExctnDtNode'] = ET.Element("ReqdExctnDt")
        ED['ReqdExctnDt_Dt_Node'] = ET.Element("Dt")

        ED['DbtrNode'] = ET.Element("Dbtr")
        ED['Nm_Dbtr_Node'] = ET.Element("Nm")
        ED['PstlAdr_Dbtr_Node'] = ET.Element("PstlAdr")
        ED['DbtrAcctNode'] = ET.Element("DbtrAcct")
        ED['Id_DbtrAcct_Node'] = ET.Element("Id")
        ED['IBAN_DbtrAcct_Node'] = ET.Element("IBAN")
        ED['DbtrAgtNode'] = ET.Element("DbtrAgt")
        ED['FinInstnId_DbtrAgt_Node'] = ET.Element("FinInstnId")
        if 'BIC' in self._config:
            if self.schema != 'pain.001.001.03':
                ED['BIC_DbtrAgt_Node'] = ET.Element("BICFI")
            else:
                ED['BIC_DbtrAgt_Node'] = ET.Element("BIC")
        ED['ChrgBrNode'] = ET.Element("ChrgBr")
        return ED

    def _create_TX_node(self, bic=True):
        """
        Method to create the blank transaction nodes as a dict. If bic is True,
        the BIC node will also be created.
        """
        ED = dict()
        ED['CdtTrfTxInfNode'] = ET.Element("CdtTrfTxInf")
        ED['PmtIdNode'] = ET.Element("PmtId")
        ED['EndToEnd_PmtId_Node'] = ET.Element("EndToEndId")
        ED['AmtNode'] = ET.Element("Amt")
        ED['InstdAmtNode'] = ET.Element("InstdAmt")
        ED['CdtrNode'] = ET.Element("Cdtr")
        ED['Nm_Cdtr_Node'] = ET.Element("Nm")
        ED['PstlAdr_Cdtr_Node'] = ET.Element("PstlAdr")
        ED['CdtrAgtNode'] = ET.Element("CdtrAgt")
        ED['FinInstnId_CdtrAgt_Node'] = ET.Element("FinInstnId")
        if bic:
            if self.schema != 'pain.001.001.03':
                ED['BIC_CdtrAgt_Node'] = ET.Element("BICFI")
            else:
                ED['BIC_CdtrAgt_Node'] = ET.Element("BIC")
        ED['CdtrAcctNode'] = ET.Element("CdtrAcct")
        ED['Id_CdtrAcct_Node'] = ET.Element("Id")
        ED['IBAN_CdtrAcct_Node'] = ET.Element("IBAN")
        ED['RmtInfNode'] = ET.Element("RmtInf")
        ED['UstrdNode'] = ET.Element("Ustrd")
        return ED

    def _add_non_batch(self, TX_nodes, PmtInf_nodes):
        """
        Method to add a transaction as non batch, will fold the transaction
        together with the payment info node and append to the main xml.
        """
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['PmtInfIdNode'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['PmtMtdNode'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['BtchBookgNode'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['NbOfTxsNode'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['CtrlSumNode'])

        if not self._config.get('domestic', False):
            PmtInf_nodes['SvcLvlNode'].append(PmtInf_nodes['Cd_SvcLvl_Node'])
            PmtInf_nodes['PmtTpInfNode'].append(PmtInf_nodes['SvcLvlNode'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['PmtTpInfNode'])
        if 'ReqdExctnDtNode' in PmtInf_nodes:
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['ReqdExctnDtNode'])
            if self.schema != "pain.001.001.03":
                PmtInf_nodes['ReqdExctnDtNode'].append(PmtInf_nodes['ReqdExctnDt_Dt_Node'])

        PmtInf_nodes['DbtrNode'].append(PmtInf_nodes['Nm_Dbtr_Node'])
        if "PstlAdr_Dbtr_Node" in TX_nodes:
            PmtInf_nodes['DbtrNode'].append(TX_nodes['PstlAdr_Dbtr_Node'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['DbtrNode'])

        PmtInf_nodes['Id_DbtrAcct_Node'].append(PmtInf_nodes['IBAN_DbtrAcct_Node'])
        PmtInf_nodes['DbtrAcctNode'].append(PmtInf_nodes['Id_DbtrAcct_Node'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['DbtrAcctNode'])

        if 'BIC' in self._config:
            PmtInf_nodes['FinInstnId_DbtrAgt_Node'].append(PmtInf_nodes['BIC_DbtrAgt_Node'])
        PmtInf_nodes['DbtrAgtNode'].append(PmtInf_nodes['FinInstnId_DbtrAgt_Node'])
        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['DbtrAgtNode'])

        PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['ChrgBrNode'])

        TX_nodes['PmtIdNode'].append(TX_nodes['EndToEnd_PmtId_Node'])
        TX_nodes['AmtNode'].append(TX_nodes['InstdAmtNode'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['PmtIdNode'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['AmtNode'])

        if 'BIC_CdtrAgt_Node' in TX_nodes and TX_nodes['BIC_CdtrAgt_Node'].text is not None:
            TX_nodes['FinInstnId_CdtrAgt_Node'].append(
                TX_nodes['BIC_CdtrAgt_Node'])
            TX_nodes['CdtrAgtNode'].append(TX_nodes['FinInstnId_CdtrAgt_Node'])
            TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['CdtrAgtNode'])

        TX_nodes['CdtrNode'].append(TX_nodes['Nm_Cdtr_Node'])
        if len(TX_nodes['PstlAdr_Cdtr_Node']) > 0:
            TX_nodes['CdtrNode'].append(TX_nodes['PstlAdr_Cdtr_Node'])

        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['CdtrNode'])

        TX_nodes['Id_CdtrAcct_Node'].append(TX_nodes['IBAN_CdtrAcct_Node'])
        TX_nodes['CdtrAcctNode'].append(TX_nodes['Id_CdtrAcct_Node'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['CdtrAcctNode'])

        TX_nodes['RmtInfNode'].append(TX_nodes['UstrdNode'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['RmtInfNode'])
        PmtInf_nodes['PmtInfNode'].append(TX_nodes['CdtTrfTxInfNode'])
        CstmrCdtTrfInitn_node = self._xml.find('CstmrCdtTrfInitn')
        CstmrCdtTrfInitn_node.append(PmtInf_nodes['PmtInfNode'])

    def _add_batch(self, TX_nodes, payment):
        """
        Method to add a payment as a batch. The transaction details are already
        present. Will fold the nodes accordingly and the call the
        _add_to_batch_list function to store the batch.
        """
        TX_nodes['PmtIdNode'].append(TX_nodes['EndToEnd_PmtId_Node'])
        TX_nodes['AmtNode'].append(TX_nodes['InstdAmtNode'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['PmtIdNode'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['AmtNode'])

        if 'BIC_CdtrAgt_Node' in TX_nodes and TX_nodes['BIC_CdtrAgt_Node'].text is not None:
            TX_nodes['FinInstnId_CdtrAgt_Node'].append(
                TX_nodes['BIC_CdtrAgt_Node'])
            TX_nodes['CdtrAgtNode'].append(TX_nodes['FinInstnId_CdtrAgt_Node'])
            TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['CdtrAgtNode'])

        TX_nodes['CdtrNode'].append(TX_nodes['Nm_Cdtr_Node'])
        if len(TX_nodes['PstlAdr_Cdtr_Node']) > 0:
            TX_nodes['CdtrNode'].append(TX_nodes['PstlAdr_Cdtr_Node'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['CdtrNode'])

        TX_nodes['Id_CdtrAcct_Node'].append(TX_nodes['IBAN_CdtrAcct_Node'])
        TX_nodes['CdtrAcctNode'].append(TX_nodes['Id_CdtrAcct_Node'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['CdtrAcctNode'])

        TX_nodes['RmtInfNode'].append(TX_nodes['UstrdNode'])
        TX_nodes['CdtTrfTxInfNode'].append(TX_nodes['RmtInfNode'])
        self._add_to_batch_list(TX_nodes, payment)

    def _add_to_batch_list(self, TX, payment):
        """
        Method to add a transaction to the batch list. The correct batch will
        be determined by the payment dict and the batch will be created if
        not existant. This will also add the payment amount to the respective
        batch total.
        """
        batch_key = payment.get('execution_date', None)
        if batch_key in self._batches.keys():
            self._batches[batch_key].append(TX['CdtTrfTxInfNode'])
        else:
            self._batches[batch_key] = []
            self._batches[batch_key].append(TX['CdtTrfTxInfNode'])

        if batch_key in self._batch_totals:
            self._batch_totals[batch_key] += payment['amount']
        else:
            self._batch_totals[batch_key] = payment['amount']

    def _finalize_batch(self):
        """
        Method to finalize the batch, this will iterate over the _batches dict
        and create a PmtInf node for each batch. The correct information (from
        the batch_key and batch_totals) will be inserted and the batch
        transaction nodes will be folded. Finally, the batches will be added to
        the main XML.
        """
        for batch_meta, batch_nodes in self._batches.items():
            PmtInf_nodes = self._create_PmtInf_node()
            PmtInf_nodes['PmtInfIdNode'].text = make_id(self._config['name'])
            PmtInf_nodes['PmtMtdNode'].text = "TRF"
            PmtInf_nodes['BtchBookgNode'].text = "true"
            if not self._config.get('domestic', False):
                PmtInf_nodes['Cd_SvcLvl_Node'].text = "SEPA"

            if batch_meta:
                if self.schema == "pain.001.001.03":
                    PmtInf_nodes['ReqdExctnDtNode'].text = batch_meta
                else:
                    PmtInf_nodes['ReqdExctnDt_Dt_Node'].text = batch_meta
            else:
                del PmtInf_nodes['ReqdExctnDtNode']
            PmtInf_nodes['Nm_Dbtr_Node'].text = self._config['name']
            if self._config.get('address', {}):
                for d, n in ADDRESS_MAPPING:
                    if self._config['address'].get(d):
                        n = ET.Element(n)
                        n.text = self._config['address'][d]
                        PmtInf_nodes['PstlAdr_Dbtr_Node'].append(n)
                for line in self._config['address'].get('lines', []):
                    n = ET.Element('AdrLine')
                    n.text = line
                    PmtInf_nodes['PstlAdr_Dbtr_Node'].append(n)
            PmtInf_nodes['IBAN_DbtrAcct_Node'].text = self._config['IBAN']

            if 'BIC' in self._config:
                PmtInf_nodes['BIC_DbtrAgt_Node'].text = self._config['BIC']

            PmtInf_nodes['ChrgBrNode'].text = "SLEV"

            PmtInf_nodes['NbOfTxsNode'].text = str(len(batch_nodes))
            PmtInf_nodes['CtrlSumNode'].text = int_to_decimal_str(self._batch_totals[batch_meta])

            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['PmtInfIdNode'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['PmtMtdNode'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['BtchBookgNode'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['NbOfTxsNode'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['CtrlSumNode'])

            if not self._config.get('domestic', False):
                PmtInf_nodes['SvcLvlNode'].append(PmtInf_nodes['Cd_SvcLvl_Node'])
                PmtInf_nodes['PmtTpInfNode'].append(PmtInf_nodes['SvcLvlNode'])
                PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['PmtTpInfNode'])
            if 'ReqdExctnDtNode' in PmtInf_nodes:
                PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['ReqdExctnDtNode'])
                if self.schema != "pain.001.001.03":
                    PmtInf_nodes['ReqdExctnDtNode'].append(PmtInf_nodes['ReqdExctnDt_Dt_Node'])

            PmtInf_nodes['DbtrNode'].append(PmtInf_nodes['Nm_Dbtr_Node'])
            if len(PmtInf_nodes['PstlAdr_Dbtr_Node']) > 0:
                PmtInf_nodes['DbtrNode'].append(PmtInf_nodes['PstlAdr_Dbtr_Node'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['DbtrNode'])

            PmtInf_nodes['Id_DbtrAcct_Node'].append(PmtInf_nodes['IBAN_DbtrAcct_Node'])
            PmtInf_nodes['DbtrAcctNode'].append(PmtInf_nodes['Id_DbtrAcct_Node'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['DbtrAcctNode'])

            if 'BIC' in self._config:
                PmtInf_nodes['FinInstnId_DbtrAgt_Node'].append(PmtInf_nodes['BIC_DbtrAgt_Node'])
            PmtInf_nodes['DbtrAgtNode'].append(PmtInf_nodes['FinInstnId_DbtrAgt_Node'])
            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['DbtrAgtNode'])

            PmtInf_nodes['PmtInfNode'].append(PmtInf_nodes['ChrgBrNode'])

            for txnode in batch_nodes:
                PmtInf_nodes['PmtInfNode'].append(txnode)

            CstmrCdtTrfInitn_node = self._xml.find('CstmrCdtTrfInitn')
            CstmrCdtTrfInitn_node.append(PmtInf_nodes['PmtInfNode'])
