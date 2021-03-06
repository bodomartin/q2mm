#!/usr/bin/python
# Still need to add functions to make pretty print statements and logs.
'''
compare
-------
Contains code necessary to evaluate the objective function,

.. math:: \chi^2 = w^2 (x_r - x_c)^2

where :math:`w` is a weight, :math:`x_r` is the reference data point's value,
and :math:`x_c` is the calculated or force field's value for the data point.

'''
from __future__ import print_function
from collections import defaultdict
from itertools import izip
import argparse
import logging
import logging.config
import numpy as np
import sys

import calculate
import constants as co
import datatypes

logger = logging.getLogger(__name__)

def main(args):
    logger.log(1, '>>> main <<<')
    parser = return_compare_parser()
    opts = parser.parse_args(args)
    r_data = calculate.main(opts.reference.split())
    c_data = calculate.main(opts.calculate.split())
    score = compare_data(r_data, c_data)
    # Pretty readouts.
    if opts.output:
        pretty_data_comp(r_data, c_data, output=opts.output)
    if opts.print:
        pretty_data_comp(r_data, c_data)
    logger.log(1, '>>> score: {}'.format(score))

def pretty_data_comp(r_data, c_data, output=None):
    """
    Recalculates score along with making a pretty output.
    """
    logger.log(1, '>>> pretty_data_comp <<<')
    strings = []
    strings.append('--' + ' Label '.ljust(30, '-') +
                   '--' + ' Weight '.center(8, '-') + 
                   '--' + ' R. Value '.center(13, '-') + 
                   '--' + ' C. Value '.center(13, '-') +
                   '--' + ' Score '.center(13, '-') + '--')
    score_typ = defaultdict(float)
    score_tot = 0.
    for r, c in izip(r_data, c_data):
        logger.log(1, '>>> {} {}'.format(r, c))
        # Double check data types.
        if r.typ == 't':
            diff = abs(r.val - c.val)
            if diff > 180.:
                diff = 360. - diff
        else:
            diff = r.val - c.val
        # Calculate score.
        score = r.wht**2 * diff**2
        # Update total.
        score_tot += score
        # Update dictionary.
        score_typ[r.typ] += score
        strings.append('  {:<30}  {:>8.2f}  {:>13.4f}  {:>13.4f}  {:>13.4f}  '.format(
                r.lbl, r.wht, r.val, c.val, score))
    strings.append('-' * 89)
    strings.append('{:<20} {:20.4f}'.format('Total score:', score_tot))
    strings.append('{:<20} {:20d}'.format('Num. data points:', len(r_data)))
    strings.append('-' * 79)
    for k, v in score_typ.iteritems():
        strings.append('{:<20} {:20.4f}'.format(k + ':', v))
    if output:
        with open(output, 'w') as f:
            for line in strings:
                f.write('{}\n'.format(line))
    else:
        for line in strings:
            print(line)

def return_compare_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--calculate', '-c', type=str, metavar = '" commands for calculate.py"',
        help=('These commands produce the FF data. Leave one space after the '
              '1st quotation mark enclosing the arguments.'))
    parser.add_argument(
        '--reference', '-r', type=str, metavar='" commands for calculate.py"',
        help=('These commands produce the QM/reference data. Leave one space '
              'after the 1st quotation mark enclosing the arguments.'))
    parser.add_argument(
        '--output', '-o', type=str, metavar='filename', 
        help='Write pretty output to filename.')
    parser.add_argument(
        '--print', '-p', action='store_true', dest='print',
        help='Print pretty output.')
    return parser

def compare_data(r_data, c_data, zero=True):
    logger.log(1, '>>> compare_data <<<')
    # r_data = np.array(sorted(r_data, key=datatypes.datum_sort_key))
    # c_data = np.array(sorted(c_data, key=datatypes.datum_sort_key))
    if zero:
        zero_energies(r_data)
    correlate_energies(r_data, c_data)
    import_weights(r_data)
    return calculate_score(r_data, c_data)

def zero_energies(data):
    logger.log(1, '>>> zero_energies <<<')
    # Go one data type at a time.
    # We do so because the group numbers are only unique within a given data
    # type.
    for energy_type in ['e', 'eo']:
        # Determine the unique group numbers.
        indices = np.where([x.typ == energy_type for x in data])[0]
        # logger.log(1, '>>> indices: {}'.format(indices))
        # logger.log(1, '>>> data[indices]: {}'.format(data[indices]))
        # logger.log(1, '>>> [x.idx_1 for x in data[indices]]: {}'.format(
        #         [x.idx_1 for x in data[indices]]))
        unique_group_nums = set([x.idx_1 for x in data[indices]])
        # Loop through the unique group numbers.
        for unique_group_num in unique_group_nums:
            # Pick out all data points that are unique to this data type
            # and group number.
            more_indices = np.where(
                [x.typ == energy_type and x.idx_1 == unique_group_num
                 for x in data])[0]
            # Find the zero for this grouping.
            zero = min([x.val for x in data[more_indices]])
            for ind in more_indices:
                data[ind].val -= zero

def correlate_energies(r_data, c_data):
    logger.log(1, '>>> correlate_energies <<<')
    for indices in select_group_of_energies(r_data):
        # logger.log(1, '>>> indices:\n{}'.format(indices))
        # logger.log(1, '>>> r_data[indices[0]].typ:\n{}'.format(
        #         r_data[indices[0]].typ))
        if r_data[indices[0]].typ in ['e', 'eo']:
            zero, zero_ind = min(
                (x.val, i) for i, x in enumerate(r_data[indices]))
            zero_ind = indices[zero_ind]
            # Wow, that was a lot of work to get the index of the zero.
            # Now, we need to get that same sub list, and update the calculated
            # data. As long as they are sorted the same, the indices should
            # match up.
            zero = c_data[zero_ind].val
            for ind in indices:
                c_data[ind].val -= zero
        elif r_data[indices[0]].typ in ['ea', 'eao']:
            avg = sum([x.val for x in r_data[indices]])/len(r_data[indices])
            for ind in indices:
                r_data[ind].val -= avg
            avg = sum([x.val for x in c_data[indices]])/len(c_data[indices])
            for ind in indices:
                c_data[ind].val -= avg

def select_group_of_energies(data):
    """
    Used to get the indices (numpy.array) for a single group of energies.
    """
    for energy_type in ['e', 'eo', 'ea', 'eao']:
        # Get all energy indices.
        indices = np.where([x.typ == energy_type for x in data])[0]
        # Get the unique group numbers.
        unique_group_nums = set([x.idx_1 for x in data[indices]])
        for unique_group_num in unique_group_nums:
            # Get all the indicies for the given energy type and for a single
            # group.
            more_indices = np.where(
                [x.typ == energy_type and x.idx_1 == unique_group_num
                 for x in data])[0]
            yield more_indices

def import_weights(data):
    for datum in data:
        if datum.wht is None:
            if datum.typ == 'eig':
                if datum.idx_1 == datum.idx_2 == 1:
                    datum.wht = co.WEIGHTS['eig_i']
                elif datum.idx_1 == datum.idx_2:
                    datum.wht = co.WEIGHTS['eig_d']
                elif datum.idx_1 != datum.idx_2:
                    datum.wht = co.WEIGHTS['eig_o']
            else:
                datum.wht = co.WEIGHTS[datum.typ]

# Need to add some pretty print outs for this.
def calculate_score(r_data, c_data):
    logger.log(1, '>>> calculate_score <<<')
    score = 0.
    for r_datum, c_datum in izip(r_data, c_data):
        logger.log(1, '>>> {} {}'.format(r_datum, c_datum))
        # Perhaps add a checking option here to ensure all the attributes
        # of each data point match up.
        # When we're talking about torsions, need to make sure that the
        # difference between -179 and 179 is 2, not 358.
        if r_datum.typ == 't':
            diff = abs(r_datum.val - c_datum.val)
            if diff > 180.:
                diff = 360. - diff
        # Simpler for other data types.
        else:
            diff = r_datum.val - c_datum.val
        individual_score = r_datum.wht**2 * diff**2
        score += individual_score
    logger.log(5, 'SCORE: {}'.format(score))
    return score
            
if __name__ == '__main__':
    logging.config.dictConfig(co.LOG_SETTINGS)
    main(sys.argv[1:])
