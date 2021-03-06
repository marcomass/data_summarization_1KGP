from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Connection
from sqlalchemy.sql.expression import Selectable, func
from typing import Optional, List, Union
from data_sources.io_parameters import *
from data_sources.annot_interface import AnnotInterface
import database.database as database
import database.db_utils as utils
from threading import RLock
from loguru import logger

table_name = 'hg19_gencode_v19_red'
table_schema = 'rr'
initializing_lock = RLock()
ann_table: Optional[Table] = None
db_meta: MetaData


class GencodeV19HG19(AnnotInterface):

    log_sql_statements: bool = True
    # MAP ATTRIBUTE NAMES TO TABLE COLUMN NAMES
    col_map = {
        Vocabulary.CHROM: 'chrom',
        Vocabulary.START: 'start',
        Vocabulary.STOP: 'stop',
        Vocabulary.STRAND: 'strand',
        Vocabulary.GENE_NAME: 'gene_name',
        Vocabulary.GENE_TYPE: 'gene_type',
        Vocabulary.GENE_ID: 'gene_id'
    }

    def __init__(self):
        self.connection: Optional[Connection] = None
        self.init_singleton_table()

    def annotate(self, connection: Connection, genomic_interval: GenomicInterval, attrs: Optional[List[Vocabulary]]) -> Selectable:
        """
        :param connection:
        :param genomic_interval:
        :param attrs: a list of Vocabulary elements indicating the kind of annotation attributes desired
        :return: a statement that when executed returns the annotation data requested.
        """
        self.connection = connection
        columns_of_interest = [ann_table.c[self.col_map[attr]].label(attr.name) for attr in attrs]
        stmt = \
            select(columns_of_interest) \
            .where((ann_table.c.start <= genomic_interval.stop) &
                   (ann_table.c.stop >= genomic_interval.start) &
                   (ann_table.c.chrom == genomic_interval.chrom))
        if genomic_interval.strand is not None and genomic_interval.strand != 0:
            stmt = stmt.where(ann_table.c.strand == genomic_interval.strand)
        if self.log_sql_statements:
            utils.show_stmt(connection, stmt, logger.debug, 'GENCODE_V19_HG19: ANNOTATE REGION/VARIANT')
        return stmt

    def find_gene_region(self, connection: Connection, gene: Gene, output_attrs: List[Vocabulary]):
        self.connection = connection
        select_columns = [ann_table.c[self.col_map[att]].label(att.name) for att in output_attrs]
        stmt = select(select_columns)\
            .where(ann_table.c.gene_name == gene.name)
        if gene.type_ is not None:
            stmt = stmt.where(ann_table.c.gene_type == gene.type_)
        if gene.id_ is not None:
            stmt = stmt.where(ann_table.c.gene_id == gene.id_)
        if self.log_sql_statements:
            utils.show_stmt(connection, stmt, logger.debug, 'GENCODE_V19_HG19: FIND GENE')
        return stmt

    def values_of_attribute(self, connection, attribute: Vocabulary) -> Union[List, Notice]:
        distinct_values = {
            self.col_map[Vocabulary.GENE_TYPE]: [
                'sense_overlapping',
                'Mt_tRNA',
                'processed_transcript',
                'TR_V_pseudogene',
                'misc_RNA',
                'snoRNA',
                'protein_coding',
                'TR_J_gene',
                'IG_J_gene',
                'rRNA',
                'polymorphic_pseudogene',
                'antisense',
                'miRNA',
                'IG_D_gene',
                'snRNA',
                'IG_V_gene',
                'TR_J_pseudogene',
                'Mt_rRNA',
                '3prime_overlapping_ncrna',
                'lincRNA',
                'IG_J_pseudogene',
                'TR_V_gene',
                'sense_intronic',
                'IG_C_pseudogene',
                'IG_C_gene',
                'TR_C_gene',
                'pseudogene',
                'IG_V_pseudogene',
                'TR_D_gene'
                ]
        }
        return distinct_values.get(self.col_map.get(attribute))

    @staticmethod
    def init_singleton_table():
        global initializing_lock
        global ann_table
        global db_meta
        if ann_table is None:
            # in a racing condition the lock can be acquired as first or as second.
            initializing_lock.acquire(True)
            # if I'm second, the table has been already initialized, so release the lock and exit. If I'm first proceed
            if ann_table is None:
                logger.debug('initializing table for class gencode_v19_hg19')
                db_meta = MetaData()
                connection = None
                try:
                    connection = database.check_and_get_connection()
                    ann_table = Table(table_name,
                                      db_meta,
                                      autoload=True,
                                      autoload_with=connection,
                                      schema=table_schema)
                finally:
                    initializing_lock.release()
                    if connection is not None:
                        connection.close()
            else:
                initializing_lock.release()


