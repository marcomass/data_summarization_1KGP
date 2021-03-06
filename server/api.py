import connexion
from data_sources.io_parameters import *
from flask import redirect
import data_sources.coordinator as coordinator
from typing import Optional, List
from prettytable import PrettyTable
from loguru import logger


class ReqParamKeys:
    """
    This class contains the macro categories of the
    """
    META = 'having_meta'
    GENDER = 'gender'
    HEALTH_STATUS = 'health_status'
    DNA_SOURCE = 'dna_source'
    ASSEMBLY = 'assembly'
    POPULATION_CODE = 'population'
    SUPER_POPULATION_CODE = 'super_population'

    VARIANTS = 'having_variants'
    WITH_VARIANTS = 'with'
    WITH_VARS_ON_SAME_CHROM_COPY = 'on_same_chrom_copy'
    WITH_VARS_ON_DIFF_CHROM_COPY = 'on_diff_chrom_copy'
    WITH_VARS_IN = 'in'

    OUTPUT = 'filter_output'
    OUT_MIN_FREQUENCY = 'min_frequency'
    OUT_MAX_FREQUENCY = 'max_frequency'
    OUT_LIMIT = 'limit'

    BY_ATTRIBUTES = 'distribute_by'

    TARGET_VARIANT = 'target_variant'

    CHROM = 'chrom'
    START = 'start'
    STOP = 'stop'
    STRAND = 'strand'
    VAR_ID = 'id'
    REF = 'ref'
    ALT = 'alt'

    GENE_NAME = 'name'
    GENE_TYPE = 'type'
    GENE_TYPE_2 = 'gene_type'
    GENE_ID = 'ensemble_id'


connexion_app = connexion.App(__name__, specification_dir='./')  # internally it starts flask
flask_app = connexion_app.app
base_path = '/popstudy/'
api_doc_relative_path = 'api/ui/'


def run():
    # do this only after the declaration of the api endpoint handlers
    connexion_app.add_api('api_definition.yml')  # <- yml located inside the specification dir
    connexion_app.run(host='localhost',
                      port=51992,
                      debug=True,
                      threaded=True,        # this is True by default of Flask - I just wanna to make it explicit
                      use_reloader=False)   # prevents module main from starting twice, but disables auto-reload upon changes detected


# ###########################       ENDPOINTS
def donor_distribution(body):
    def go():
        params = prepare_body_parameters(body)
        result = coordinator.donor_distribution(params[2], params[0], params[1])
        return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


def variant_distribution(body):
    def go():
        params = prepare_body_parameters(body)
        result = coordinator.variant_distribution(params[2], params[0], params[1], params[3])
        return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


def most_common_variants(body):
    def go():
        params = prepare_body_parameters(body)
        result = coordinator.most_common_variants(params[0], params[1], params[6], params[5])
        return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


def rarest_variants(body):
    def go():
        params = prepare_body_parameters(body)
        result = coordinator.rarest_variants(params[0], params[1], params[4], params[5])
        return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


def values(attribute):
    def go():
        item = parse_name_to_vocabulary(attribute)
        if item is None:
            return f'Attribute {attribute} is not a valid parameter for this request', 400
        else:
            result = coordinator.values_of_attribute(item)
            return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


def annotate(body):
    with_annotations = [
        Vocabulary.CHROM,
        Vocabulary.START,
        Vocabulary.STOP,
        Vocabulary.STRAND,
        Vocabulary.GENE_NAME,
        Vocabulary.GENE_TYPE
    ]

    def go():
        if body.get(ReqParamKeys.STOP):
            interval = parse_genomic_interval_from_dict(body)
            result = coordinator.annotate_interval(interval, with_annotations)
        else:
            variant = parse_variant_from_dict(body)
            result = coordinator.annotate_variant(variant, with_annotations)
        return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


def variants_in_region(body):
    def go():
        if body.get(ReqParamKeys.STOP):
            interval = parse_genomic_interval_from_dict(body)
            result = coordinator.variants_in_genomic_interval(interval)
        else:
            gene = parse_gene_from_dict(body)
            result = coordinator.variants_in_gene(gene)
        return result if result is not None else service_unavailable_message()
    return try_and_catch(go)


@connexion_app.route(base_path)
def home():
    # redirect to base_path + api_doc_relative_path
    return redirect(api_doc_relative_path)


# ###########################       TRANSFORM INPUT
def prepare_body_parameters(body):
    meta = body.get(ReqParamKeys.META)
    if meta is not None:
        meta = MetadataAttrs(gender=meta.get(ReqParamKeys.GENDER),
                             health_status=meta.get(ReqParamKeys.HEALTH_STATUS),
                             dna_source=meta.get(ReqParamKeys.DNA_SOURCE),
                             assembly=meta.get(ReqParamKeys.ASSEMBLY),
                             population=meta.get(ReqParamKeys.POPULATION_CODE),
                             super_population=meta.get(ReqParamKeys.SUPER_POPULATION_CODE))

    variants = body.get(ReqParamKeys.VARIANTS)
    if variants is not None:
        if variants.get(ReqParamKeys.WITH_VARS_IN) is not None:
            if variants[ReqParamKeys.WITH_VARS_IN].get(ReqParamKeys.STOP):
                interval = parse_genomic_interval_from_dict(variants[ReqParamKeys.WITH_VARS_IN])
                gene = None
            else:
                gene = parse_gene_from_dict(variants[ReqParamKeys.WITH_VARS_IN])
                interval = None
        else:
            interval = None
            gene = None
        variants = RegionAttrs(parse_to_mutation_array(variants.get(ReqParamKeys.WITH_VARIANTS)),
                               parse_to_mutation_array(variants.get(ReqParamKeys.WITH_VARS_ON_SAME_CHROM_COPY)),
                               parse_to_mutation_array(variants.get(ReqParamKeys.WITH_VARS_ON_DIFF_CHROM_COPY)),
                               interval,
                               gene)

    by_attributes = None
    distribute_by = body.get(ReqParamKeys.BY_ATTRIBUTES)
    if distribute_by is not None:
        by_attributes = list()
        # allow only the following parameter names into distribute_by
        for att in [ReqParamKeys.GENDER, ReqParamKeys.HEALTH_STATUS, ReqParamKeys.DNA_SOURCE,
                    ReqParamKeys.POPULATION_CODE, ReqParamKeys.SUPER_POPULATION_CODE]:  # TODO missing mut type
            if att in distribute_by:
                by_attributes.append(parse_name_to_vocabulary(att))

    target_variant = body.get(ReqParamKeys.TARGET_VARIANT)
    if target_variant is not None:
        target_variant = parse_variant_from_dict(target_variant)

    out_limit = None
    out_min_frequency = None
    out_max_frequency = None
    output = body.get(ReqParamKeys.OUTPUT)
    if output is not None:
        out_limit = output.get(ReqParamKeys.OUT_LIMIT)
        out_max_frequency = output.get(ReqParamKeys.OUT_MAX_FREQUENCY)
        out_min_frequency = output.get(ReqParamKeys.OUT_MIN_FREQUENCY)

    return meta, variants, by_attributes, target_variant, out_min_frequency, out_limit, out_max_frequency


def parse_to_mutation_array(dict_array_of_mutations):
    """
    We receive from the user only standard python data structures (generated from the JSON body request parameter).
    We want to convert each dictionary representing a mutation into a Mutation object.
    :param dict_array_of_mutations: the array of dictionary elements, each one representing a mutation.
    :return: an array of Mutation objects.
    """
    if dict_array_of_mutations is None or len(dict_array_of_mutations) == 0:
        return None
    else:
        return [parse_variant_from_dict(a_dict) for a_dict in dict_array_of_mutations]


def parse_variant_from_dict(mutation_dict: dict):
    if mutation_dict.get(ReqParamKeys.VAR_ID) is not None:
        return Mutation(_id=mutation_dict[ReqParamKeys.VAR_ID])
    else:
        return Mutation(mutation_dict.get(ReqParamKeys.CHROM),
                        mutation_dict.get(ReqParamKeys.START),
                        mutation_dict.get(ReqParamKeys.REF),
                        mutation_dict.get(ReqParamKeys.ALT))


def parse_genomic_interval_from_dict(region_dict: dict):
    return GenomicInterval(region_dict.get(ReqParamKeys.CHROM),
                           region_dict.get(ReqParamKeys.START),
                           region_dict.get(ReqParamKeys.STOP),
                           region_dict.get(ReqParamKeys.STRAND))


def parse_gene_from_dict(gene_dict: dict):
    return Gene(gene_dict.get(ReqParamKeys.GENE_NAME),
                gene_dict.get(ReqParamKeys.GENE_TYPE),
                gene_dict.get(ReqParamKeys.GENE_ID))


def parse_name_to_vocabulary(name: str):
    if name == ReqParamKeys.GENDER:
        return Vocabulary.GENDER
    elif name == ReqParamKeys.POPULATION_CODE:
        return Vocabulary.POPULATION
    elif name == ReqParamKeys.SUPER_POPULATION_CODE:
        return Vocabulary.SUPER_POPULATION
    elif name == ReqParamKeys.DNA_SOURCE:
        return Vocabulary.DNA_SOURCE
    elif name == ReqParamKeys.HEALTH_STATUS:
        return Vocabulary.HEALTH_STATUS
    elif name == ReqParamKeys.ASSEMBLY:
        return Vocabulary.ASSEMBLY
    elif name == ReqParamKeys.GENE_TYPE_2:
        return Vocabulary.GENE_TYPE
    else:
        logger.info('name without a match in Vocabulary')
        return None


# ###########################       TRANSFORM OUTPUT
def print_output_table(output_dictionary):
    pretty_table = PrettyTable(output_dictionary['columns'])
    for row in output_dictionary['rows']:
        pretty_table.add_row(row)
    print(pretty_table)


# ###########################       ERROR HANDLING
def try_and_catch(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except VariantUndefined as e:
        logger.info(repr(e))
        return bad_variant_parameters(repr(e))
    except GenomicIntervalUndefined as e:
        logger.info(repr(e))
        return bad_genomic_interval_parameters(repr(e))
    except Exception as e:
        logger.exception(e)
        return service_unavailable_message()


@flask_app.errorhandler(Exception)
def unhandled_exception(e):
    logger.error('! An uncaught exception reached the default exception handler !')
    logger.exception(e)
    return 'Internal server error', 500


def service_unavailable_message():
    return '503: Service unavailable. Retry later.', 503, {'x-error': 'service unavailable'}


def bad_variant_parameters(msg: str):
    return 'One or more variants included in the request miss required attributes or contain misspells. ' \
           f'Detailed message: {msg}', 400, {'x-error': 'Cannot answer to this request'}


def bad_genomic_interval_parameters(msg: str):
    return 'One or more genomic intervals included in the request miss required attributes or contain misspells. ' \
           f'Detailed message: {msg}', 400, {'x-error': 'Cannot answer to this request'}


if __name__ == '__main__':
    run()
    import sys
    from database import database
    db_user = sys.argv[1]
    db_password = sys.argv[2]
    db_port = sys.argv[3]
    database.config_db_engine_parameters(flask_app, db_user, db_password, db_port)


# def are_mutations_unique_between_filter_groups(regions: dict) -> bool:
#     all_mutations = list()
#     if regions.get(ReqParamKeys.WITH_VARIANTS) is not None:
#         all_mutations.append(regions.get(ReqParamKeys.WITH_VARIANTS))
#     if regions.get(ReqParamKeys.WITH_VARS_ON_SAME_CHROM_COPY) is not None:
#         all_mutations.append(regions.get(ReqParamKeys.WITH_VARS_ON_SAME_CHROM_COPY))
#     if regions.get(ReqParamKeys.WITH_VARS_ON_DIFF_CHROM_COPY) is not None:
#         all_mutations.append(regions.get(ReqParamKeys.WITH_VARS_ON_DIFF_CHROM_COPY))
#     for region in all_mutations:
#         count = 0
#         for region2 in all_mutations:
#             if region == region2:
#                 count += 1
#         if count > 1:
#             return False
#     return True
